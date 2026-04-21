# -*- coding: utf-8 -*-
"""
Changan.az modellərini scrape edib Excel-ə yazır.
Sahələr: make, model, buraxilis_ili, muherrikin_tipi, muherrikin_hecmi,
        ban_tipi, at_gucu, suret_qutusu, oturuculuk, yurus, cityName, price, currency
Çıxış: changan_modeller_2025.xlsx
"""

import re
import time
import math
import pandas as pd
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE = "https://changan.az"
LIST_URL = urljoin(BASE, "/models/")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


KNOWN_MODELS = {
    "UNI-Z IDD", "UNI V IDD", "Q05", "Deepal S7", "Nevo A05", "Alsvin",
    "UNI-K IDD", "UNI-V", "UNI-K", "UNI-T",
    "CS 55 Plus", "CS 35 Plus", "HUNTER", "Eado Plus", "CS 95",
}

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().upper()

NORM_KNOWN = {norm(k): k for k in KNOWN_MODELS}

PRICE_RE = re.compile(r"(\d[\d\s]{2,9})\s*(?:₼|AZN)", re.I)

session = requests.Session()
session.headers.update({
    "User-Agent": UA,
    "Accept-Language": "az,en;q=0.8",
    "Connection": "keep-alive"
})

def get_soup(url, retries=2, sleep=1.0):
    for i in range(retries + 1):
        r = session.get(url, timeout=30)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        time.sleep(sleep * (i + 1))
    r.raise_for_status()

def extract_price_from_text(text: str):
    m = PRICE_RE.search(text or "")
    if not m:
        return ""
    return int(re.sub(r"\D", "", m.group(1)))

def price_near(anchor_tag):
    
    m = PRICE_RE.search(anchor_tag.get_text(" ", strip=True))
    if m:
        return int(re.sub(r"\D", "", m.group(1)))
    
    scope = []
    if anchor_tag.parent: scope.append(anchor_tag.parent)
    scope += list(anchor_tag.next_siblings) + list(anchor_tag.previous_siblings)
    for node in scope:
        if hasattr(node, "get_text"):
            m = PRICE_RE.search(node.get_text(" ", strip=True))
            if m:
                return int(re.sub(r"\D", "", m.group(1)))
    return ""

def get_listing_models():
    """Siyahı səhifəsindən şəkilə uyğun modelləri (ad, url, siyahı-qiyməti) çıxarır."""
    soup = get_soup(LIST_URL)
    cards = {}
    for a in soup.find_all("a", href=True):
        raw = a.get_text(" ", strip=True)
        if not raw:
            continue
        n = norm(raw)
        if n not in NORM_KNOWN:
            continue
        model_name = NORM_KNOWN[n]

        href = a["href"].strip()
        if href.startswith("/"):
            href = urljoin(BASE, href)
        
        if not href.startswith(BASE):
            continue
        
        href = href.split("#")[0].split("?")[0]

        price = price_near(a)
        
        if model_name not in cards:
            cards[model_name] = {"name": model_name, "url": href, "price": price}
        else:
            
            if not cards[model_name]["price"] and price:
                cards[model_name]["price"] = price

    
    if len(cards) < len(KNOWN_MODELS):
        text_blob = soup.get_text("\n", strip=True)
        for km in KNOWN_MODELS:
            if km in cards:
                continue
            if km in text_blob:
                a = soup.find("a", string=lambda s: s and km in s)
                if a:
                    href = a.get("href", "")
                    if href.startswith("/"):
                        href = urljoin(BASE, href)
                    cards[km] = {"name": km, "url": href, "price": price_near(a)}

    return list(cards.values())

def text_after_heading(soup, keys):
    def is_heading(tag):
        if tag.name not in ("h2","h3","h4","strong"):
            return False
        t = tag.get_text(" ", strip=True).lower()
        return any(k in t for k in keys)
    hdr = soup.find(is_heading)
    if not hdr:
        return ""
    nxt = hdr.find_next(lambda t: t.name in ("p","div","span","li"))
    return nxt.get_text(" ", strip=True) if nxt else ""

