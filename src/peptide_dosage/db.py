import sqlite3
import json
import os
import csv
from datetime import datetime, timezone

from . import calc

# Set once at startup by app.py, to app.paths.data / "peptides.db" —
# the TUI's cwd-relative default isn't writable on iOS/Android app sandboxes.
DB_PATH = os.path.join(os.path.dirname(__file__), "peptides.db")


def set_db_path(path):
    global DB_PATH
    DB_PATH = str(path)

# Default peptides database with scientific PubMed citations
DEFAULT_PEPTIDES = [
    {
        "name": "BPC-157",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Commonly used for joint/tendon healing. Standard dose: 250mcg - 500mcg daily or twice daily.",
        "schedule": [
            ("Week 1-2", 250.0, "mcg"),
            ("Week 3-4", 350.0, "mcg"),
            ("Week 5-6", 500.0, "mcg"),
        ],
        "sources": [
            {"title": "Emerging Use of BPC-157 in Orthopaedic Sports Medicine", "pmid": "40756949", "url": "https://pubmed.ncbi.nlm.nih.gov/40756949/"},
            {"title": "Role of BPC-157 in Tissue Repair and Pain Management", "pmid": "41898733", "url": "https://pubmed.ncbi.nlm.nih.gov/41898733/"}
        ]
    },
    {
        "name": "Ipamorelin",
        "vial_mg": 5.0,
        "water_ml": 2.5,
        "dose": 200.0,
        "unit": "mcg",
        "freq": "daily (before bed)",
        "notes": "Growth hormone secretagogue. Standard dose: 200mcg - 300mcg daily, 5 days on / 2 days off.",
        "schedule": [
            ("Week 1-4", 200.0, "mcg"),
            ("Week 5-8", 250.0, "mcg"),
            ("Week 9-12", 300.0, "mcg"),
        ],
        "sources": [
            {"title": "Ipamorelin, the first selective growth hormone secretagogue", "pmid": "9849822", "url": "https://pubmed.ncbi.nlm.nih.gov/9849822/"},
            {"title": "Pharmacokinetic-pharmacodynamic modeling of ipamorelin in human volunteers", "pmid": "10496658", "url": "https://pubmed.ncbi.nlm.nih.gov/10496658/"}
        ]
    },
    {
        "name": "CJC-1295",
        "vial_mg": 2.0,
        "water_ml": 2.0,
        "dose": 100.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Often combined with Ipamorelin. Standard dose: 100mcg - 150mcg, 1-3 times daily.",
        "schedule": [
            ("Week 1-8", 100.0, "mcg"),
        ],
        "sources": [
            {"title": "Prolonged stimulation of GH and IGF-I secretion by CJC-1295 in healthy adults", "pmid": "16352683", "url": "https://pubmed.ncbi.nlm.nih.gov/16352683/"},
            {"title": "Pulsatile secretion of growth hormone during continuous stimulation by CJC-1295", "pmid": "17018654", "url": "https://pubmed.ncbi.nlm.nih.gov/17018654/"}
        ]
    },
    {
        "name": "Semaglutide",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 0.25,
        "unit": "mg",
        "freq": "weekly",
        "notes": "GLP-1 receptor agonist. Standard titration starts at 0.25mg weekly for 4 weeks.",
        "schedule": [
            ("Week 1-4 (Titration)", 0.25, "mg"),
            ("Week 5-8 (Titration)", 0.50, "mg"),
            ("Week 9-12 (Titration)", 1.00, "mg"),
            ("Week 13-16 (Titration)", 1.70, "mg"),
            ("Week 17+ (Maintenance)", 2.40, "mg"),
        ],
        "sources": [
            {"title": "Once-Weekly Semaglutide in Adults with Overweight or Obesity (STEP 1)", "pmid": "33567185", "url": "https://pubmed.ncbi.nlm.nih.gov/33567185/"},
            {"title": "Long-term weight loss effects of semaglutide in obesity (SELECT trial)", "pmid": "38740993", "url": "https://pubmed.ncbi.nlm.nih.gov/38740993/"}
        ]
    },
    {
        "name": "Tirzepatide",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 2.5,
        "unit": "mg",
        "freq": "weekly",
        "notes": "GIP/GLP-1 receptor agonist (often referred to as GLP-2 dual agonist). Titrated monthly.",
        "schedule": [
            ("Week 1-4 (Titration)", 2.5, "mg"),
            ("Week 5-8 (Titration)", 5.0, "mg"),
            ("Week 9-12 (Titration)", 7.5, "mg"),
            ("Week 13-16 (Titration)", 10.0, "mg"),
            ("Week 17-20 (Titration)", 12.5, "mg"),
            ("Week 21+ (Maintenance)", 15.0, "mg"),
        ],
        "sources": [
            {"title": "Tirzepatide Once Weekly for the Treatment of Obesity (SURMOUNT-1)", "pmid": "35658024", "url": "https://pubmed.ncbi.nlm.nih.gov/35658024/"},
            {"title": "Tirzepatide as Compared with Semaglutide for the Treatment of Obesity", "pmid": "40353578", "url": "https://pubmed.ncbi.nlm.nih.gov/40353578/"}
        ]
    },
    {
        "name": "Retatrutide",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 2.0,
        "unit": "mg",
        "freq": "weekly",
        "notes": "GLP-1/GIP/GCGR triple agonist (GLP-3). Standard titration starts at 2mg weekly.",
        "schedule": [
            ("Week 1-4 (Titration)", 2.0, "mg"),
            ("Week 5-8 (Titration)", 4.0, "mg"),
            ("Week 9-12 (Titration)", 8.0, "mg"),
            ("Week 13+ (Maintenance)", 12.0, "mg"),
        ],
        "sources": [
            {"title": "Triple-Hormone-Receptor Agonist Retatrutide for Obesity - A Phase 2 Trial", "pmid": "37366315", "url": "https://pubmed.ncbi.nlm.nih.gov/37366315/"},
            {"title": "Efficacy and safety of retatrutide, a novel GLP-1, GIP, and glucagon receptor agonist", "pmid": "40291085", "url": "https://pubmed.ncbi.nlm.nih.gov/40291085/"}
        ]
    },
    {
        "name": "MOTS-c",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 5.0,
        "unit": "mg",
        "freq": "3x weekly",
        "notes": "Mitochondria-derived peptide. Dosed 5mg three times weekly (e.g. Mon/Wed/Fri) for 4-6 weeks.",
        "schedule": [
            ("Week 1-4 (Active)", 5.0, "mg"),
        ],
        "sources": [
            {"title": "Mitochondrial-derived peptide MOTS-c promotes metabolic homeostasis and reduces obesity", "pmid": "25738459", "url": "https://pubmed.ncbi.nlm.nih.gov/25738459/"},
            {"title": "MOTS-c improves intrinsic muscle mitochondrial bioenergetic health", "pmid": "41520850", "url": "https://pubmed.ncbi.nlm.nih.gov/41520850/"}
        ]
    },
    {
        "name": "GLOW Blend",
        "vial_mg": 50.0,
        "water_ml": 3.0,
        "dose": 1.5,
        "unit": "mg",
        "freq": "daily",
        "notes": "Cosmetic cellular renewal blend containing GHK-Cu, BPC-157, and TB-500.",
        "schedule": [
            ("Week 1-4 (Daily)", 1.5, "mg"),
        ],
        "sources": [
            {"title": "Regenerative and Protective Actions of the GHK-Cu Peptide in Light of New Clinical Data", "pmid": "29986520", "url": "https://pubmed.ncbi.nlm.nih.gov/29986520/"}
        ]
    },
    {
        "name": "KLOW Blend",
        "vial_mg": 50.0,
        "water_ml": 3.0,
        "dose": 1.5,
        "unit": "mg",
        "freq": "daily",
        "notes": "Anti-inflammatory and skin/hair recovery blend containing GHK-Cu, BPC-157, TB-500, and KPV.",
        "schedule": [
            ("Week 1-4 (Daily)", 1.5, "mg"),
        ],
        "sources": [
            {"title": "The tripeptide GHK-Cu in prevention of oxidative stress and tissue repair", "pmid": "22616288", "url": "https://pubmed.ncbi.nlm.nih.gov/22616288/"}
        ]
    },
    {
        "name": "Sermorelin",
        "vial_mg": 5.0,
        "water_ml": 2.5,
        "dose": 300.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "GHRH analogue promoting natural GH release. Typically injected nightly.",
        "schedule": [
            ("Week 1-12 (Nightly)", 300.0, "mcg"),
        ],
        "sources": [
            {"title": "Sermorelin: a review of its use in diagnosis and treatment of GH deficiency", "pmid": "18031173", "url": "https://pubmed.ncbi.nlm.nih.gov/18031173/"},
            {"title": "Once daily subcutaneous growth hormone-releasing hormone therapy accelerates growth", "pmid": "8772599", "url": "https://pubmed.ncbi.nlm.nih.gov/8772599/"}
        ]
    },
    {
        "name": "AOD-9604",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 300.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Anti-obesity peptide fragment. Administered in the morning on an empty stomach.",
        "schedule": [
            ("Week 1-12 (Morning)", 300.0, "mcg"),
        ],
        "sources": [
            {"title": "Effects of human GH and its lipolytic fragment (AOD9604) on lipid metabolism", "pmid": "11713213", "url": "https://pubmed.ncbi.nlm.nih.gov/11713213/"}
        ]
    },
    {
        "name": "NAD+",
        "vial_mg": 500.0,
        "water_ml": 5.0,
        "dose": 50.0,
        "unit": "mg",
        "freq": "twice weekly",
        "notes": "Nicotinamide Adenine Dinucleotide. Reconstituted at 100mg/mL. Subcutaneous injection.",
        "schedule": [
            ("Week 1-2 (Starting)", 25.0, "mg"),
            ("Week 3-4 (Target)", 50.0, "mg"),
            ("Week 5+ (Maintenance)", 100.0, "mg"),
        ],
        "sources": [
            {"title": "NAD+ metabolism and its roles in cellular physiology and disease", "pmid": "31548645", "url": "https://pubmed.ncbi.nlm.nih.gov/31548645/"}
        ]
    },
    {
        "name": "Tesamorelin",
        "vial_mg": 2.0,
        "water_ml": 2.0,
        "dose": 2.0,
        "unit": "mg",
        "freq": "daily (at bedtime)",
        "notes": "GHRH analogue for visceral adipose reduction and growth hormone stimulation. Standard dose: 2mg daily.",
        "schedule": [
            ("Week 1-12 (Nightly)", 2.0, "mg"),
        ],
        "sources": [
            {"title": "Effects of Tesemorelin, a Growth Hormone-Releasing Hormone Analogue, in HIV Patients", "pmid": "17148701", "url": "https://pubmed.ncbi.nlm.nih.gov/17148701/"},
            {"title": "Tesemorelin for the treatment of visceral adiposity", "pmid": "21848416", "url": "https://pubmed.ncbi.nlm.nih.gov/21848416/"}
        ]
    },
    {
        "name": "DSIP",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 100.0,
        "unit": "mcg",
        "freq": "nightly (before bed)",
        "notes": "Nonapeptide studied for sleep regulation and stress/HPA-axis modulation. Standard research dose: 100mcg - 300mcg nightly before sleep.",
        "schedule": [
            ("Week 1-2", 100.0, "mcg"),
            ("Week 3-4", 200.0, "mcg"),
            ("Week 5+", 300.0, "mcg"),
        ],
        "sources": [
            {"title": "Effects of delta sleep-inducing peptide on sleep of chronic insomniac patients. A double-blind study", "pmid": "1299794", "url": "https://pubmed.ncbi.nlm.nih.gov/1299794/"},
            {"title": "Characterization, properties and multivariate functions of delta-sleep-inducing peptide (DSIP)", "pmid": "6548966", "url": "https://pubmed.ncbi.nlm.nih.gov/6548966/"}
        ]
    },
    {
        "name": "Melanotan II",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "daily (loading), then 2-3x weekly (maintenance)",
        "notes": "Non-selective melanocortin receptor agonist used for skin pigmentation/tanning and libido. Loading dose 250mcg - 500mcg daily until desired tan, then 500mcg 2-3x weekly maintenance.",
        "schedule": [
            ("Week 1-2 (Loading)", 250.0, "mcg"),
            ("Week 3-4 (Loading)", 500.0, "mcg"),
            ("Week 5+ (Maintenance)", 500.0, "mcg"),
        ],
        "sources": [
            {"title": "Evaluation of melanotan-II, a superpotent cyclic melanotropic peptide in a pilot phase-I clinical study", "pmid": "8637402", "url": "https://pubmed.ncbi.nlm.nih.gov/8637402/"},
            {"title": "Synthetic melanotropic peptide initiates erections in men with psychogenic erectile dysfunction: double-blind, placebo controlled crossover study", "pmid": "9679884", "url": "https://pubmed.ncbi.nlm.nih.gov/9679884/"}
        ]
    },
    {
        "name": "GHK-Cu",
        "vial_mg": 100.0,
        "water_ml": 5.0,
        "dose": 1.0,
        "unit": "mg",
        "freq": "daily",
        "notes": "Naturally occurring copper-binding tripeptide used both topically (cosmetic serums for skin remodeling/collagen synthesis) and via subcutaneous injection (systemic tissue repair, anti-inflammatory, wound healing). Standard injectable dose: 1mg - 2mg daily.",
        "schedule": [
            ("Week 1-4", 1.0, "mg"),
            ("Week 5-8", 1.5, "mg"),
            ("Week 9-12", 2.0, "mg"),
        ],
        "sources": [
            {"title": "GHK Peptide as a Natural Modulator of Multiple Cellular Pathways in Skin Regeneration", "pmid": "26236730", "url": "https://pubmed.ncbi.nlm.nih.gov/26236730/"}
        ]
    },
    {
        "name": "Cagrilintide",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 0.25,
        "unit": "mg",
        "freq": "weekly",
        "notes": "Long-acting amylin analogue, often paired with GLP-1 agonists (e.g. semaglutide) for weight management. Standard titration starts at 0.25mg weekly, following a semaglutide-style dose escalation.",
        "schedule": [
            ("Week 1-4 (Titration)", 0.25, "mg"),
            ("Week 5-8 (Titration)", 0.50, "mg"),
            ("Week 9-12 (Titration)", 1.00, "mg"),
            ("Week 13+ (Maintenance)", 2.40, "mg"),
        ],
        "sources": [
            {"title": "Development of Cagrilintide, a Long-Acting Amylin Analogue", "pmid": "34288673", "url": "https://pubmed.ncbi.nlm.nih.gov/34288673/"},
            {"title": "Safety, tolerability, pharmacokinetics, and pharmacodynamics of concomitant administration of multiple doses of cagrilintide with semaglutide 2.4 mg for weight management: a randomised, controlled, phase 1b trial", "pmid": "33894838", "url": "https://pubmed.ncbi.nlm.nih.gov/33894838/"}
        ]
    },
    {
        "name": "CJC-1295 with DAC",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 1.0,
        "unit": "mg",
        "freq": "weekly (or twice weekly)",
        "notes": "Long-acting GHRH analog conjugated to a Drug Affinity Complex (DAC) that binds serum albumin, extending its half-life to roughly 6-8 days -- distinct from CJC-1295 no-DAC, which requires daily dosing. Standard dose: 1mg - 2mg once or twice weekly.",
        "schedule": [
            ("Week 1-4", 1.0, "mg"),
            ("Week 5-8", 2.0, "mg"),
        ],
        "sources": [
            {"title": "Once-daily administration of CJC-1295, a long-acting growth hormone-releasing hormone (GHRH) analog, normalizes growth in the GHRH knockout mouse", "pmid": "16822960", "url": "https://pubmed.ncbi.nlm.nih.gov/16822960/"}
        ]
    },
    {
        "name": "Selank",
        "vial_mg": 11.0,
        "water_ml": 5.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "daily (SubQ injection, morning or split AM/PM)",
        "notes": "Synthetic heptapeptide analogue of tuftsin studied for anxiolytic, neuroprotective, and cognitive-enhancing effects. Administered via subcutaneous (SubQ) injection (typically lower abdomen or outer thigh using a 29-31G U-100 syringe) reconstituted with bacteriostatic water. Standard dose: 250mcg - 500mcg daily (morning or split AM/early afternoon), often cycled 2-4 weeks on followed by a 1-2 week break.",
        "schedule": [
            ("Week 1-2 (Initiation)", 250.0, "mcg"),
            ("Week 3-4 (Maintenance)", 500.0, "mcg"),
        ],
        "sources": [
            {"title": "Efficacy and possible mechanisms of action of a new peptide anxiolytic selank in the therapy of generalized anxiety disorders and neurasthenia", "pmid": "18454096", "url": "https://pubmed.ncbi.nlm.nih.gov/18454096/"},
            {"title": "Peptide-based Anxiolytics: The Molecular Aspects of Heptapeptide Selank Biological Activity", "pmid": "30255741", "url": "https://pubmed.ncbi.nlm.nih.gov/30255741/"}
        ]
    },
    {
        "name": "Semax",
        "vial_mg": 11.0,
        "water_ml": 5.0,
        "dose": 300.0,
        "unit": "mcg",
        "freq": "daily (SubQ injection, morning)",
        "notes": "ACTH(4-10) fragment analogue studied for neuroprotection, focus/cognition, and BDNF expression. Administered via subcutaneous (SubQ) injection (typically lower abdomen or outer thigh using a 29-31G U-100 syringe) reconstituted with bacteriostatic water. Morning administration is strongly recommended to avoid sleep disruption or insomnia due to its stimulating nootropic effects. Standard dose: 250mcg - 600mcg daily (morning), often cycled 2-4 weeks on (or 5 days on / 2 days off).",
        "schedule": [
            ("Week 1-2 (Initiation)", 300.0, "mcg"),
            ("Week 3-4 (Maintenance)", 600.0, "mcg"),
        ],
        "sources": [
            {"title": "Semax, an ACTH(4-10) analogue with nootropic properties, activates BDNF expression in the rat hippocampus and frontal cortex", "pmid": "16967870", "url": "https://pubmed.ncbi.nlm.nih.gov/16967870/"},
            {"title": "The Peptide Drug ACTH(4-7)PGP (Semax) Suppresses mRNA Transcripts Encoding Proinflammatory Mediators Induced by Reversible Ischemia of the Rat Brain", "pmid": "34097675", "url": "https://pubmed.ncbi.nlm.nih.gov/34097675/"}
        ]
    },
    {
        "name": "Pinealon",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 100.0,
        "unit": "mcg",
        "freq": "daily (short course)",
        "notes": "Short synthetic tripeptide bioregulator (Khavinson peptide) studied for neuroprotective/antioxidant effects. Standard protocol: 100mcg - 200mcg daily for a 10-20 day course, repeated periodically.",
        "schedule": [
            ("Days 1-10 (Course 1)", 100.0, "mcg"),
            ("Days 1-10 (Course 2, next cycle)", 200.0, "mcg"),
        ],
        "sources": [
            {"title": "Pinealon protects the rat offspring from prenatal hyperhomocysteinemia", "pmid": "22567179", "url": "https://pubmed.ncbi.nlm.nih.gov/22567179/"}
        ]
    },
    {
        "name": "PT-141",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 1.0,
        "unit": "mg",
        "freq": "as needed (PRN), 45 min before activity, max 1x/24hr",
        "notes": "FDA-approved (as Vyleesi) melanocortin receptor agonist for hypoactive sexual desire disorder; also used off-label for erectile dysfunction. Standard dose: 0.5mg - 1.75mg subcutaneously as needed, at least 45 minutes before activity, no more than once per 24 hours.",
        "schedule": [
            ("Initial/Trial Dose", 0.5, "mg"),
            ("Standard Dose", 1.0, "mg"),
            ("Max Dose", 1.75, "mg"),
        ],
        "sources": [
            {"title": "Bremelanotide for the Treatment of Hypoactive Sexual Desire Disorder: Two Randomized Phase 3 Trials", "pmid": "31599840", "url": "https://pubmed.ncbi.nlm.nih.gov/31599840/"},
            {"title": "Evaluation of the safety, pharmacokinetics and pharmacodynamic effects of subcutaneously administered PT-141, a melanocortin receptor agonist, in healthy male subjects and in patients with an inadequate response to Viagra", "pmid": "14999221", "url": "https://pubmed.ncbi.nlm.nih.gov/14999221/"}
        ]
    },
    {
        "name": "Epithalon",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 5.0,
        "unit": "mg",
        "freq": "daily (short course)",
        "notes": "Synthetic tetrapeptide bioregulator (Khavinson peptide) studied for telomerase activation and cellular senescence. Standard protocol: 5mg - 10mg daily for a 10-20 day course, typically 1-2 courses per year.",
        "schedule": [
            ("Days 1-10 (Course)", 5.0, "mg"),
            ("Days 1-20 (Extended Course)", 10.0, "mg"),
        ],
        "sources": [
            {"title": "Epithalon peptide induces telomerase activity and telomere elongation in human somatic cells", "pmid": "12937682", "url": "https://pubmed.ncbi.nlm.nih.gov/12937682/"},
            {"title": "Peptide promotes overcoming of the division limit in human somatic cell", "pmid": "15455129", "url": "https://pubmed.ncbi.nlm.nih.gov/15455129/"}
        ]
    },
    {
        "name": "AICAR",
        "vial_mg": 50.0,
        "water_ml": 2.0,
        "dose": 50.0,
        "unit": "mg",
        "freq": "3x weekly",
        "notes": "AMPK activator studied as an exercise-mimetic compound affecting fatty acid oxidation and glucose uptake in skeletal muscle. Standard research dose: 50mg - 100mg, 3 times weekly.",
        "schedule": [
            ("Week 1-2", 50.0, "mg"),
            ("Week 3-4", 100.0, "mg"),
        ],
        "sources": [
            {"title": "AICA riboside increases AMP-activated protein kinase, fatty acid oxidation, and glucose uptake in rat muscle", "pmid": "9435525", "url": "https://pubmed.ncbi.nlm.nih.gov/9435525/"},
            {"title": "Activity of LKB1 and AMPK-related kinases in skeletal muscle: effects of contraction, phenformin, and AICAR", "pmid": "15068958", "url": "https://pubmed.ncbi.nlm.nih.gov/15068958/"}
        ]
    },
    {
        "name": "TB-500",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 2.5,
        "unit": "mg",
        "freq": "2x weekly (loading)",
        "notes": "Synthetic fragment of Thymosin Beta-4 studied for tissue repair, angiogenesis, and reduced inflammation. Standard loading dose: 2mg - 2.5mg twice weekly for 4-6 weeks, then maintenance dose every 2-4 weeks.",
        "schedule": [
            ("Week 1-4 (Loading)", 2.5, "mg"),
            ("Week 5-6 (Loading)", 2.5, "mg"),
            ("Week 7+ (Maintenance)", 2.5, "mg"),
        ],
        "sources": [
            {"title": "The actin binding site on thymosin beta4 promotes angiogenesis", "pmid": "14500546", "url": "https://pubmed.ncbi.nlm.nih.gov/14500546/"},
            {"title": "Thymosin beta4 accelerates wound healing", "pmid": "10469335", "url": "https://pubmed.ncbi.nlm.nih.gov/10469335/"}
        ]
    },
    {
        "name": "IGF-1 LR3",
        "vial_mg": 0.1,
        "water_ml": 1.0,
        "dose": 20.0,
        "unit": "mcg",
        "freq": "daily (post-workout)",
        "notes": "Modified IGF-1 analog with reduced IGF-binding-protein affinity and extended half-life, used for its potent anabolic/anti-catabolic effects. Micro-dosed: 20mcg - 50mcg daily, typically injected locally post-workout in short 4-6 week cycles.",
        "schedule": [
            ("Week 1-2", 20.0, "mcg"),
            ("Week 3-4", 40.0, "mcg"),
            ("Week 5-6", 50.0, "mcg"),
        ],
        "sources": [
            {"title": "Long R3 insulin-like growth factor-I (IGF-I) infusion stimulates organ growth but reduces plasma IGF-I, IGF-II and IGF binding protein concentrations in the guinea pig", "pmid": "7561636", "url": "https://pubmed.ncbi.nlm.nih.gov/7561636/"},
            {"title": "Detection of LongR3-IGF-I, Des(1-3)-IGF-I, and R3-IGF-I using immunopurification and high resolution mass spectrometry for antidoping purposes", "pmid": "33587816", "url": "https://pubmed.ncbi.nlm.nih.gov/33587816/"}
        ]
    },
    {
        "name": "Melanotan I",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "daily (loading), then 2-3x weekly (maintenance)",
        "notes": "Selective MC1R agonist studied for skin pigmentation/tanning; the linear precursor peptide to Melanotan II (basis of the approved drug afamelanotide), with a milder side-effect profile (less nausea/libido effect) than MT-II. Loading dose 250mcg - 500mcg daily until desired tan, then 2-3x weekly maintenance.",
        "schedule": [
            ("Week 1-2 (Loading)", 250.0, "mcg"),
            ("Week 3-4 (Loading)", 500.0, "mcg"),
            ("Week 5+ (Maintenance)", 500.0, "mcg"),
        ],
        "sources": [
            {"title": "Skin pigmentation and pharmacokinetics of melanotan-I in humans", "pmid": "9113347", "url": "https://pubmed.ncbi.nlm.nih.gov/9113347/"},
            {"title": "Afamelanotide, an agonistic analog of α-melanocyte-stimulating hormone, in dermal phototoxicity of erythropoietic protoporphyria", "pmid": "21073357", "url": "https://pubmed.ncbi.nlm.nih.gov/21073357/"}
        ]
    },
    {
        "name": "HCG",
        "vial_mg": 5.0,
        "water_ml": 1.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "2-3x weekly",
        "notes": "Human Chorionic Gonadotropin, an LH-mimetic glycoprotein hormone used to stimulate Leydig cell testosterone production and maintain testicular function/fertility (e.g. alongside TRT or for secondary hypogonadism). NOTE: real-world HCG is conventionally dosed in International Units (IU), not mg/mcg by mass -- a common vial is labeled '5,000 IU', not '5mg'. The mg/mcg figures here are placeholders forced into this app's mg-based schema, not a validated IU conversion -- verify actual IU dosing against your product's labeling.",
        "schedule": [
            ("Week 1-4", 250.0, "mcg"),
            ("Week 5+ (Maintenance)", 250.0, "mcg"),
        ],
        "sources": [
            {"title": "Human chorionic gonadotropin treatment: a viable option for management of secondary hypogonadism and male infertility", "pmid": "33345656", "url": "https://pubmed.ncbi.nlm.nih.gov/33345656/"},
            {"title": "Evaluating the Combination of Human Chorionic Gonadotropin and Clomiphene Citrate in Treatment of Male Hypogonadotropic Hypogonadism: A Prospective Study", "pmid": "34164348", "url": "https://pubmed.ncbi.nlm.nih.gov/34164348/"}
        ]
    },
    {
        "name": "GHRP-2",
        "vial_mg": 5.0,
        "water_ml": 2.5,
        "dose": 100.0,
        "unit": "mcg",
        "freq": "daily (1-3x, pre-meal)",
        "notes": "Ghrelin-receptor-agonist growth hormone secretagogue (pharmaceutical name pralmorelin); also clinically used as a diagnostic agent for GH deficiency. Increases appetite alongside GH release, and is often paired with a GHRH analog like CJC-1295. Standard dose: 100mcg - 300mcg, 1-3 times daily.",
        "schedule": [
            ("Week 1-4", 100.0, "mcg"),
            ("Week 5-8", 200.0, "mcg"),
            ("Week 9-12", 300.0, "mcg"),
        ],
        "sources": [
            {"title": "Growth hormone releasing peptide-2 (GHRP-2), like ghrelin, increases food intake in healthy men", "pmid": "15699539", "url": "https://pubmed.ncbi.nlm.nih.gov/15699539/"},
            {"title": "Pralmorelin: GHRP 2, GPA 748, growth hormone-releasing peptide 2, KP-102 D, KP-102 LN, KP-102D, KP-102LN", "pmid": "15230633", "url": "https://pubmed.ncbi.nlm.nih.gov/15230633/"}
        ]
    },
    {
        "name": "GHRP-6",
        "vial_mg": 5.0,
        "water_ml": 2.5,
        "dose": 100.0,
        "unit": "mcg",
        "freq": "daily (1-3x)",
        "notes": "Hexapeptide growth hormone secretagogue acting via the ghrelin receptor; associated with pronounced appetite stimulation and cytoprotective effects reported alongside GH release. Standard dose: 100mcg - 300mcg, 1-3 times daily.",
        "schedule": [
            ("Week 1-4", 100.0, "mcg"),
            ("Week 5-8", 200.0, "mcg"),
            ("Week 9-12", 300.0, "mcg"),
        ],
        "sources": [
            {"title": "Growth hormone releasing peptide (GHRP-6) stimulates phosphatidylinositol (PI) turnover in human pituitary somatotroph cells", "pmid": "7772238", "url": "https://pubmed.ncbi.nlm.nih.gov/7772238/"},
            {"title": "Growth hormone-releasing effect of oral growth hormone-releasing peptide 6 (GHRP-6) administration in children with short stature", "pmid": "7581965", "url": "https://pubmed.ncbi.nlm.nih.gov/7581965/"}
        ]
    },
    {
        "name": "Thymosin Alpha-1",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 1.6,
        "unit": "mg",
        "freq": "2x weekly",
        "notes": "Immunomodulatory thymic peptide (marketed outside the US as Zadaxin) studied for immune restoration, vaccine-response enhancement, and adjunct use in infections/oncology. Standard clinical dose: 1.6mg subcutaneously twice weekly.",
        "schedule": [
            ("Week 1-4", 1.6, "mg"),
            ("Week 5+ (Maintenance)", 1.6, "mg"),
        ],
        "sources": [
            {"title": "Immune Modulation with Thymosin Alpha 1 Treatment", "pmid": "27450734", "url": "https://pubmed.ncbi.nlm.nih.gov/27450734/"},
            {"title": "Comprehensive Review of the Safety and Efficacy of Thymosin Alpha 1 in Human Clinical Trials", "pmid": "38308608", "url": "https://pubmed.ncbi.nlm.nih.gov/38308608/"}
        ]
    },
    {
        "name": "Thymalin",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 5.0,
        "unit": "mg",
        "freq": "daily (short course)",
        "notes": "Calf thymus-derived peptide bioregulator (Khavinson/Morozov) studied for immune restoration and geroprotective effects in aging populations, including a long-term Russian cohort study. Standard protocol: 5mg - 10mg daily for a 10-day course, repeated periodically.",
        "schedule": [
            ("Days 1-10 (Course)", 5.0, "mg"),
            ("Days 1-10 (Higher-Dose Course)", 10.0, "mg"),
        ],
        "sources": [
            {"title": "Thymalin: Activation of Differentiation of Human Hematopoietic Stem Cells", "pmid": "33237528", "url": "https://pubmed.ncbi.nlm.nih.gov/33237528/"},
            {"title": "[Geroprotective effect of thymalin and epithalamin]", "pmid": "12577695", "url": "https://pubmed.ncbi.nlm.nih.gov/12577695/"}
        ]
    },
    {
        "name": "Oxytocin",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 40.0,
        "unit": "mcg",
        "freq": "daily to 2x daily",
        "notes": "Nonapeptide hormone studied for prosocial, anxiolytic, and analgesic effects via subcutaneous administration. Standard research dose: 40mcg - 100mcg subcutaneously, once or twice daily.",
        "schedule": [
            ("Week 1-2", 40.0, "mcg"),
            ("Week 3+", 100.0, "mcg"),
        ],
        "sources": [
            {"title": "Subcutaneous Oxytocin Injection Reduces Heat Pain: A Randomized-Controlled Trial", "pmid": "38642595", "url": "https://pubmed.ncbi.nlm.nih.gov/38642595/"},
            {"title": "Oxytocin: pharmacology and clinical application", "pmid": "3534134", "url": "https://pubmed.ncbi.nlm.nih.gov/3534134/"}
        ]
    },
    {
        "name": "VIP",
        "vial_mg": 5.0,
        "water_ml": 5.0,
        "dose": 50.0,
        "unit": "mcg",
        "freq": "as directed (intranasal), up to 4x daily",
        "notes": "Vasoactive Intestinal Peptide, a 28-amino-acid neuropeptide with vasodilatory, immunomodulatory, and neuroprotective properties; used off-label intranasally in some chronic inflammatory response syndrome (CIRS) protocols. Standard dose: 50mcg per spray, up to 4 times daily.",
        "schedule": [
            ("Week 1-2", 50.0, "mcg"),
            ("Week 3+ (Maintenance)", 50.0, "mcg"),
        ],
        "sources": [
            {"title": "Vasoactive intestinal peptide in man: pharmacokinetics, metabolic and circulatory effects", "pmid": "730072", "url": "https://pubmed.ncbi.nlm.nih.gov/730072/"},
            {"title": "Structure-activity relationship of vasoactive intestinal peptide (VIP): potent agonists and potential clinical applications", "pmid": "18172612", "url": "https://pubmed.ncbi.nlm.nih.gov/18172612/"}
        ]
    },
    {
        "name": "SS-31 (Elamipretide)",
        "vial_mg": 50.0,
        "water_ml": 2.0,
        "dose": 4.0,
        "unit": "mg",
        "freq": "daily",
        "notes": "Mitochondria-targeted tetrapeptide studied for age-related mitochondrial dysfunction, oxidative stress, and exercise tolerance; binds cardiolipin in the inner mitochondrial membrane. Standard research dose: 4mg - 10mg daily via subcutaneous injection.",
        "schedule": [
            ("Week 1-2", 4.0, "mg"),
            ("Week 3-4", 8.0, "mg"),
            ("Week 5+ (Maintenance)", 10.0, "mg"),
        ],
        "sources": [
            {"title": "Improving mitochondrial function with SS-31 reverses age-related redox stress and improves exercise tolerance in aged mice", "pmid": "30597195", "url": "https://pubmed.ncbi.nlm.nih.gov/30597195/"},
            {"title": "The mitochondrially targeted peptide elamipretide (SS-31) improves ADP sensitivity in aged mitochondria by increasing uptake through the adenine nucleotide translocator (ANT)", "pmid": "37462785", "url": "https://pubmed.ncbi.nlm.nih.gov/37462785/"}
        ]
    },
    {
        "name": "Snap-8",
        "vial_mg": 50.0,
        "water_ml": 10.0,
        "dose": 5.0,
        "unit": "mg",
        "freq": "daily (topical)",
        "notes": "Acetyl Glutamyl Heptapeptide-1, a synthetic octapeptide derived from SNAP-25 fragments used in topical cosmetic formulations to reduce expression-line depth (Botox-alternative mechanism). Primarily applied topically as a diluted serum rather than injected; no PubMed-indexed clinical studies specific to Snap-8 were found (only cosmetic-industry/patent literature) -- treat dosing here as a rough topical-dilution reference only.",
        "schedule": [
            ("Week 1-4 (Daily Topical)", 5.0, "mg"),
        ],
        "sources": []
    },
    {
        "name": "KPV",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Alpha-MSH-derived anti-inflammatory tripeptide (Lysine-Proline-Valine) studied for gut/skin inflammation via NF-kB and PepT1-mediated pathways. Standard research dose: 250mcg - 500mcg daily.",
        "schedule": [
            ("Week 1-2", 250.0, "mcg"),
            ("Week 3-4", 500.0, "mcg"),
        ],
        "sources": [
            {"title": "PepT1-mediated tripeptide KPV uptake reduces intestinal inflammation", "pmid": "18061177", "url": "https://pubmed.ncbi.nlm.nih.gov/18061177/"},
            {"title": "Alpha-melanocyte-related tripeptide, Lys-d-Pro-Val, ameliorates endotoxin-induced nuclear factor kappaB translocation and activation", "pmid": "11256945", "url": "https://pubmed.ncbi.nlm.nih.gov/11256945/"}
        ]
    },
    {
        "name": "AHK-Cu",
        "vial_mg": 50.0,
        "water_ml": 5.0,
        "dose": 1.0,
        "unit": "mg",
        "freq": "daily",
        "notes": "Copper Tripeptide-3, a GHK-Cu-related copper-binding tripeptide studied primarily for hair follicle/dermal papilla stimulation and skin rejuvenation, mostly used topically. No PubMed-indexed primary studies specific to AHK-Cu were found via search (only cosmetic-industry sources) -- data here is a rough community-dosing reference only.",
        "schedule": [
            ("Week 1-4", 1.0, "mg"),
            ("Week 5-8", 2.0, "mg"),
        ],
        "sources": []
    },
    {
        "name": "Ara-290 (Cibinetide)",
        "vial_mg": 4.0,
        "water_ml": 2.0,
        "dose": 2.0,
        "unit": "mg",
        "freq": "3x weekly",
        "notes": "Non-hematopoietic erythropoietin-derived peptide (Cibinetide) studied for tissue-protective and neuropathic pain relief via the innate repair receptor, without EPO's hematopoietic/cardiovascular side effects. Standard research dose: 1mg - 4mg, 3 times weekly.",
        "schedule": [
            ("Week 1-4", 1.0, "mg"),
            ("Week 5-8", 2.0, "mg"),
            ("Week 9+ (Maintenance)", 4.0, "mg"),
        ],
        "sources": [
            {"title": "ARA 290, a peptide derived from the tertiary structure of erythropoietin, produces long-term relief of neuropathic pain coupled with suppression of the spinal microglia response", "pmid": "24529189", "url": "https://pubmed.ncbi.nlm.nih.gov/24529189/"},
            {"title": "ARA290, a peptide derived from the tertiary structure of erythropoietin, produces long-term relief of neuropathic pain: an experimental study in rats and β-common receptor knockout mice", "pmid": "21873879", "url": "https://pubmed.ncbi.nlm.nih.gov/21873879/"}
        ]
    },
    {
        "name": "LL-37",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 200.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Human cathelicidin antimicrobial peptide with broad-spectrum antimicrobial, immunomodulatory, and wound-healing activity. Standard research dose: 100mcg - 200mcg daily; human safety/efficacy data remain limited.",
        "schedule": [
            ("Week 1-2", 100.0, "mcg"),
            ("Week 3-4", 200.0, "mcg"),
        ],
        "sources": [
            {"title": "LL-37, the only human member of the cathelicidin family of antimicrobial peptides", "pmid": "16716248", "url": "https://pubmed.ncbi.nlm.nih.gov/16716248/"},
            {"title": "LL-37: Cathelicidin-related antimicrobial peptide with pleiotropic activity", "pmid": "27117377", "url": "https://pubmed.ncbi.nlm.nih.gov/27117377/"}
        ]
    },
    {
        "name": "Adipotide",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 0.5,
        "unit": "mg",
        "freq": "3x weekly",
        "notes": "Prohibitin-targeted proapoptotic peptide (CKGGRAKDC-GG-D(KLAKLAK)2) that induces apoptosis in white-adipose-tissue vasculature. Demonstrated obesity reversal in rodent/primate studies but with documented reversible renal effects in the primate trial -- investigational, not human-approved, and carries real safety signals distinct from most other entries in this list.",
        "schedule": [
            ("Week 1-2", 0.25, "mg"),
            ("Week 3-4", 0.5, "mg"),
        ],
        "sources": [
            {"title": "Reversal of obesity by targeted ablation of adipose tissue", "pmid": "15133506", "url": "https://pubmed.ncbi.nlm.nih.gov/15133506/"},
            {"title": "Rapid and weight-independent improvement of glucose tolerance induced by a peptide designed to elicit apoptosis in adipose tissue endothelium", "pmid": "22733798", "url": "https://pubmed.ncbi.nlm.nih.gov/22733798/"}
        ]
    },
    {
        "name": "Kisspeptin-10",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 100.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Potent stimulator of the hypothalamic-pituitary-gonadal axis via GnRH secretion; studied for reproductive hormone/fertility research and hypogonadism. Standard research dose: 100mcg - 200mcg daily.",
        "schedule": [
            ("Week 1-2", 100.0, "mcg"),
            ("Week 3-4", 200.0, "mcg"),
        ],
        "sources": [
            {"title": "The effects of kisspeptin-10 on reproductive hormone release show sexual dimorphism in humans", "pmid": "21976724", "url": "https://pubmed.ncbi.nlm.nih.gov/21976724/"},
            {"title": "Kisspeptin-10 is a potent stimulator of LH and increases pulse frequency in men", "pmid": "21632807", "url": "https://pubmed.ncbi.nlm.nih.gov/21632807/"}
        ]
    },
    {
        "name": "5-Amino-1MQ",
        "vial_mg": 50.0,
        "water_ml": 5.0,
        "dose": 10.0,
        "unit": "mg",
        "freq": "daily",
        "notes": "Small-molecule NNMT (nicotinamide N-methyltransferase) inhibitor studied preclinically for adipose-tissue fat metabolism and weight management; not a peptide, and most commonly taken orally in the research community rather than injected. Standard protocol: 10mg daily, cycled 4-8 weeks.",
        "schedule": [
            ("Week 1-8 (Daily)", 10.0, "mg"),
        ],
        "sources": [
            {"title": "Small molecule inhibitor of nicotinamide N-methyltransferase shows anti-proliferative activity in HeLa cells", "pmid": "33645410", "url": "https://pubmed.ncbi.nlm.nih.gov/33645410/"},
            {"title": "Reduced calorie diet combined with NNMT inhibition establishes a distinct microbiome in DIO mice", "pmid": "35013352", "url": "https://pubmed.ncbi.nlm.nih.gov/35013352/"}
        ]
    },
    {
        "name": "Dihexa",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 2.0,
        "unit": "mg",
        "freq": "daily",
        "notes": "Angiotensin IV analog and HGF/c-Met system activator studied preclinically for cognitive/neuroprotective effects; poor water solubility means it is typically compounded sublingually or orally in practice rather than injected. Standard research dose: 2mg - 4mg daily.",
        "schedule": [
            ("Week 1-2", 2.0, "mg"),
            ("Week 3-4", 4.0, "mg"),
        ],
        "sources": [
            {"title": "The Brain Hepatocyte Growth Factor/c-Met Receptor System: A New Target for the Treatment of Alzheimer's Disease", "pmid": "25649658", "url": "https://pubmed.ncbi.nlm.nih.gov/25649658/"},
            {"title": "The development of small molecule angiotensin IV analogs to treat Alzheimer's and Parkinson's diseases", "pmid": "25455861", "url": "https://pubmed.ncbi.nlm.nih.gov/25455861/"}
        ]
    },
    {
        "name": "Mazdutide",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 3.0,
        "unit": "mg",
        "freq": "weekly",
        "notes": "GLP-1/glucagon receptor dual agonist studied for weight management and type 2 diabetes. Standard titration starts at 3mg weekly, escalating toward a 9mg maintenance dose as tolerated.",
        "schedule": [
            ("Week 1-4 (Titration)", 3.0, "mg"),
            ("Week 5-8 (Titration)", 4.5, "mg"),
            ("Week 9-12 (Titration)", 6.0, "mg"),
            ("Week 13+ (Maintenance)", 9.0, "mg"),
        ],
        "sources": [
            {"title": "Once-Weekly Mazdutide in Chinese Adults with Obesity or Overweight", "pmid": "40421736", "url": "https://pubmed.ncbi.nlm.nih.gov/40421736/"},
            {"title": "A phase 2 randomised controlled trial of mazdutide in Chinese overweight adults or adults with obesity", "pmid": "38092790", "url": "https://pubmed.ncbi.nlm.nih.gov/38092790/"}
        ]
    },
    {
        "name": "Survodutide",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 0.6,
        "unit": "mg",
        "freq": "weekly",
        "notes": "Glucagon receptor/GLP-1 receptor dual agonist studied for obesity and MASH (fatty liver disease). Slow-titration schedule starting at 0.6mg weekly, escalating toward a 3.6mg-6.0mg maintenance dose as tolerated.",
        "schedule": [
            ("Week 1-4 (Titration)", 0.6, "mg"),
            ("Week 5-8 (Titration)", 1.2, "mg"),
            ("Week 9-16 (Titration)", 2.4, "mg"),
            ("Week 17+ (Maintenance)", 3.6, "mg"),
        ],
        "sources": [
            {"title": "Survodutide Once Weekly for the Treatment of Adults with Obesity", "pmid": "42253238", "url": "https://pubmed.ncbi.nlm.nih.gov/42253238/"},
            {"title": "A Phase 2 Randomized Trial of Survodutide in MASH and Fibrosis", "pmid": "38847460", "url": "https://pubmed.ncbi.nlm.nih.gov/38847460/"}
        ]
    },
    {
        "name": "Cartalax",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 100.0,
        "unit": "mcg",
        "freq": "daily (short course)",
        "notes": "Synthetic tripeptide bioregulator (Ala-Glu-Asp, Khavinson-lab series) studied preclinically for cartilage/chondrocyte support, in the same family as Epithalon and Pinealon. Standard protocol: 100mcg - 150mcg daily for a 10-day course, repeated periodically. No registered human clinical trials or peptide-specific dose-ranging data exist for this specific peptide.",
        "schedule": [
            ("Days 1-10 (Course 1)", 100.0, "mcg"),
            ("Days 1-10 (Course 2, next cycle)", 150.0, "mcg"),
        ],
        "sources": [
            {"title": "Peptide bioregulators: the new class of geroprotectors. Message 2. Clinical studies results", "pmid": "24003726", "url": "https://pubmed.ncbi.nlm.nih.gov/24003726/"}
        ]
    },
    {
        "name": "Melatonin",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 3.0,
        "unit": "mg",
        "freq": "nightly (before bed)",
        "notes": "Pineal hormone regulating circadian rhythm/sleep onset; not a peptide, and far more commonly taken orally than injected. Standard dose: 1mg - 5mg nightly, roughly 30-60 minutes before bed.",
        "schedule": [
            ("Week 1-2", 1.0, "mg"),
            ("Week 3+", 3.0, "mg"),
        ],
        "sources": [
            {"title": "Optimizing the Time and Dose of Melatonin as a Sleep-Promoting Drug: A Systematic Review of Randomized Controlled Trials and Dose-Response Meta-Analysis", "pmid": "38888087", "url": "https://pubmed.ncbi.nlm.nih.gov/38888087/"},
            {"title": "Meta-analysis: melatonin for the treatment of primary sleep disorders", "pmid": "23691095", "url": "https://pubmed.ncbi.nlm.nih.gov/23691095/"}
        ]
    },
    {
        "name": "Vitamin B12 (Methylcobalamin)",
        "vial_mg": 5.0,
        "water_ml": 1.0,
        "dose": 1000.0,
        "unit": "mcg",
        "freq": "weekly",
        "notes": "Methylcobalamin (active form of vitamin B12); not a peptide, but a common injectable alongside peptide protocols for energy/neuropathy support. Standard IM/SC dose: 500mcg - 1500mcg weekly.",
        "schedule": [
            ("Week 1-4", 500.0, "mcg"),
            ("Week 5+", 1000.0, "mcg"),
        ],
        "sources": [
            {"title": "Vitamin B12 Supplementation in Diabetic Neuropathy: A 1-Year, Randomized, Double-Blind, Placebo-Controlled Trial", "pmid": "33513879", "url": "https://pubmed.ncbi.nlm.nih.gov/33513879/"},
            {"title": "A randomized, open labeled study comparing the serum levels of cobalamin after three doses of 500 mcg vs. a single dose methylcobalamin of 1500 mcg in patients with peripheral neuropathy", "pmid": "30013732", "url": "https://pubmed.ncbi.nlm.nih.gov/30013732/"}
        ]
    },
    {
        "name": "CJC-1295 / Ipamorelin Blend",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 200.0,
        "unit": "mcg",
        "freq": "daily (before bed)",
        "notes": "Pre-mixed 1:1 blend of CJC-1295 (no DAC) and Ipamorelin, combining a GHRH analog with a selective GH secretagogue for a synergistic GH pulse. Standard combined dose: 200mcg (100mcg + 100mcg) - 300mcg (150mcg + 150mcg) daily, typically before bed.",
        "schedule": [
            ("Week 1-4", 200.0, "mcg"),
            ("Week 5-8", 300.0, "mcg"),
        ],
        "sources": [
            {"title": "Prolonged stimulation of GH and IGF-I secretion by CJC-1295 in healthy adults", "pmid": "16352683", "url": "https://pubmed.ncbi.nlm.nih.gov/16352683/"},
            {"title": "Ipamorelin, the first selective growth hormone secretagogue", "pmid": "9849822", "url": "https://pubmed.ncbi.nlm.nih.gov/9849822/"}
        ]
    },
    {
        "name": "Cagrilintide / Semaglutide Blend",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 0.5,
        "unit": "mg",
        "freq": "weekly",
        "notes": "Pre-mixed combination of Cagrilintide and Semaglutide (a community analog of Novo Nordisk's investigational dual amylin/GLP-1 combination). Standard titration starts at 0.5mg combined (0.25mg + 0.25mg) weekly, following a semaglutide-style dose escalation.",
        "schedule": [
            ("Week 1-4 (Titration)", 0.5, "mg"),
            ("Week 5-8 (Titration)", 1.0, "mg"),
            ("Week 9-12 (Titration)", 2.0, "mg"),
            ("Week 13+ (Maintenance)", 2.4, "mg"),
        ],
        "sources": [
            {"title": "Development of Cagrilintide, a Long-Acting Amylin Analogue", "pmid": "34288673", "url": "https://pubmed.ncbi.nlm.nih.gov/34288673/"},
            {"title": "Safety, tolerability, pharmacokinetics, and pharmacodynamics of concomitant administration of multiple doses of cagrilintide with semaglutide 2.4 mg for weight management: a randomised, controlled, phase 1b trial", "pmid": "33894838", "url": "https://pubmed.ncbi.nlm.nih.gov/33894838/"}
        ]
    },
    {
        "name": "BPC-157 / TB-500 Blend",
        "vial_mg": 20.0,
        "water_ml": 2.0,
        "dose": 1.0,
        "unit": "mg",
        "freq": "2x weekly",
        "notes": "Pre-mixed regenerative blend combining BPC-157 and TB-500 (Thymosin Beta-4 fragment) for synergistic tissue repair, recovery, and reduced inflammation. Standard combined dose: 0.5mg - 1mg, 2-3 times weekly.",
        "schedule": [
            ("Week 1-4 (Loading)", 1.0, "mg"),
            ("Week 5+ (Maintenance)", 0.5, "mg"),
        ],
        "sources": [
            {"title": "Emerging Use of BPC-157 in Orthopaedic Sports Medicine", "pmid": "40756949", "url": "https://pubmed.ncbi.nlm.nih.gov/40756949/"},
            {"title": "Thymosin beta4 accelerates wound healing", "pmid": "10469335", "url": "https://pubmed.ncbi.nlm.nih.gov/10469335/"}
        ]
    },
    {
        "name": "PNC-27",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 1.0,
        "unit": "mg",
        "freq": "daily",
        "notes": "Chimeric p53-penetratin peptide (p53 HDM-2-binding domain fused to a cell-penetrating leader) studied preclinically as an anti-cancer agent -- selectively binds membrane-bound HDM-2 on cancer cells, forming pores and inducing necrosis, while sparing normal cells that lack surface HDM-2. Investigational only; no human clinical trials or established human dosing exist. Community research dose: 0.5mg - 1mg daily (extrapolated from in vitro/animal studies, not clinically validated).",
        "schedule": [
            ("Week 1-2", 0.5, "mg"),
            ("Week 3+", 1.0, "mg"),
        ],
        "sources": [
            {"title": "Anticancer peptide PNC-27 adopts an HDM-2-binding conformation and kills cancer cells by binding to HDM-2 in their membranes", "pmid": "20080680", "url": "https://pubmed.ncbi.nlm.nih.gov/20080680/"},
            {"title": "Anti-Cancer Peptide PNC-27 Kills Cancer Cells by Unique Interactions with Plasma Membrane-Bound hdm-2 and with Mitochondrial Membranes Causing Mitochondrial Disruption", "pmid": "38802154", "url": "https://pubmed.ncbi.nlm.nih.gov/38802154/"}
        ]
    },
    {
        "name": "FOXO4-DRI",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 5.0,
        "unit": "mg",
        "freq": "3x weekly (short course)",
        "notes": "Retro-inverso senolytic peptide that disrupts the FOXO4-p53 interaction, selectively triggering apoptosis in senescent cells while sparing healthy tissue. Studied preclinically in aging, cartilage, and pulmonary fibrosis models. Investigational only; no human clinical trials or established human dosing exist. Community research protocol: 5mg, 3 times weekly for a short course (e.g. 1-2 weeks), cycled periodically.",
        "schedule": [
            ("Days 1-14 (Course)", 5.0, "mg"),
        ],
        "sources": [
            {"title": "Senolytic Peptide FOXO4-DRI Selectively Removes Senescent Cells From in vitro Expanded Human Chondrocytes", "pmid": "33996787", "url": "https://pubmed.ncbi.nlm.nih.gov/33996787/"},
            {"title": "Targeting the FOXO4-p53 axis by retro-inverso peptide senolytic agents: a pharmacological strategy to mitigate brain aging and cognitive decline", "pmid": "42024235", "url": "https://pubmed.ncbi.nlm.nih.gov/42024235/"}
        ]
    },
    {
        "name": "LC216 (Lipotropic/MIC Blend)",
        "vial_mg": 300.0,
        "water_ml": 10.0,
        "dose": 30.0,
        "unit": "mg",
        "freq": "1-2x weekly",
        "notes": "Generic multi-component lipotropic (MIC-style) blend combining lipotropic agents such as Methionine, Inositol, and Choline (often with added B12/B-complex) to support hepatic fat metabolism; supplier-specific proprietary formulas vary in exact composition and ratio, and this entry's vial/dose figures are a rough placeholder, not a specific validated formula -- adjust to match your actual product's label. Controlled clinical evidence for the combined formulation's weight-loss effect is limited, though individual components have established roles in hepatic lipid metabolism. Typically sold pre-mixed as a ready-to-inject liquid rather than reconstituted from powder.",
        "schedule": [
            ("Week 1-4", 30.0, "mg"),
        ],
        "sources": []
    },
    {
        "name": "Adamax",
        "vial_mg": 10.0,
        "water_ml": 2.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Supplier-listed nootropic product; the specific active compound was not confirmed, so no literature-backed dosing or citations could be sourced for it. Values here are a generic peptide-nootropic placeholder (similar scale to the other intranasal/subcutaneous nootropic peptides in this catalog, e.g. Semax/Selank) -- verify actual composition and dosing against your product's label before use.",
        "schedule": [
            ("Week 1-2", 250.0, "mcg"),
            ("Week 3-4", 500.0, "mcg"),
        ],
        "sources": []
    },
    {
        "name": "Custom / Other",
        "vial_mg": 5.0,
        "water_ml": 2.0,
        "dose": 250.0,
        "unit": "mcg",
        "freq": "daily",
        "notes": "Enter custom values below to calculate dilution and syringe markings.",
        "schedule": [
            ("Week 1-4", 250.0, "mcg")
        ],
        "sources": []
    }
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table for profiles (people)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Table for master peptide templates
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS peptides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        vial_mg REAL,
        water_ml REAL,
        dose REAL,
        unit TEXT,
        freq TEXT,
        notes TEXT,
        schedule_json TEXT,
        sources_json TEXT
    )
    """)

    # Table for user/patient tracked protocols
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_protocols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        peptide_name TEXT NOT NULL,
        vial_mg REAL NOT NULL,
        water_ml REAL NOT NULL,
        target_dose REAL NOT NULL,
        dose_unit TEXT NOT NULL,
        frequency TEXT,
        notes TEXT,
        schedule_json TEXT,
        sources_json TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )
    """)

    # created_at wasn't in the original schema; ALTER TABLE ADD COLUMN isn't
    # idempotent, so guard it with a table_info check before adding it.
    existing_columns = {row["name"] for row in cursor.execute("PRAGMA table_info(user_protocols)")}
    if "created_at" not in existing_columns:
        cursor.execute("ALTER TABLE user_protocols ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    # When the current vial was reconstituted -- drives beyond-use-date (BUD)
    # warnings and "doses left in this vial" inventory. NULL = not reconstituted.
    if "reconstituted_at" not in existing_columns:
        cursor.execute("ALTER TABLE user_protocols ADD COLUMN reconstituted_at TIMESTAMP")

    # Table for logged dose-taken events (the actual adherence history, as
    # opposed to user_protocols which only tracks the planned protocol)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dose_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        protocol_id INTEGER,
        peptide_name TEXT NOT NULL,
        dose_amount REAL NOT NULL,
        dose_unit TEXT NOT NULL,
        taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )
    """)

    # Table for literature tracking / PubMed article cache
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tracked_literature (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pmid TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        authors_json TEXT,
        abstract TEXT,
        journal TEXT,
        pub_date TEXT,
        url TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tracked_literature_pmid ON tracked_literature(pmid)")

    # Optional peptide association, so articles tracked from the Reference tab
    # can be filtered back to the peptide they were cited for.
    lit_columns = {row["name"] for row in cursor.execute("PRAGMA table_info(tracked_literature)")}
    if "peptide_name" not in lit_columns:
        cursor.execute("ALTER TABLE tracked_literature ADD COLUMN peptide_name TEXT")

    # Populate default profile if none exist
    cursor.execute("SELECT COUNT(*) as count FROM profiles")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("INSERT INTO profiles (name, notes) VALUES ('Default User', 'Main user profile')")

    # One-time rename migration: "Tesemorelin" was a misspelling of "Tesamorelin".
    # Rewrite both the master template and any already-saved patient protocols
    # so existing users don't get silently orphaned by the corrected name.
    cursor.execute("UPDATE peptides SET name = 'Tesamorelin' WHERE name = 'Tesemorelin'")
    cursor.execute("UPDATE user_protocols SET peptide_name = 'Tesamorelin' WHERE peptide_name = 'Tesemorelin'")

    # Migration: Selank and Semax updated from intranasal sprays to
    # subcutaneous (SubQ) injection protocols for both catalog templates and
    # existing patient protocols.
    for p in DEFAULT_PEPTIDES:
        if p["name"] in ("Selank", "Semax"):
            cursor.execute("""
            UPDATE peptides
            SET freq = ?, notes = ?, schedule_json = ?, sources_json = ?
            WHERE name = ? AND (freq LIKE '%intranasal%' OR notes LIKE '%intranasal%')
            """, (
                p["freq"],
                p["notes"],
                json.dumps(p["schedule"]),
                json.dumps(p["sources"]),
                p["name"]
            ))
            cursor.execute("""
            UPDATE user_protocols
            SET frequency = ?, notes = ?, schedule_json = ?, sources_json = ?
            WHERE peptide_name = ? AND (frequency LIKE '%intranasal%' OR notes LIKE '%intranasal%')
            """, (
                p["freq"],
                p["notes"],
                json.dumps(p["schedule"]),
                json.dumps(p["sources"]),
                p["name"]
            ))

    # Populate default master peptides
    for p in DEFAULT_PEPTIDES:
        cursor.execute("""
        INSERT OR IGNORE INTO peptides (name, vial_mg, water_ml, dose, unit, freq, notes, schedule_json, sources_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["name"],
            p["vial_mg"],
            p["water_ml"],
            p["dose"],
            p["unit"],
            p["freq"],
            p["notes"],
            json.dumps(p["schedule"]),
            json.dumps(p["sources"])
        ))

    conn.commit()
    conn.close()


