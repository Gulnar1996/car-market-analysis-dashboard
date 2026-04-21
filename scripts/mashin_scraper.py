
#mashin_al_scrape.py


import re
import time
import random
from urllib.parse import urljoin
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
import pandas as pd

BASE = "https://mashin.al"
LIST_URL = f"{BASE}/masinlar"
TOTAL_PAGES = 1484 
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "az,ru;q=0.9,en;q=0.8,tr;q=0.7",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def get_page_links(page: int) -> List[str]:
    """Bir səhifədəki elan linkləri"""
    url = f"{LIST_URL}?page={page}" if page > 1 else LIST_URL
    for _ in range(3):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                links = [
                    urljoin(BASE, a.get("href"))
                    for a in soup.select("a.abs-link[href^='/masinlar/elan/']")
                ]
                return list(dict.fromkeys(links))
        except Exception:
            time.sleep(2)
    return []


def extract_brand_model(soup: BeautifulSoup):
    spans = soup.select("h1.productInnerTitle span.productInnerTitle__item")
    texts = [clean(s.get_text()) for s in spans if clean(s.get_text())]
    brand = texts[0] if len(texts) > 0 else None
    model = texts[1] if len(texts) > 1 else None
    return brand, model


def extract_price(soup: BeautifulSoup):
    texts = []
    for sel in ["[class*='price']", "[class*='Price']", "span", "div"]:
        for n in soup.select(sel):
            txt = clean(n.get_text(" ", strip=True))
            if txt:
                texts.append(txt)
    m_re = re.compile(r"(\d[\d\s.,]*)\s*(AZN|USD|EUR)", re.I)
    for txt in texts:
        m = m_re.search(txt)
        if m:
            raw = f"{m.group(1).strip()} {m.group(2).upper()}"
            amt = int(re.sub(r"\D", "", m.group(1)))
            cur = m.group(2).upper()
            return raw, amt, cur
    return None, None, None


def extract_listing(url: str) -> Dict[str, str]:
    """Elan səhifəsindən məlumat çıxarır"""
    for _ in range(3):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(1)
    else:
        return {}

    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r"/elan/(\d+)", url)
    listing_id = m.group(1) if m else None

    row: Dict[str, str] = {"id": listing_id, "url": url}

    brand, model = extract_brand_model(soup)
    if brand: row["brand"] = brand
    if model: row["model"] = model

    for desc in soup.select(".vehicle-specs__list-description"):
        h6, h5 = desc.find("h6"), desc.find("h5")
        if h6 and h5:
            row[clean(h6.get_text())] = clean(h5.get_text())

    q_raw, q_amt, q_cur = extract_price(soup)
    if q_raw: row["Qiymət"] = q_raw
    if q_amt is not None: row["price_amount"] = q_amt
    if q_cur: row["price_currency"] = q_cur

    return row


def save_to_excel(rows: List[Dict[str, str]], file="mashin_all_pages.xlsx"):
    preferred = [
        "id", "url", "brand", "model", "Qiymət", "price_amount", "price_currency",
        "Buraxılış ili", "Satış şəhəri", "Rəng", "Mühərrik növü",
        "Ban növü", "Sürətlər qutusu", "Ötürücü", "Yürüş"
    ]
    all_cols = list(dict.fromkeys(preferred + [k for r in rows for k in r.keys()]))
    df = pd.DataFrame(rows).reindex(columns=all_cols)
    with pd.ExcelWriter(file, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="elanlar", index=False)


def main():
    all_data = []
    seen_ids = set()

    for page in range(1, TOTAL_PAGES + 1):
        print(f"[PAGE {page}] linklər yüklənir...")
        links = get_page_links(page)
        print(f"  tapıldı: {len(links)} link")

        for link in links:
            lid = re.search(r"/elan/(\d+)", link)
            lid = lid.group(1) if lid else None
            if lid in seen_ids:
                continue
            data = extract_listing(link)
            if data:
                all_data.append(data)
                seen_ids.add(data.get("id"))
            time.sleep(0.4 + random.random() * 0.4)

        
        if page % 5 == 0:
            save_to_excel(all_data, "mashin_partial.xlsx")
            print(f"  [✓] {page}. səhifəyə qədər qeyd edildi (mashin_partial.xlsx)")

        time.sleep(1.2 + random.random() * 0.8)

    save_to_excel(all_data, "mashin_all_pages.xlsx")
    print(f"\n[✓ BİTTİ] Cəmi {len(all_data)} elan → mashin_all_pages.xlsx faylında")


if __name__ == "__main__":
    main()
