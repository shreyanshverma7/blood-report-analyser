import os
import requests
from bs4 import BeautifulSoup

SOURCES = [
    ("https://medlineplus.gov/lab-tests/complete-blood-count/", "cbc_overview.txt"),
    ("https://medlineplus.gov/lab-tests/hemoglobin-test/", "hemoglobin.txt"),
    ("https://medlineplus.gov/lab-tests/platelet-tests/", "platelets.txt"),
    ("https://medlineplus.gov/lab-tests/comprehensive-metabolic-panel/", "metabolic_panel.txt"),
    ("https://medlineplus.gov/lab-tests/liver-function-tests/", "liver_function.txt"),
    ("https://medlineplus.gov/lab-tests/creatinine-test/", "creatinine.txt"),
    ("https://medlineplus.gov/lab-tests/calcium-blood-test/", "calcium.txt"),
    ("https://medlineplus.gov/lab-tests/cholesterol-levels/", "cholesterol.txt"),
    ("https://medlineplus.gov/lab-tests/thyroid-function-tests/", "thyroid.txt"),
    ("https://medlineplus.gov/lab-tests/vitamin-d-test/", "vitamin_d.txt"),
    ("https://medlineplus.gov/lab-tests/vitamin-b12-test/", "vitamin_b12.txt"),
    ("https://medlineplus.gov/lab-tests/alkaline-phosphatase/", "alp.txt"),
]

OUT_DIR = "src/kb/sources"
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; blood-report-kb-fetcher/1.0)"}

for url, filename in SOURCES:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # MedlinePlus puts article content in <div id="mplus-content"> or <main>
        content_div = soup.find("div", id="mplus-content") or soup.find("main") or soup.body
        text = content_div.get_text(separator="\n", strip=True)
        out_path = os.path.join(OUT_DIR, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✓ {filename}: {text[:100]!r}")
    except Exception as e:
        print(f"✗ {filename}: {e}")
