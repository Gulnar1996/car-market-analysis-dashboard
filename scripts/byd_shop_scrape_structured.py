# byd_woo_scraper.py
import re, time, unicodedata, json
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd
from difflib import get_close_matches

BASE = "https://bydmotorsbaku.az"
START_URL = f"{BASE}/shop/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

sess = requests.Session()
sess.headers.update({"User-Agent": UA})


CARD_SEL       = "div.product-grid-item, li.product"
TITLE_LINK_SEL = "h3.wd-entities-title a, h2.woocommerce-loop-product__title a, h3 a"
IMG_SEL        = "img"


def soup_get(url: str) -> BeautifulSoup:
    r = sess.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def next_page_url(soup: BeautifulSoup, base_url: str):
    link = soup.select_one('link[rel="next"]') or soup.select_one('a[rel="next"]')
    if link and link.get("href"):
        return urljoin(base_url, link["href"])
    pager = soup.select_one(".woocommerce-pagination .next, .pager__item--next a, .js-pager__items .pager__item--next a")
    if pager and pager.get("href"):
        return urljoin(base_url, pager["href"])
    return None

def pick_img_src(img):
    if not img: return None
    for attr in ("src","data-src","data-original","data-lazy-src"):
        if img.get(attr): return img[attr].split()[0]
    if img.get("srcset"):
        return img["srcset"].split(",")[0].strip().split(" ")[0]
    return None

def normalize_text(s: str) -> str:
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


LABEL_SYNONYMS = {
    "Price":       ["price","qiymet","qiymət","цена","стоимость","fiyat"],
    "Year":        ["year","il","buraxilis ili","buraxılış ili","model year","год"],
    "Engine Size": ["engine size","engine","engine capacity","engine displacement","muherrik hecmi","mühərrik həcmi","объем двигателя","двигатель","motor hacmi"],
    "Horsepower":  ["horsepower","power","engine power","guc","güc","ps","bhp","л.с.","лс"],
    "Distance":    ["distance","mileage","yurus","yürüş","kilometraj","пробег"],
    "Fuel Type":   ["fuel","fuel type","yanacaq","тип топлива","yakıt","yakıt türü"],
    "Transmission":["transmission","gearbox","suretler qutusu","sürətlər qutusu","şanzıman",
                    "korobka peredach","коробка передач","трансмиссия","kutu","vites","gear","transmisyon"],
}
NORM_LOOKUP = {}
for canon, alts in LABEL_SYNONYMS.items():
    for a in alts:
        NORM_LOOKUP[normalize_text(a)] = canon

def map_label_smart(label: str):
    lab = normalize_text(label)
    if lab in NORM_LOOKUP: return NORM_LOOKUP[lab]
    choices = list(NORM_LOOKUP.keys())
    m = get_close_matches(lab, choices, n=1, cutoff=0.8)
    return NORM_LOOKUP[m[0]] if m else None


def parse_price_currency(text):
    """Tam mətndən rəqəm + valyuta çıxar (məs: '79 900 ₼')."""
    if not text: return None, None
    t = normalize_space(text)
    cur = "AZN" if ("₼" in t or "AZN" in t.upper()) else \
          "USD" if ("$" in t or "USD" in t.upper()) else \
          "EUR" if ("€" in t or "EUR" in t.upper()) else None
    m = re.search(r"(\d[\d\s,\.]*)", t)
    price = None
    if m:
        num = re.sub(r"[,\s]", "", m.group(1))
        try: price = float(num)
        except: 
            try: price = int(num)
            except: pass
    return price, cur

def clean_engine_size(v):
    if not v: return None
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(l|lt|литр|litr|cc|см3|cm3)\b", v, re.I)
    if m: return f"{m.group(1).replace(',', '.')} {m.group(2).upper()}"
    return v.strip()

