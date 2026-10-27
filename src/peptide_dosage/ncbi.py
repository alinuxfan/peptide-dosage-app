"""
NCBI E-utilities client for PubMed article retrieval.

Fetches article metadata (title, authors, abstract, journal, publication date, URL)
for PubMed IDs (PMIDs) via the NCBI Entrez E-utilities XML API (`efetch.fcgi`).
"""

import asyncio
import http.client
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NCBI_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFAULT_TOOL = "peptide-dosage-toga"
DEFAULT_USER_AGENT = f"{DEFAULT_TOOL}/1.0 (+https://github.com/alinuxfan/peptide-dosage-app)"

# Keep waits short since the UI has no cancel: the timeout applies per socket operation,
# so the typical worst case is about 2 x 10s plus one capped backoff.
DEFAULT_RETRIES = 2  # maximum attempts
DEFAULT_TIMEOUT = 10.0  # seconds per attempt
MAX_BACKOFF_SECONDS = 3.0


def validate_pmid(pmid: str | int) -> str:
    """Validate and clean a PMID. Raises ValueError if invalid."""
    if pmid is None:
        raise ValueError("PMID cannot be None.")
    pmid_str = str(pmid).strip()
    if not pmid_str:
        raise ValueError("PMID cannot be empty.")
    if not re.fullmatch(r"\d+", pmid_str):
        raise ValueError(f"Invalid PMID '{pmid_str}': PMIDs must contain only numeric digits.")
    return pmid_str


def parse_pubmed_xml(xml_content: bytes | str, pmid: str) -> dict:
    """Parse PubMed XML returned by NCBI efetch into structured article dict.

    Returns dict with keys:
        pmid, title, authors, authors_str, abstract, journal, pub_date, doi, url
    """
    if isinstance(xml_content, str):
        xml_bytes = xml_content.encode("utf-8")
    else:
        xml_bytes = xml_content

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse XML response from NCBI for PMID {pmid}: {e}")

    article_elem = root.find(".//PubmedArticle")
    if article_elem is None:
        err_msg = root.find(".//ERROR")
        if err_msg is not None and err_msg.text:
            raise ValueError(f"NCBI error for PMID {pmid}: {err_msg.text.strip()}")
        raise ValueError(f"No article found in PubMed for PMID {pmid}.")

    medline = article_elem.find(".//MedlineCitation")
    article = medline.find(".//Article") if medline is not None else article_elem.find(".//Article")
    if article is None:
        raise ValueError(f"Malformed article XML structure for PMID {pmid}.")

    # 1. Title
    title_elem = article.find(".//ArticleTitle")
    if title_elem is not None:
        title = "".join(title_elem.itertext()).strip()
        title = re.sub(r"\s+", " ", title)
    else:
        title = "Untitled Document"

    # 2. Authors
    authors: list[str] = []
    author_list = article.find(".//AuthorList")
    if author_list is not None:
        for a in author_list.findall("Author"):
            last = a.find("LastName")
            fore = a.find("ForeName")
            init = a.find("Initials")
            collab = a.find("CollectiveName")

            last_text = last.text.strip() if last is not None and last.text else ""
            fore_text = fore.text.strip() if fore is not None and fore.text else ""
            init_text = init.text.strip() if init is not None and init.text else ""
            collab_text = collab.text.strip() if collab is not None and collab.text else ""

            if fore_text and last_text:
                authors.append(f"{fore_text} {last_text}")
            elif last_text and init_text:
                authors.append(f"{last_text} {init_text}")
            elif last_text:
                authors.append(last_text)
            elif collab_text:
                authors.append(collab_text)

    if not authors:
        authors = ["Unknown Authors"]

    authors_str = ", ".join(authors)

    # 3. Abstract
    abstract_nodes = article.findall(".//Abstract/AbstractText")
    abstract_parts: list[str] = []
    for ab in abstract_nodes:
        label = ab.attrib.get("Label")
        txt = "".join(ab.itertext()).strip()
        txt = re.sub(r"\s+", " ", txt)
        if not txt:
            continue
        if label:
            abstract_parts.append(f"{label.upper()}: {txt}")
        else:
            abstract_parts.append(txt)

    if abstract_parts:
        abstract = "\n\n".join(abstract_parts)
    else:
        abstract = "No abstract available in PubMed."

    # 4. Journal & Publication Date
    journal_elem = article.find(".//Journal/Title")
    if journal_elem is None:
        journal_elem = article.find(".//Journal/ISOAbbreviation")
    journal = "".join(journal_elem.itertext()).strip() if journal_elem is not None else ""

    pub_year_elem = article.find(".//JournalIssue/PubDate/Year")
    if pub_year_elem is None:
        pub_year_elem = article.find(".//JournalIssue/PubDate/MedlineDate")
    pub_date = pub_year_elem.text.strip() if pub_year_elem is not None and pub_year_elem.text else ""

    # 5. DOI
    doi = ""
    for id_elem in article_elem.findall(".//ArticleIdList/ArticleId"):
        if id_elem.attrib.get("IdType") == "doi" and id_elem.text:
            doi = id_elem.text.strip()
            break

    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "authors_str": authors_str,
        "abstract": abstract,
        "journal": journal,
        "pub_date": pub_date,
        "doi": doi,
        "url": url,
    }


