# turbo_full_scraper_with_price.py


import re
import time
import random
import json
from typing import List, Dict, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pandas as pd



BASE = "https://turbo.az"
LIST_URL = f"{BASE}/autos"

TOTAL_PAGES = 1817     
START_PAGE  = 1       
END_PAGE    = TOTAL_PAGES


PER_LINK_SLEEP   = (0.6, 1.1)  
PER_PAGE_SLEEP   = (0.8, 1.5)   

CHECKPOINT_EVERY = 1            

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "az,ru;q=0.9,en;q=0.8,tr;q=0.7",
    "Cache-Control": "no-cache",
}



S = requests.Session()
S.headers.update(HEADERS)

ID_RE = re.compile(r"/autos/(\d+)[-\w]*", re.I)


PRICE_MAIN_SEL = "div.product-price__i.product-price__i--bold"
PRICE_ANY_SEL  = "div.product-price__i"

def clean(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()

def parse_price(text: str) -> Tuple[str | None, int | None]:
    """
    '84 900 AZN' → ('84 900 AZN', 84900)
    '54.300 ₼'  → ('54.300 ₼', 54300)
    """
    if not text:
        return None, None
    txt = clean(text)
    digits = re.findall(r"\d+", txt)
    num = int("".join(digits)) if digits else None
    return txt, num

def extract_price_from_soup(soup: BeautifulSoup) -> Tuple[str | None, int | None]:
   
    el = soup.select_one(PRICE_MAIN_SEL)
    if el:
        return parse_price(el.get_text())

    
    el = soup.select_one(PRICE_ANY_SEL)
    if el:
        return parse_price(el.get_text())

    
    meta = soup.select_one("meta[itemprop='price']")
    cur  = soup.select_one("meta[itemprop='priceCurrency']")
    if meta and meta.get("content"):
        txt = f"{meta.get('content')} {cur.get('content') if cur else 'AZN'}"
        return parse_price(txt)

    
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = tag.string and tag.string.strip()
            if not data:
                continue
            obj = json.loads(data)
            objs = obj if isinstance(obj, list) else [obj]
            for o in objs:
                if isinstance(o, dict) and isinstance(o.get("offers"), dict):
                    pr = o["offers"].get("price")
                    cur_code = o["offers"].get("priceCurrency", "AZN")
                    if pr:
                        return parse_price(f"{pr} {cur_code}")
        except Exception:
            continue

    return None, None

def request_with_retry(url: str, max_try: int = 3, backoff_base: float = 2.0) -> requests.Response | None:
    """
    Sadə retry/backoff; 429/5xx üçün gözləyib yenidən cəhd edir.
    """
    for attempt in range(1, max_try + 1):
        try:
            r = S.get(url, timeout=30)
            if r.status_code == 200 and r.text:
                return r
            
            if r.status_code in (429, 503, 502, 500):
                wait = backoff_base ** attempt + random.random()
                print(f"      [retry] {r.status_code} → {wait:.1f}s gözlənilir")
                time.sleep(wait)
            else:
                
                time.sleep(1.0 + random.random())
        except requests.RequestException as e:
            wait = backoff_base ** attempt / 2 + random.random()
            print(f"      [retry] istisna: {e} → {wait:.1f}s")
            time.sleep(wait)
    return None

def page_url(page: int) -> str:
    return LIST_URL if page == 1 else f"{LIST_URL}?page={page}"

def get_page_links(page: int) -> List[str]:
    """
    Verilən səhifədən bütün /autos/... linklərini toplayır.
    """
    url = page_url(page)
    r = request_with_retry(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    links = []
    for a in soup.select("a.products-i__link[href^='/autos/']"):
        href = a.get("href")
        if href:
            links.append(urljoin(BASE, href))
    
    return list(dict.fromkeys(links))

def extract_listing(url: str) -> Dict[str, str | int]:
    """
    Tək elanın məlumatları:
      - Xüsusiyyətlərdən (label→value) alınan sahələr
      - Qiymət (mətn və rəqəm)
    """
    r = request_with_retry(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "lxml")
    m = ID_RE.search(url)
    lid = m.group(1) if m else None

    row: Dict[str, str | int] = {"id": lid, "url": url}

    
    for box in soup.select("div.product-properties__i"):
        k = box.select_one("label.product-properties__i-name")
        v = box.select_one("span.product-properties__i-value")
        if not (k and v):
            continue
        key = clean(k.get_text())
        val = clean(v.get_text())
        if key:
            row[key] = val

    
    price_txt, price_num = extract_price_from_soup(soup)
    if price_txt:
        row["Qiymət"] = price_txt
    if price_num is not None:
        row["Qiymət (AZN_num)"] = price_num

    return row

def save_excel(rows: List[Dict[str, str | int]], path: str):
    """
    Excel-ə yazır. Sütun sırası: əvvəl id/url, sonra tez-tez rast gəlinən sahələr,
    qalanları isə avtomatik əlavə olunur.
    """
    preferred = [
        "id", "url", "Qiymət", "Qiymət (AZN_num)",
        "Şəhər", "Marka", "Model", "Buraxılış ili",
        "Ban növü", "Rəng", "Mühərrik", "Yürüş", "Sürətlər qutusu",
        "Ötürücü", "Yeni", "Vəziyyəti", "Yerlərin sayı",
        "Hansı bazar üçün yığılıb"
    ]
    cols = list(dict.fromkeys(preferred + [k for r in rows for k in r.keys()]))

    df = pd.DataFrame(rows).reindex(columns=cols)
    with pd.ExcelWriter(path, engine="xlsxwriter") as w:
        df.to_excel(w, sheet_name="elanlar", index=False)

def crawl_all(start: int = START_PAGE, end: int = END_PAGE):
    print("[START] Turbo.az crawl başlayır...")
    results: List[Dict[str, str | int]] = []
    seen_ids = set()

    for page in range(start, end + 1):
        url = page_url(page)
        print(f"[PAGE {page}/{end}] {url}")

        links = get_page_links(page)
        print(f"  tapıldı: {len(links)} link")

        for j, link in enumerate(links, 1):
            m = ID_RE.search(link)
            lid = m.group(1) if m else None
            if lid and lid in seen_ids:
                print(f"    [{j}/{len(links)}] SKIP id={lid} (təkrar)")
                continue

            print(f"    [{j}/{len(links)}] id={lid} → yüklənir...", end="", flush=True)
            row = extract_listing(link)
            if row:
                results.append(row)
                if row.get("id"):
                    seen_ids.add(row["id"])
                print(" OK")
            else:
                print(" BOŞ/ERROR")

            time.sleep(random.uniform(*PER_LINK_SLEEP))

       
        if page % CHECKPOINT_EVERY == 0:
            try:
                save_excel(results, path="turbo_partial.xlsx")
                print(f"  [SAVE] {page}. səhifəyə qədər yazıldı → turbo_partial.xlsx")
            except Exception as e:
                print(f"  [WARN] Saxlama xətası: {e}")

        time.sleep(random.uniform(*PER_PAGE_SLEEP))

    save_excel(results, path="turbo_all_with_prices.xlsx")
    print(f"[DONE] Cəmi elan: {len(results)} → turbo_all_with_prices.xlsx")

if __name__ == "__main__":
    
    crawl_all()