def clean_horsepower(v):
    if not v: return None
    hp = re.search(r"(\d+)\s*(hp|ps|bhp|л\.?с\.?)\b", v, re.I)
    if hp: return f"{hp.group(1)} HP"
    kw = re.search(r"(\d+(?:[\.,]\d+)?)\s*kW\b", v, re.I)
    if kw: return f"{kw.group(1).replace(',', '.')} kW"
    return v.strip()

def clean_distance(v):
    if not v: return None
    m = re.search(r"(\d[\d\s,\.]*)\s*(km|км|mi|mile|mil)\b", v, re.I)
    if m:
        num = re.sub(r"[,\s]", "", m.group(1))
        unit = m.group(2).lower()
        if unit == "км": unit = "km"
        return f"{num} {unit}"
    return v.strip()

def kv_from_tables(root):
    out = {}
    for tr in root.select("tr"):
        th = tr.select_one("th, td:first-child, strong, b")
        td = tr.select_one("td:last-child")
        if th and td:
            mapped = map_label_smart(th.get_text(" ", strip=True))
            val = td.get_text(" ", strip=True)
            if mapped and val:
                out[mapped] = val
    return out

def kv_from_text(root):
    out = {}
    text = root.get_text("\n", strip=True)
    for line in text.split("\n"):
        line = line.strip("•-–— ").replace("—", "-")
        if ":" in line:    k, v = line.split(":", 1)
        elif " - " in line: k, v = line.split(" - ", 1)
        elif " – " in line: k, v = line.split(" – ", 1)
        else: continue
        mapped = map_label_smart(k)
        if mapped and v.strip():
            out[mapped] = v.strip()
    return out

FUEL_WORDS = ["plug-in hybrid","hybrid","phev","benzin","gasoline","petrol","diesel","electric","elektrik","ev","hev","cng","lng","lpg","бензин","дизель","гибрид"]
TRANS_WORDS = ["automatic","auto","at","robotized","dct","cvt","variator","dual clutch",
               "manual","mt","tiptronic","semiautomatic","semi-automatic",
               "avtomat","avtomatik","mexaniki","robotlasdirilmis","robotlaşdırılmış",
               "otomatik","manuel","автомат","механика","робот","вариатор"]

def regex_fallback_from_text(text):
    out = {}
    t = normalize_text(text)
    
    m = re.search(r"(?:price|qiymet|qiymət|цена|стоимость)[^0-9]{0,10}(\d[\d\s,\.]+)\s*([₼$€]|azn|usd|eur)?", t, re.I)
    if m and "Price" not in out:
        p, c = parse_price_currency(m.group(0)); out["Price"], out["Currency"] = p, c
    
    y = re.search(r"\b(20[1-5]\d|19\d{2})\b", t)
    if y: out["Year"] = y.group(1)
    
    e = re.search(r"(\d+(?:[\.,]\d+)?)\s*(l|lt|cc|см3|cm3|litr)\b", t, re.I)
    if e: out["Engine Size"] = clean_engine_size(e.group(0))
    
    hp = re.search(r"\b(\d+)\s*(hp|ps|bhp|л\.?с\.?)\b", t, re.I)
    kw = re.search(r"\b(\d+(?:[\.,]\d+)?)\s*kW\b", t, re.I)
    if hp: out["Horsepower"] = clean_horsepower(hp.group(0))
    elif kw: out["Horsepower"] = clean_horsepower(kw.group(0))
    
    d = re.search(r"\b(\d[\d\s,\.]*)\s*(km|км|mi|mile|mil)\b", t, re.I)
    if d: out["Distance"] = clean_distance(d.group(0))
    
    m_tr = re.search(
        r"(transmission|suretler qutusu|sürətlər qutusu|şanzıman|korobka peredach|коробка передач|трансмиссия)\s*[:\-–]\s*([a-z0-9 \-]+)",
        t, re.I
    )
    if m_tr:
        val = m_tr.group(2).strip()
        for w in TRANS_WORDS:
            if re.search(rf"\b{re.escape(normalize_text(w))}\b", val):
                out["Transmission"] = (w.upper() if w in ["at","mt","dct","cvt"] else w.title())
                break
   
    if "Transmission" not in out:
        for w in TRANS_WORDS:
            if re.search(rf"\b{re.escape(normalize_text(w))}\b", t):
                out["Transmission"] = (w.upper() if w in ["at","mt","dct","cvt"] else w.title())
                break
    
    for w in FUEL_WORDS:
        if re.search(rf"\b{re.escape(normalize_text(w))}\b", t):
            out["Fuel Type"] = (w.title() if w not in ["phev","ev","hev"] else w.upper())
            break
    return out