def find_anywhere(soup, pat):
    t = soup.get_text(" ", strip=True)
    m = re.search(pat, t, flags=re.I)
    return m.group(1).strip() if m else ""

def split_engine(engine_raw):
    """'1.5 L Plug-in Hibrid' → ('1.5 L', 'Plug-in Hibrid')"""
    if not engine_raw:
        return "", ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(l|lt|litr)", engine_raw, re.I)
    hecmi = m.group(1) + " L" if m else ""
    tipi = engine_raw[m.end():].strip(" -–:,") if m else engine_raw.strip()
    return hecmi, tipi

def guess_body_type(page_text):
    t = page_text.lower()
    if "sedan" in t:
        return "sedan"
    if any(k in t for k in ("suv", "krossover", "crossover")):
        return "SUV"
    if any(k in t for k in ("pikap", "pickup")):
        return "pikap"
    if any(k in t for k in ("hatchback", "hetçbek", "hetcbek")):
        return "hetçbek"
    return ""

def parse_model_page(url):
    soup = get_soup(url)
    page_text = soup.get_text(" ", strip=True)

    
    h1 = soup.find("h1")
    model_title = h1.get_text(" ", strip=True) if h1 else ""

    engine_raw = text_after_heading(soup, ["mühərrik"])
    if not engine_raw:
        engine_raw = find_anywhere(soup, r"Mühərrik\s*[:\-]\s*([^\n•]+)")

    hp_raw = text_after_heading(soup, ["at gücü", "gücü"])
    if not hp_raw:
        hp_raw = find_anywhere(soup, r"At gücü\s*[:\-]\s*([^\n•]+)")

    gb_raw = text_after_heading(soup, ["sürətlər qutusu", "transmissiya", "qutu"])
    if not gb_raw:
        gb_raw = find_anywhere(soup, r"Sürətlər qutusu\s*[:\-]\s*([^\n•]+)")

    
    at_gucu = ""
    m = re.search(r"\b(\d{2,4})\b", hp_raw or "")
    if m:
        at_gucu = m.group(1)

    
    hecmi, tipi = split_engine(engine_raw)

    
    ban = guess_body_type(page_text)

    
    price_candidates = [int(re.sub(r"\D", "", m.group(1)))
                        for m in re.finditer(PRICE_RE, page_text)]
    extra_price = min(price_candidates) if price_candidates else ""

    return {
        "model_title": model_title,
        "muherrikin_tipi": tipi,
        "muherrikin_hecmi": hecmi,
        "ban_tipi": ban,
        "at_gucu": at_gucu,
        "suret_qutusu": gb_raw,
        "extra_price": extra_price,
    }

def main():
    listing = get_listing_models()
    if not listing:
        print("Siyahıdan model tapılmadı. /models/ strukturunu yoxlayın.")
        return

    rows = []
    for i, item in enumerate(listing, 1):
        url = item["url"]
        name = item["name"]
        print(f"[{i}/{len(listing)}] {name} -> {url}")
        try:
            details = parse_model_page(url)
            price = item["price"] or details["extra_price"] or ""
            rows.append({
                "make": "Changan",
                "model": name,                               
                "buraxilis_ili": "",                         
                "muherrikin_tipi": details["muherrikin_tipi"],
                "muherrikin_hecmi": details["muherrikin_hecmi"],
                "ban_tipi": details["ban_tipi"],
                "at_gucu": details["at_gucu"],
                "suret_qutusu": details["suret_qutusu"],
                "oturuculuk": "",                            
                "yurus": 0,                                  
                "cityName": "Bakı",
                "price": price,
                "currency": "AZN",
            })
            time.sleep(0.4)  
        except Exception as e:
            print(f"Xəta ({url}): {e}")

   
    df = pd.DataFrame(rows, columns=[
        "make","model","buraxilis_ili","muherrikin_tipi","muherrikin_hecmi",
        "ban_tipi","at_gucu","suret_qutusu","oturuculuk","yurus",
        "cityName","price","currency"
    ])

    out = "changan_modeller_2025.xlsx"
    df.to_excel(out, index=False)
    print(f"OK: {len(df)} sətir yazıldı → {out}")

if __name__ == "__main__":
    main()