# Profile Management Functions
def get_profiles():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_profile(name, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO profiles (name, notes) VALUES (?, ?)", (name, notes))
        conn.commit()
        profile_id = cursor.lastrowid
        conn.close()
        return profile_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def delete_profile(profile_id):
    """Delete a profile and (via FK cascade) its protocols and dose log.

    Refuses to delete the last remaining profile so the app always has at
    least one valid profile to fall back to. Returns False if refused.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM profiles")
    if cursor.fetchone()["count"] <= 1:
        conn.close()
        return False
    cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    conn.commit()
    conn.close()
    return True


# Master Peptide Functions
def get_peptides():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM peptides ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d["schedule"] = json.loads(d["schedule_json"]) if d["schedule_json"] else []
        d["sources"] = json.loads(d["sources_json"]) if d["sources_json"] else []
        result.append(d)
    return result


def get_peptide_by_name(name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM peptides WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["schedule"] = json.loads(d["schedule_json"]) if d["schedule_json"] else []
        d["sources"] = json.loads(d["sources_json"]) if d["sources_json"] else []
        return d
    return None


# Patient Protocol Functions
def get_user_protocols(profile_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_protocols WHERE profile_id = ? ORDER BY updated_at DESC", (profile_id,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d["schedule"] = json.loads(d["schedule_json"]) if d["schedule_json"] else []
        d["sources"] = json.loads(d["sources_json"]) if d["sources_json"] else []
        result.append(d)
    return result


def get_user_protocol_by_id(protocol_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_protocols WHERE id = ?", (protocol_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["schedule"] = json.loads(d["schedule_json"]) if d["schedule_json"] else []
        d["sources"] = json.loads(d["sources_json"]) if d["sources_json"] else []
        return d
    return None


def add_or_update_user_protocol(profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit, frequency, notes, schedule, sources):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if this peptide already exists for the profile
    cursor.execute("SELECT id FROM user_protocols WHERE profile_id = ? AND peptide_name = ?", (profile_id, peptide_name))
    existing = cursor.fetchone()
    
    schedule_json = json.dumps(schedule)
    sources_json = json.dumps(sources)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if existing:
        cursor.execute("""
        UPDATE user_protocols 
        SET vial_mg = ?, water_ml = ?, target_dose = ?, dose_unit = ?, frequency = ?, notes = ?, schedule_json = ?, sources_json = ?, updated_at = ?
        WHERE id = ?
        """, (vial_mg, water_ml, target_dose, dose_unit, frequency, notes, schedule_json, sources_json, now, existing["id"]))
    else:
        cursor.execute("""
        INSERT INTO user_protocols (profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit, frequency, notes, schedule_json, sources_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit, frequency, notes, schedule_json, sources_json, now))
        
    conn.commit()
    conn.close()


