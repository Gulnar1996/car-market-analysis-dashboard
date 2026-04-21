#mercedes_scrape.py
"""
Mercedes-Benz Azerbaijan - /models/ scraper (model, price, colors)
Run:  python mercedes_scraper_v2.py
Output: mercedes_models_all.csv  (UTF-8-SIG)
"""

import re
import sys
import time
import math
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE = "https://www.mercedes-benz.com.az"
MODELS_INDEX = f"{BASE}/models/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = 25
SLEEP = 0.8  

AZN_RE = re.compile(r"([\d\s]+)\s*AZN", re.I)
COLOR_HINT_RE = re.compile(
    r"(white|black|silver|blue|red|grey|gray|beige|green|"
    r"polar|obsidian|sodalite|sapphire|graphite|emerald|denim|iridium|"
    r"mojave|high[-\s]?tech|nautic|mountain|verdes?|manufaktur|magno|metallic)",
    re.I
)

def get(url: str) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp

def clean_text(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "")).strip()

def parse_price_block(text: str):
    """
    'Başlayaraq 77 000 AZN ƏDV daxil' -> (77000, 'AZN')
    """
    if not text:
        return None, None
    m = AZN_RE.search(text)
    if not m:
        return None, None
    amount = int(m.group(1).replace(" ", ""))
    return amount, "AZN"

def guess_body_from_url(url: str) -> str | None:
    u = url.lower()
    if "hatchback" in u:
        return "Hatchback"
    if "sedan" in u:
        return "Sedan"
    if "cabriolet" in u or "roadster" in u:
        return "Kabriolet"
    if "coupe" in u or "coup" in u:
        return "Coupé"
    if "v-class" in u:
        return "MPV"
    if "suv" in u or any(k in u for k in ["gla", "glb", "glc", "gle", "gls", "g-class", "eqs-suv", "eqe-suv"]):
        return "SUV"
    return None



def extract_model(soup: BeautifulSoup) -> str | None:
    """
    Mercedes AZ saytında model adı tez-tez:
      <div class="jump module model-name ...">
        <span class="strapline"><span>EQE SUV</span></span>
      </div>
    """
    
    model_div = soup.find("div", class_=re.compile(r"\bmodel-name\b"))
    if model_div:
        strap = model_div.find("span", class_=re.compile(r"\bstrapline\b"))
        if strap:
            t = clean_text(strap.get_text(" ", strip=True))
            if t:
                return t

    
    for tag in ("h1", "h2"):
        el = soup.find(tag)
        if el:
            t = clean_text(el.get_text(" ", strip=True))
            t = re.sub(r"^\s*Model\s+", "", t, flags=re.I)  # "Model A-Class ..." -> "A-Class ..."
            if t:
                return t

    
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        t = clean_text(meta["content"])
        t = re.sub(r"^\s*Model\s+", "", t, flags=re.I)
        return t or None

    return None

def extract_price(soup: BeautifulSoup) -> tuple[int | None, str | None]:
    
    texts = set()
    for el in soup.find_all(string=re.compile(r"AZN", re.I)):
        t = clean_text(str(el))
        if t:
            texts.add(t)
        p = getattr(el, "parent", None)
        if p:
            pt = clean_text(p.get_text(" ", strip=True))
            if pt:
                texts.add(pt)

    
    for sel in ["[class*=price]", "[class*=amount]", ".price", ".amount"]:
        for el in soup.select(sel):
            texts.add(clean_text(el.get_text(" ", strip=True)))

    for t in texts:
        amt, cur = parse_price_block(t)
        if amt and cur:
            return amt, cur
    return None, None

def extract_colors(soup: BeautifulSoup) -> list[str]:
    """
    Rəng adları tez-tez:
      - <button title="Polar White"> ... </button>
      - <button aria-label="Polar White"> ... </button>
      - <span>Polar White</span> (swatch caption)
    Yalnız rəngə bənzər qısa adları saxlayırıq.
    """
    hits = set()

    
    for btn in soup.find_all("button"):
        for attr in ("title", "aria-label", "data-colour", "data-color", "data-label"):
            v = btn.get(attr)
            if v and len(v) <= 40 and COLOR_HINT_RE.search(v):
                hits.add(clean_text(v))

    
    likely_containers = soup.find_all(attrs={"class": re.compile(r"color|colour|r[əe]ng|swatch|paint", re.I)})
    for c in likely_containers:
        for sp in c.select("span, label, div, li, p"):
            t = clean_text(sp.get_text(" ", strip=True))
            if not t or len(t) > 40:
                continue
            if COLOR_HINT_RE.search(t) and not re.search(r"AZN|Başlayaraq", t, re.I):
                hits.add(t)

    
    if not hits:
        for sp in soup.find_all("span"):
            t = clean_text(sp.get_text(" ", strip=True))
            if 2 <= len(t) <= 40 and COLOR_HINT_RE.search(t):
                hits.add(t)

    
    norm = {}
    for x in hits:
        y = re.sub(r"[-\s]+", " ", x, flags=re.I).strip()
        y = y.replace("  ", " ")
        norm[y.lower()] = x 
    return sorted(norm.values(), key=lambda s: (len(s), s.lower()))



def get_model_links(index_url: str) -> list[str]:
    """
    Collect all /models/... links from the models index page.
    """
    resp = get(index_url)
    soup = BeautifulSoup(resp.text, "lxml")

    links = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        full = urljoin(index_url, href)
        path = urlparse(full).path
        if not path:
            continue
        if not path.startswith("/models/"):
            continue
        if path.endswith("/#"):
            continue
        
        full = full.split("#")[0].split("?")[0]
        links.add(full)

    
    return sorted(links)

def scrape_model_page(url: str) -> dict:
    resp = get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    brand = "Mercedes-Benz"
    model = extract_model(soup)
    price, price_currency = extract_price(soup)
    colors = extract_colors(soup)

    row = {
        "brand": brand,
        "model": model,
        "Qiymət": price,
        "price_currency": price_currency,
        "Buraxılış ili": None,        
        "Satış şəhəri": "Bakı",       
        "Rəng": ", ".join(colors) if colors else None,
        "Mühərrik növü": None,
        "Ban növü": guess_body_from_url(url),
        "Sürətlər qutusu": None,
        "Ötürücü": None,
        "Yürüş": None,
        "model_url": url
    }
    return row

def main():
    print("Model linkləri yığılır...")
    links = get_model_links(MODELS_INDEX)
    print(f"Tapıldı: {len(links)} link")

    rows = []
    for i, link in enumerate(links, 1):
        try:
            print(f"[{i}/{len(links)}] {link}")
            rows.append(scrape_model_page(link))
            time.sleep(SLEEP)
        except Exception as e:
            print(f"Xəta ({link}): {e}", file=sys.stderr)
            rows.append({
                "brand": "Mercedes-Benz",
                "model": None,
                "Qiymət": None,
                "price_currency": None,
                "Buraxılış ili": None,
                "Satış şəhəri": None,
                "Rəng": None,
                "Mühərrik növü": None,
                "Ban növü": None,
                "Sürətlər qutusu": None,
                "Ötürücü": None,
                "Yürüş": None,
                "model_url": link,
                "error": str(e),
            })

    
    cols = [
        "brand","model","Qiymət","price_currency","Buraxılış ili","Satış şəhəri",
        "Rəng","Mühərrik növü","Ban növü","Sürətlər qutusu","Ötürücü","Yürüş","model_url","error"
    ]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]

    
    out = "mercedes_models_all.csv"
    df.drop(columns=["error"]).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nYazıldı: {out}")
    print(df.head())

if __name__ == "__main__":
    main()