def parse_numeric_amount(text):
    """'24.000', '39,800', '79 900' -> 24000.0, 39800.0, 79900.0"""
    if not text:
        return None
    t = text.replace("\xa0", " ").strip()
   
    t = re.sub(r"(?<=\d)[\.\s](?=\d{3}\b)", "", t)
    t = t.replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return float(m.group(1)) if m else None

def get_price_from_dom(soup):
    """
    WooCommerce DOM-dan qiyməti toplayır:
    - PriceText (göründüyü kimi)
    - PriceMin, PriceMax (range varsa)
    - Price (tək dəyər və ya min)
    - Currency
    """
    wrap = soup.select_one("p.price, .price")
    if not wrap:
        wrap = soup.select_one("span.woocommerce-Price-amount, span.price")
        if not wrap:
            return None

    price_text = normalize_space(wrap.get_text(" ", strip=True))
    amounts = [el.get_text(" ", strip=True) for el in wrap.select(".woocommerce-Price-amount")]
    
    currency = None
    cur_el = wrap.select_one(".woocommerce-Price-currencySymbol")
    if cur_el:
        sym = cur_el.get_text(strip=True)
        currency = "AZN" if sym == "₼" else "USD" if sym == "$" else "EUR" if sym == "€" else None

    price_min = price_max = price_single = None
    if len(amounts) >= 2:
        price_min = parse_numeric_amount(amounts[0])
        price_max = parse_numeric_amount(amounts[-1])
    elif len(amounts) == 1:
        price_single = parse_numeric_amount(amounts[0])

    out = {"PriceText": price_text}
    if currency: out["Currency"] = currency
    if price_min is not None: out["PriceMin"] = price_min
    if price_max is not None: out["PriceMax"] = price_max
    if price_single is not None:
        out["Price"] = price_single
    else:
       
        if price_min is not None:
            out["Price"] = price_min
    return out

def get_jsonld_price(soup):
    """schema.org Product JSON-LD daxilindəki price & currency."""
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            if obj.get("@type") in ("Product", "Offer", "AggregateOffer"):
                offer = obj.get("offers", obj)
                if isinstance(offer, list):
                    offer = offer[0]
                price = offer.get("price") or offer.get("lowPrice") or offer.get("highPrice")
                cur = offer.get("priceCurrency")
                if price:
                    try:
                        price_num = float(str(price).replace(",", "."))
                    except:
                        price_num = None
                    return price_num, cur
    return None, None