def delete_user_protocol(protocol_id):
    conn = get_connection()
    cursor = conn.cursor()
    # dose_log rows deliberately outlive their protocol (peptide_name is
    # denormalized for exactly this reason), but protocol_id has no cascading FK,
    # so null it rather than leaving it pointing at a row that no longer exists.
    cursor.execute("UPDATE dose_log SET protocol_id = NULL WHERE protocol_id = ?", (protocol_id,))
    cursor.execute("DELETE FROM user_protocols WHERE id = ?", (protocol_id,))
    conn.commit()
    conn.close()


def set_protocol_reconstituted(protocol_id, when=None):
    """Mark a protocol's vial as reconstituted now (or at `when`), starting a
    fresh beyond-use-date window and resetting the vial's dose inventory.
    Pass when=False to clear the date (vial not reconstituted)."""
    conn = get_connection()
    cursor = conn.cursor()
    if when is False:
        value = None
    else:
        value = when or datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE user_protocols SET reconstituted_at = ? WHERE id = ?", (value, protocol_id))
    conn.commit()
    conn.close()
    return value


def update_protocol_schedule(protocol_id, schedule, target_dose, dose_unit):
    """Overwrite a protocol's titration schedule (e.g. from the Titration
    Schedule Generator), also syncing target_dose/dose_unit to the new
    maintenance level so dose logging/adherence reflect the updated plan."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
    UPDATE user_protocols
    SET schedule_json = ?, target_dose = ?, dose_unit = ?, updated_at = ?
    WHERE id = ?
    """, (json.dumps(schedule), target_dose, dose_unit, now, protocol_id))
    conn.commit()
    conn.close()


