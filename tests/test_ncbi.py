import asyncio
import http.client
import io
import ssl
import types
import urllib.error

import pytest

from peptide_dosage import ncbi

SAMPLE_XML = b"""<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2021</Year></PubDate></JournalIssue>
          <Title>Journal of Tests</Title>
        </Journal>
        <ArticleTitle>A <i>great</i> study</ArticleTitle>
        <Abstract>
          <AbstractText Label="Background">It works.</AbstractText>
          <AbstractText Label="Results">Yes it does.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Doe</LastName><ForeName>Jane</ForeName></Author>
          <Author><LastName>Roe</LastName><Initials>R</Initials></Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList><ArticleId IdType="doi">10.1000/xyz</ArticleId></ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

EMPTY_XML = b'<?xml version="1.0" ?><PubmedArticleSet></PubmedArticleSet>'


class FakeResponse:
    def __init__(self, data=SAMPLE_XML, read_exc=None):
        self._data = data
        self._read_exc = read_exc

    def read(self):
        if self._read_exc is not None:
            raise self._read_exc
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "reason", {}, io.BytesIO(b""))


@pytest.fixture
def script(monkeypatch):
    """Patch urlopen to play back responses/exceptions in order (the last one repeats).

    Also patches time.sleep so tests never really wait. No real network access.
    """
    sleeps = []
    monkeypatch.setattr(ncbi, "time", types.SimpleNamespace(sleep=sleeps.append))

    def install(*outcomes):
        calls = []
        queue = list(outcomes)

        def fake_urlopen(req, timeout=None):
            calls.append((req, timeout))
            outcome = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        return calls, sleeps

    return install


def test_parse_sample():
    art = ncbi.parse_pubmed_xml(SAMPLE_XML, "123")
    assert art["pmid"] == "123"
    assert art["title"] == "A great study"
    assert art["authors"] == ["Jane Doe", "Roe R"]
    assert art["authors_str"] == "Jane Doe, Roe R"
    assert art["abstract"] == "BACKGROUND: It works.\n\nRESULTS: Yes it does."
    assert art["journal"] == "Journal of Tests"
    assert art["pub_date"] == "2021"
    assert art["doi"] == "10.1000/xyz"
    assert art["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/"


def test_fetch_success(script):
    calls, _ = script(FakeResponse())
    art = ncbi.fetch_pubmed_article_sync(" 123 ")
    assert art["title"] == "A great study"
    assert len(calls) == 1
    req, timeout = calls[0]
    assert timeout == ncbi.DEFAULT_TIMEOUT
    assert "id=123" in req.full_url
    assert "example.com" not in req.full_url
    assert "%40" not in req.full_url
    ua = req.get_header("User-agent")
    assert "example.com" not in ua
    assert "mailto" not in ua


def test_api_key_passed(script):
    calls, _ = script(FakeResponse())
    ncbi.fetch_pubmed_article_sync("1", api_key="KEY")
    assert "api_key=KEY" in calls[0][0].full_url


@pytest.mark.parametrize("code", [429, 500, 503])
def test_retry_then_success(script, code):
    calls, sleeps = script(http_error(code), FakeResponse())
    art = ncbi.fetch_pubmed_article_sync("123")
    assert art["pmid"] == "123"
    assert len(calls) == 2
    assert len(sleeps) == 1


@pytest.mark.parametrize("code", [429, 502])
def test_retries_exhausted_raises_runtime_error(script, code):
    calls, sleeps = script(http_error(code))
    with pytest.raises(RuntimeError):
        ncbi.fetch_pubmed_article_sync("123", retries=4)
    assert len(calls) == 4
    assert len(sleeps) == 3
    assert all(s <= ncbi.MAX_BACKOFF_SECONDS for s in sleeps)


def test_retry_after_honored_but_capped(script):
    err = urllib.error.HTTPError("http://x", 429, "Too Many", {"Retry-After": "120"}, io.BytesIO(b""))
    _, sleeps = script(err, FakeResponse())
    ncbi.fetch_pubmed_article_sync("123")
    assert sleeps == [ncbi.MAX_BACKOFF_SECONDS]


def test_404_not_retried(script):
    calls, _ = script(http_error(404))
    with pytest.raises(RuntimeError):
        ncbi.fetch_pubmed_article_sync("123")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "exc",
    [
        http.client.IncompleteRead(b"abc", 10),
        http.client.RemoteDisconnected("closed"),
        http.client.HTTPException("bad"),
        ssl.SSLError("handshake failed"),
        ConnectionResetError("reset"),
        TimeoutError("timed out"),
        urllib.error.URLError("no route"),
        OSError("network unreachable"),
    ],
)
def test_network_failures_become_runtime_error(script, exc):
    calls, _ = script(FakeResponse(read_exc=exc))
    with pytest.raises(RuntimeError):
        ncbi.fetch_pubmed_article_sync("123")
    assert len(calls) == ncbi.DEFAULT_RETRIES


def test_failure_raised_by_urlopen_itself(script):
    script(ssl.SSLError("boom"))
    with pytest.raises(RuntimeError):
        ncbi.fetch_pubmed_article_sync("123")


def test_read_error_then_success(script):
    calls, _ = script(FakeResponse(read_exc=http.client.IncompleteRead(b"")), FakeResponse())
    assert ncbi.fetch_pubmed_article_sync("123")["pmid"] == "123"
    assert len(calls) == 2


def test_retries_zero_still_attempts_once(script):
    calls, _ = script(FakeResponse())
    assert ncbi.fetch_pubmed_article_sync("123", retries=0)["pmid"] == "123"
    assert len(calls) == 1


@pytest.mark.parametrize("bad", ["", "  ", "abc", "12a", "-5", None, "1.5"])
def test_invalid_pmid_value_error(script, bad):
    calls, _ = script(FakeResponse())
    with pytest.raises(ValueError):
        ncbi.fetch_pubmed_article_sync(bad)
    assert calls == []


def test_empty_result_value_error(script):
    script(FakeResponse(data=EMPTY_XML))
    with pytest.raises(ValueError):
        ncbi.fetch_pubmed_article_sync("123")


def test_unparseable_result_value_error(script):
    calls, _ = script(FakeResponse(data=b"<not xml"))
    with pytest.raises(ValueError):
        ncbi.fetch_pubmed_article_sync("123")
    assert len(calls) == 1


def test_async_wrapper_success(script):
    script(FakeResponse())
    art = asyncio.run(ncbi.fetch_pubmed_article("123"))
    assert art["title"] == "A great study"


def test_async_wrapper_errors(script):
    script(http_error(500))
    with pytest.raises(RuntimeError):
        asyncio.run(ncbi.fetch_pubmed_article("123", retries=1))
    with pytest.raises(ValueError):
        asyncio.run(ncbi.fetch_pubmed_article("bad"))