def parse_detail(detail_url):
    s = soup_get(detail_url)
    out = {}

   
    h1 = s.select_one("h1.product_title, h1.entry-title, h1")
    if h1: out["model"] = h1.get_text(strip=True)

   
    dom_price = get_price_from_dom(s)
    if dom_price:
        out.update(dom_price)

    if not out.get("Price"):
        p_json, c_json = get_jsonld_price(s)
        if p_json:
            out["Price"] = p_json
            if c_json and not out.get("Currency"):
                out["Currency"] = c_json

    
    og_title = s.select_one('meta[property="og:title"]')
    if og_title and og_title.get("content") and not out.get("model"):
        out["model"] = og_title["content"].split("|")[0].strip()

    brand_meta = s.select_one('meta[property="product:brand"], meta[property="og:site_name"]')
    if brand_meta and brand_meta.get("content"):
        out["brand"] = brand_meta["content"].strip()

    og_img = s.select_one('meta[property="og:image"]')
    if og_img and og_img.get("content"):
        out["image"] = urljoin(detail_url, og_img["content"])

    og_desc = s.select_one('meta[property="og:description"], meta[name="description"]')
    if og_desc and og_desc.get("content"):
        rx_meta = regex_fallback_from_text(og_desc["content"])
        for k, v in rx_meta.items():
            if k not in out or not out[k]:
                out[k] = v

    
    desc = s.select_one("#tab-description, .woocommerce-Tabs-panel--description") \
        or s.select_one(".woocommerce-product-details__short-description, .entry-summary")
    if desc:
        kv = {}
        kv.update(kv_from_tables(desc))
        kv.update(kv_from_text(desc))
        rx = regex_fallback_from_text(desc.get_text("\n", strip=True))
        for k, v in rx.items():
            if k not in kv or not kv[k]:
                kv[k] = v
        out.update(kv)

    
    page_text = s.get_text("\n", strip=True)
    rx_page = regex_fallback_from_text(page_text)
    for k, v in rx_page.items():
        if k not in out or not out[k]:
            out[k] = v

    
    if out.get("Engine Size"): out["Engine Size"] = clean_engine_size(out["Engine Size"])
    if out.get("Horsepower"):  out["Horsepower"]  = clean_horsepower(out["Horsepower"])
    if out.get("Distance"):    out["Distance"]    = clean_distance(out["Distance"])

    return out


def parse_listing(list_url):
    soup = soup_get(list_url)
    items = []
    for card in soup.select(CARD_SEL):
        a = card.select_one(TITLE_LINK_SEL)
        if not a or not a.get("href"): 
            continue
        title = a.get_text(strip=True)
        href = urljoin(list_url, a["href"])
        img_el = card.select_one(IMG_SEL)
        img = pick_img_src(img_el)
        img = urljoin(list_url, img) if img else None
        items.append({"brand":"BYD","model":title,"url":href,"image":img})
    nx = next_page_url(soup, list_url)
    return items, nx


def crawl(start_url=START_URL, delay=1.2, max_pages=100):
    rows, seen = [], set()
    url, page = start_url, 1
    while url and page <= max_pages:
        cards, nx = parse_listing(url)
        if not cards: break
        for c in cards:
            if c["url"] in seen: continue
            seen.add(c["url"])
            det = parse_detail(c["url"])
            rows.append({
                "brand": det.get("brand", "BYD"),
                "model": det.get("model", c["model"]),
                "PriceText": det.get("PriceText"),
                "Price": det.get("Price"),
                "PriceMin": det.get("PriceMin"),
                "PriceMax": det.get("PriceMax"),
                "Currency": det.get("Currency"),
                "Year": det.get("Year"),
                "Engine Size": det.get("Engine Size"),
                "Horsepower": det.get("Horsepower"),
                "Distance": det.get("Distance"),
                "Fuel Type": det.get("Fuel Type"),
                "Transmission": det.get("Transmission"),
                "url": c["url"],
                "image": det.get("image", c.get("image")),
            })
            time.sleep(delay)
        print(f"Page {page}: {len(cards)} items (total {len(rows)})")
        url, page = nx, page + 1
        time.sleep(delay)

    df = pd.DataFrame(rows)
    cols = ["brand","model","PriceText","Price","PriceMin","PriceMax","Currency","Year",
            "Engine Size","Horsepower","Distance","Fuel Type","Transmission","url","image"]
    for col in cols:
        if col not in df.columns: df[col] = None
    df = df[cols].drop_duplicates(subset=["url"])
    df.to_csv("byd_models.csv", index=False)
    print(f"✅ Yadda saxlandı: byd_models.csv — {len(df)} sətir")
    return df

if __name__ == "__main__":
    crawl()