# Dose Log Functions
def log_dose(profile_id, protocol_id, peptide_name, dose_amount, dose_unit, notes="", taken_at=None):
    """Record a dose. `taken_at` ("YYYY-MM-DD HH:MM:SS", naive UTC) backdates a
    dose that was taken earlier but logged late; None means "right now"."""
    conn = get_connection()
    cursor = conn.cursor()
    if taken_at:
        cursor.execute("""
        INSERT INTO dose_log (profile_id, protocol_id, peptide_name, dose_amount, dose_unit, notes, taken_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (profile_id, protocol_id, peptide_name, dose_amount, dose_unit, notes, taken_at))
    else:
        cursor.execute("""
        INSERT INTO dose_log (profile_id, protocol_id, peptide_name, dose_amount, dose_unit, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (profile_id, protocol_id, peptide_name, dose_amount, dose_unit, notes))
    conn.commit()
    conn.close()


def get_dose_log_entry_by_id(log_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dose_log WHERE id = ?", (log_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_dose_log_entry(log_id, dose_amount, dose_unit, taken_at, notes=""):
    """Correct an already-logged dose (wrong amount, wrong date, missing note)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE dose_log
    SET dose_amount = ?, dose_unit = ?, taken_at = ?, notes = ?
    WHERE id = ?
    """, (dose_amount, dose_unit, taken_at, notes, log_id))
    conn.commit()
    conn.close()


def get_dose_log(profile_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dose_log WHERE profile_id = ? ORDER BY taken_at DESC", (profile_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_dose_log_entry(log_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dose_log WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()


def get_protocol_adherence(profile_id):
    """Compute a best-effort adherence percentage per protocol for a profile.

    Adherence is a heuristic: it parses the protocol's free-text frequency
    (e.g. "3x weekly") into an expected weekly dose count via
    calc.parse_weekly_frequency, and compares it to how many dose_log
    entries exist since the protocol was created. Unparseable frequencies
    or brand-new protocols report adherence_pct=None ("not measurable")
    rather than guessing.

    Also computes next_due_at (a datetime, or None if unmeasurable) from
    the same weekly-expected figure, anchored off the most recent logged
    dose (or the protocol's created_at if none has been logged yet).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, peptide_name, frequency, created_at, reconstituted_at, vial_mg, target_dose, dose_unit "
        "FROM user_protocols WHERE profile_id = ? ORDER BY peptide_name ASC",
        (profile_id,)
    )
    protocols = cursor.fetchall()

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive, to match SQLite's UTC CURRENT_TIMESTAMP strings
    result = []
    for p in protocols:
        cursor.execute(
            "SELECT COUNT(*) as count, MAX(taken_at) as last_taken FROM dose_log WHERE protocol_id = ?",
            (p["id"],)
        )
        log_row = cursor.fetchone()
        logged_count = log_row["count"]

        created_dt = None
        if p["created_at"]:
            try:
                created_dt = datetime.strptime(p["created_at"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                created_dt = None

        days_elapsed = 0.0
        if created_dt:
            days_elapsed = max(0.0, (now - created_dt).total_seconds() / 86400.0)

        last_taken_dt = None
        if log_row["last_taken"]:
            try:
                last_taken_dt = datetime.strptime(log_row["last_taken"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                last_taken_dt = None

        weekly_expected = calc.parse_weekly_frequency(p["frequency"] or "")
        adherence_pct = calc.adherence_percent(logged_count, weekly_expected, days_elapsed)
        next_due_at = calc.next_dose_due_at(weekly_expected, last_taken_dt, created_dt)

        reconstituted_dt = None
        if p["reconstituted_at"]:
            try:
                reconstituted_dt = datetime.strptime(p["reconstituted_at"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                reconstituted_dt = None

        # Vial inventory counts only doses drawn from the *current* vial, so it
        # resets whenever the protocol is marked reconstituted again.
        if reconstituted_dt:
            cursor.execute(
                "SELECT COUNT(*) as count FROM dose_log WHERE protocol_id = ? AND taken_at >= ?",
                (p["id"], p["reconstituted_at"])
            )
            doses_used = cursor.fetchone()["count"]
        else:
            doses_used = logged_count

        dose_mg = calc.dose_to_mg(p["target_dose"], p["dose_unit"])
        total_doses = calc.doses_per_vial(p["vial_mg"], dose_mg)

        result.append({
            "protocol_id": p["id"],
            "peptide_name": p["peptide_name"],
            "frequency": p["frequency"],
            "logged_count": logged_count,
            "adherence_pct": adherence_pct,
            "adherence_label": calc.adherence_label(adherence_pct, weekly_expected, days_elapsed),
            "next_due_at": next_due_at,
            "reconstituted_at": reconstituted_dt,
            "bud_expiry_at": calc.bud_expiry_at(reconstituted_dt),
            "bud_exceeded": calc.bud_exceeded_by_duration(total_doses, weekly_expected),
            "doses_used": doses_used,
            "doses_total": total_doses,
            "doses_remaining": calc.doses_remaining(total_doses, doses_used),
        })

    conn.close()
    return result


def export_person_reference_sheet(profile_id, dest_dir=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM profiles WHERE id = ?", (profile_id,))
    prof = cursor.fetchone()
    if not prof:
        conn.close()
        return None
    profile_name = prof["name"]
    
    protocols = get_user_protocols(profile_id)
    conn.close()
    
    filename = f"patient_{calc.safe_filename_part(profile_name)}_peptides_summary.txt"
    filepath = os.path.join(dest_dir or os.getcwd(), filename)
    
    with open(filepath, "w") as f:
        f.write("=" * 72 + "\n")
        f.write(f" PATIENT PEPTIDE PROTOCOL REFERENCE SHEET: {profile_name.upper()}\n")
        f.write("=" * 72 + "\n")
        f.write(f"Date Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Tracked Peptides: {len(protocols)}\n")
        f.write("=" * 72 + "\n\n")
        
        if not protocols:
            f.write("No active peptide protocols assigned for this person.\n")
        else:
            for i, p in enumerate(protocols, 1):
                f.write(f"[{i}] PEPTIDE: {p['peptide_name'].upper()}\n")
                f.write("-" * 50 + "\n")
                conc_mg_ml = calc.concentration_mg_ml(p['vial_mg'], p['water_ml'])
                conc_mcg_ml = conc_mg_ml * 1000.0
                dose_mg = calc.dose_to_mg(p['target_dose'], p['dose_unit'])
                vol_ml = calc.draw_volume_ml(dose_mg, conc_mg_ml)
                units = calc.syringe_units(vol_ml)
                
                f.write(f"• Vial Size:           {p['vial_mg']:.1f} mg\n")
                f.write(f"• BAC Water Added:     {p['water_ml']:.1f} mL\n")
                f.write(f"• Solution Strength:   {conc_mg_ml:.2f} mg/mL ({conc_mcg_ml:,.0f} mcg/mL)\n")
                f.write(f"• Prescribed Dose:     {p['target_dose']} {p['dose_unit']} ({p['frequency']})\n")
                f.write(f"• U-100 Syringe Draw:  {units:.1f} Units ({vol_ml:.3f} mL)\n")
                f.write(f"• Clinical Notes:      {p['notes']}\n")
                
                if p['schedule']:
                    f.write("\n  Titration Schedule:\n")
                    phase_width = max(20, max((len(phase) for phase, _, _ in p['schedule']), default=20))
                    header = f"  {'Phase':<{phase_width}} | {'Dose':<10} | {'Syringe Draw':<15}"
                    f.write(header + "\n")
                    f.write("  " + "-" * (len(header) - 2) + "\n")
                    for phase, d_val, u_unit in p['schedule']:
                        d_mg = calc.dose_to_mg(d_val, u_unit)
                        v_ml = calc.draw_volume_ml(d_mg, conc_mg_ml)
                        u_draw = calc.syringe_units(v_ml)
                        d_str = f"{d_val:.0f} mcg" if u_unit == 'mcg' else f"{d_val:.2f} mg"
                        f.write(f"  {phase:<{phase_width}} | {d_str:<10} | {u_draw:.1f} Units\n")
                        
                if p['sources']:
                    f.write("\n  Scientific Citations & Literature:\n")
                    for s in p['sources']:
                        f.write(f"  - {s['title']} (PMID: {s['pmid']})\n")
                        f.write(f"    URL: {s['url']}\n")
                        
                f.write("\n" + "=" * 72 + "\n\n")

        dose_log = get_dose_log(profile_id)[:10]
        if dose_log:
            f.write("RECENT DOSE LOG (Last 10 Entries)\n")
            f.write("-" * 72 + "\n")
            for entry in dose_log:
                notes_suffix = f" — {entry['notes']}" if entry['notes'] else ""
                f.write(f"  {entry['taken_at']}  {entry['peptide_name']}: {entry['dose_amount']} {entry['dose_unit']}{notes_suffix}\n")
            f.write("\n" + "=" * 72 + "\n")

    return filename


def export_dose_log_csv(profile_id, dest_dir=None):
    """Export a profile's full dose log to a CSV file in dest_dir (default:
    cwd). Returns the filename, or None if the profile doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM profiles WHERE id = ?", (profile_id,))
    prof = cursor.fetchone()
    conn.close()
    if not prof:
        return None
    profile_name = prof["name"]

    dose_log = get_dose_log(profile_id)

    filename = f"dose_log_{calc.safe_filename_part(profile_name)}.csv"
    filepath = os.path.join(dest_dir or os.getcwd(), filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Peptide", "Dose Amount", "Dose Unit", "Taken At", "Notes"])
        for entry in dose_log:
            writer.writerow([
                entry["id"],
                entry["peptide_name"],
                entry["dose_amount"],
                entry["dose_unit"],
                entry["taken_at"],
                entry["notes"] or "",
            ])

    return filename


# Tracked Literature Functions
def save_tracked_article(
    pmid: str,
    title: str,
    authors: list[str] | str,
    abstract: str,
    journal: str = "",
    pub_date: str = "",
    url: str = "",
    notes: str = "",
    peptide_name: str = "",
) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    if isinstance(authors, list):
        authors_json = json.dumps(authors)
    elif isinstance(authors, str):
        authors_json = json.dumps([a.strip() for a in authors.split(",") if a.strip()])
    else:
        authors_json = json.dumps([])

    clean_pmid = str(pmid).strip()
    if not url:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{clean_pmid}/"

    cursor.execute("""
    INSERT INTO tracked_literature (pmid, title, authors_json, abstract, journal, pub_date, url, notes, peptide_name)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(pmid) DO UPDATE SET
        title = excluded.title,
        authors_json = excluded.authors_json,
        abstract = excluded.abstract,
        journal = excluded.journal,
        pub_date = excluded.pub_date,
        url = excluded.url,
        notes = COALESCE(excluded.notes, tracked_literature.notes),
        peptide_name = COALESCE(NULLIF(excluded.peptide_name, ''), tracked_literature.peptide_name)
    """, (clean_pmid, title, authors_json, abstract, journal, pub_date, url, notes, peptide_name))
    conn.commit()

    cursor.execute("SELECT * FROM tracked_literature WHERE pmid = ?", (clean_pmid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["authors"] = json.loads(d["authors_json"]) if d["authors_json"] else []
        return d
    return {}


def get_tracked_literature(peptide_name: str | None = None) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if peptide_name:
        cursor.execute(
            "SELECT * FROM tracked_literature WHERE peptide_name = ? ORDER BY id DESC",
            (peptide_name,)
        )
    else:
        cursor.execute("SELECT * FROM tracked_literature ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["authors"] = json.loads(d["authors_json"]) if d["authors_json"] else []
        result.append(d)
    return result


def get_tracked_article_by_pmid(pmid: str | int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    clean_pmid = str(pmid).strip()
    cursor.execute("SELECT * FROM tracked_literature WHERE pmid = ?", (clean_pmid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["authors"] = json.loads(d["authors_json"]) if d["authors_json"] else []
        return d
    return None


def delete_tracked_article(article_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracked_literature WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()


def clear_tracked_literature() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracked_literature")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