def _backoff_delay(attempt: int, retry_after: str | None = None) -> float:
    """Seconds to wait after failed attempt number `attempt` (0-based), capped.

    Honors a numeric Retry-After header when present, but never waits past the cap.
    """
    delay = 1.0 * (attempt + 1)
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    return min(delay, MAX_BACKOFF_SECONDS)


def fetch_pubmed_article_sync(
    pmid: str | int,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
    api_key: str | None = None,
) -> dict:
    """Fetch article data from NCBI E-utilities synchronously with retry backoff.

    `retries` is the maximum number of attempts (minimum 1). Raises ValueError for an
    invalid PMID or an article that is not found / cannot be parsed, and RuntimeError
    for any network or server failure (after retries are exhausted).
    """
    clean_pmid = validate_pmid(pmid)

    params = {
        "db": "pubmed",
        "id": clean_pmid,
        "retmode": "xml",
        "tool": DEFAULT_TOOL,
    }
    if api_key:
        params["api_key"] = api_key

    query_str = urllib.parse.urlencode(params)
    url = f"{NCBI_EFETCH_URL}?{query_str}"
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/xml, text/xml",
    }

    req = urllib.request.Request(url, headers=headers)
    attempts = max(1, int(retries))

    for attempt in range(attempts):
        is_last = attempt == attempts - 1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                xml_data = resp.read()
        except urllib.error.HTTPError as http_err:
            # 429 (rate limited) and 5xx (server trouble) are worth retrying.
            retryable = http_err.code == 429 or http_err.code >= 500
            http_err.close()
            if retryable and not is_last:
                time.sleep(_backoff_delay(attempt, http_err.headers.get("Retry-After")))
                continue
            if http_err.code == 429:
                msg = "NCBI is rate-limiting requests right now. Please try again in a moment."
            elif http_err.code >= 500:
                msg = f"The NCBI PubMed service is having problems (HTTP {http_err.code}). Please try again later."
            else:
                msg = f"NCBI rejected the request (HTTP {http_err.code}: {http_err.reason})."
            raise RuntimeError(msg) from http_err
        except (OSError, http.client.HTTPException) as net_err:
            # Covers URLError, timeouts, connection resets, ssl.SSLError (all OSError
            # subclasses) and http.client.IncompleteRead / RemoteDisconnected.
            if not is_last:
                time.sleep(_backoff_delay(attempt))
                continue
            raise RuntimeError(
                "Could not reach NCBI PubMed. Check your internet connection and try again "
                f"({type(net_err).__name__}: {net_err})."
            ) from net_err
        return parse_pubmed_xml(xml_data, clean_pmid)

    # Unreachable: every iteration either returns, raises, or continues to a later one.
    raise RuntimeError(f"Failed to fetch PMID {clean_pmid}.")


async def fetch_pubmed_article(
    pmid: str | int,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
    api_key: str | None = None,
) -> dict:
    """Async wrapper that runs the NCBI E-utilities fetch in a background thread."""
    return await asyncio.to_thread(
        fetch_pubmed_article_sync,
        pmid,
        retries=retries,
        timeout=timeout,
        api_key=api_key,
    )
