#!/usr/bin/env python3
"""Charlotte County FL Solar Permit Scraper."""

import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://aca-prod.accela.com/BOCC/"
SEARCH_URL = BASE + "Cap/CapHome.aspx?module=Building&TabName=Building"

LICENSE_TYPES = [
    "C SOLAR ENERGY",
    "C SOLAR SYSTEM",
    "C SOLAR WAT HEAT",
]

LOOKBACK_DAYS = 365
HERE = Path(__file__).parent
OUTPUT_FILE = HERE / "permits.json"
CACHE_FILE = HERE / ".geocode_cache.json"
DEBUG_DIR = HERE / "debug_html"

UA = "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"

LOG_FMT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
log = logging.getLogger("scraper")

VS_KEYS = [
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
    "__VIEWSTATEENCRYPTED",
    "__EVENTTARGET",
    "__EVENTARGUMENT",
]

ADDR_TOKENS = [
    " RD", " ST", " AVE", " BLVD", " DR",
    " LN", " CT", " PKWY", " WAY", " TER",
    " CIR", " HWY", " TRL", " PL",
]

STATUS_WORDS = [
    "issued",
    "review",
    "submitted",
    "pending",
    "approved",
    "void",
    "expired",
    "finaled",
    "closed",
    "hold",
    "withdrawn",
    "incomplete",
    "ready",
]


def get_form_state(html):
    soup = BeautifulSoup(html, "html.parser")
    state = {}
    for name in VS_KEYS:
        el = soup.find("input", {"name": name})
        if el is not None:
            state[name] = el.get("value", "")
    return state


def find_input_near_label(soup, fragment):
    pattern = re.compile(fragment, re.I)
    for label in soup.find_all(string=pattern):
        parent = label.parent
        for _ in range(6):
            if parent is None:
                break
            ctrl = parent.find(["input", "select"])
            if ctrl is not None and ctrl.get("name"):
                return ctrl["name"]
            parent = parent.parent
    return None


def discover_fields(html):
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for sel in soup.find_all("select"):
        opts = [o.get_text(strip=True) for o in sel.find_all("option")]
        has_solar = False
        for o in opts:
            if "SOLAR ENERGY" in o:
                has_solar = True
                break
        if has_solar:
            fields["license_type"] = sel.get("name")
            log.info("DEBUG: license select: %s", sel.get("name"))
            break
    fields["start_date"] = find_input_near_label(soup, r"Start Date")
    fields["end_date"] = find_input_near_label(soup, r"End Date")
    log.info("DEBUG: fields: %s", fields)
    pat = r'PostBackOptions\("([^"]+)"'
    for btn in soup.find_all("a"):
        title = btn.get("title")
        href = btn.get("href") or ""
        if title == "Search" and "btnNewSearch" in href:
            m = re.search(pat, href)
            if m:
                fields["search_event"] = m.group(1)
                log.info("DEBUG: search btn: %s", m.group(1))
                break
    return fields


def save_html(html, label):
    DEBUG_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^a-z0-9_]+", "_", label.lower())
    safe = safe[:50]
    path = DEBUG_DIR / (safe + ".html")
    path.write_text(html)
    log.info("DEBUG: wrote %d bytes to %s", len(html), path)





def search_one(session, license_type, start, end):
    log.info("=" * 50)
    log.info("Search: %s", license_type)
    resp = session.get(SEARCH_URL, timeout=30)
    resp.raise_for_status()
    log.info(
        "DEBUG: GET form: %d, len=%d",
        resp.status_code,
        len(resp.text),
    )
    save_html(resp.text, "01_form_" + license_type)

    state = get_form_state(resp.text)
    log.info("DEBUG: vs keys: %s", list(state.keys()))
    fields = discover_fields(resp.text)

    if not fields.get("license_type"):
        log.error("No license type field.")
        return []

    default_btn = "ctl00$PlaceHolderMain$btnNewSearch"
    payload = {}
    payload["__EVENTTARGET"] = fields.get(
        "search_event", default_btn
    )
    payload["__EVENTARGUMENT"] = ""
    for k, v in state.items():
        payload[k] = v
    payload[fields["license_type"]] = license_type
    if fields.get("start_date"):
        payload[fields["start_date"]] = start
    if fields.get("end_date"):
        payload[fields["end_date"]] = end

    log.info("DEBUG: payload keys: %s", list(payload.keys()))

    time.sleep(1.5)
    resp = session.post(SEARCH_URL, data=payload, timeout=60)
    resp.raise_for_status()
    log.info(
        "DEBUG: POST: %d, len=%d, url=%s",
        resp.status_code,
        len(resp.text),
        resp.url,
    )
    save_html(resp.text, "02_results_" + license_type)

    soup = BeautifulSoup(resp.text, "html.parser")
    title = "no title"
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    log.info("DEBUG: page title: %s", title)

    msgs = []
    sel = "[class*='error'], [class*='Error'], [class*='Message']"
    for e in soup.select(sel):
        txt = e.get_text(strip=True)
        if txt and len(txt) < 300:
            msgs.append(txt)
    if msgs:
        log.info("DEBUG: messages: %s", msgs[:5])

    body = soup.get_text(" ", strip=True)
    log.info("DEBUG: body[:800]: %s", body[:800])

    heads = []
    for h in soup.select("h1, h2, h3"):
        txt = h.get_text(strip=True)
        if txt:
            heads.append(txt)
    log.info("DEBUG: headings: %s", heads[:10])

    permits = []
    page = 1
    while True:
        rows, has_next, next_t = parse_page(resp.text)
        log.info("Page %d: %d permits", page, len(rows))
        permits.extend(rows)
        if not has_next:
            break
        time.sleep(2)
        state = get_form_state(resp.text)
        payload = {}
        payload["__EVENTTARGET"] = next_t
        payload["__EVENTARGUMENT"] = ""
        for k, v in state.items():
            payload[k] = v
        resp = session.post(
            SEARCH_URL, data=payload, timeout=60
        )
        resp.raise_for_status()
        page += 1
        if page > 50:
            break
    return permits


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    permits = []

    rows = soup.select("tr[id*='trDataRow']")
    log.info("DEBUG: trDataRow rows: %d", len(rows))

    if not rows:
        tables = soup.find_all("table")
        log.info("DEBUG: total tables: %d", len(tables))
        for i, t in enumerate(tables):
            heads = []
            for th in t.find_all("th"):
                heads.append(th.get_text(strip=True).lower())
            if heads:
                log.info(
                    "DEBUG: table %d headers: %s",
                    i,
                    heads[:8],
                )
            has_rec = False
            has_dt = False
            for h in heads:
                if "record" in h:
                    has_rec = True
                if "date" in h:
                    has_dt = True
            if has_rec and has_dt:
                rows = t.find_all("tr")[1:]
                log.info(
                    "DEBUG: using table %d, rows=%d",
                    i,
                    len(rows),
                )
                break

    if not rows:
        gvs = soup.select("[class*='GridView'], [id*='GridView']")
        log.info("DEBUG: gridviews: %d", len(gvs))

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        texts = []
        for c in cells:
            texts.append(c.get_text(" ", strip=True))
        p = {}
        p["raw_cells"] = texts
        p["date"] = first_match(texts, r"^\d{1,2}/\d{1,2}/\d{2,4}$")
        p["record_number"] = first_match(texts, r"^[A-Z0-9-]{5,}$")
        p["status"] = find_status(texts)
        p["address"] = find_addr(texts)
        p["description"] = longest(texts)
        link = row.find("a", href=re.compile(r"Detail"))
        if link:
            p["detail_url"] = urljoin(BASE, link["href"])
            if not p["record_number"]:
                p["record_number"] = link.get_text(strip=True)
        if p["record_number"]:
            permits.append(p)

    has_next = False
    next_t = None
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        if text in ("next", ">", "next >"):
            href = a.get("href", "")
            m = re.search(r"__doPostBack\('([^']+)'", href)
            if m:
                has_next = True
                next_t = m.group(1)
                break
    return permits, has_next, next_t


def first_match(texts, pattern):
    rx = re.compile(pattern)
    for t in texts:
        if rx.match(t):
            return t
    return None


def longest(texts):
    if not texts:
        return ""
    return max(texts, key=len)


def find_addr(texts):
    for t in texts:
        if not re.match(r"^\d+\s+\S+", t):
            continue
        upper = t.upper()
        for tok in ADDR_TOKENS:
            if tok in upper:
                return t
    return None


def find_status(texts):
    for t in reversed(texts):
        if len(t) >= 60:
            continue
        lower = t.lower()
        for w in STATUS_WORDS:
            if w in lower:
                return t
    return None


def load_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def geocode(address, cache):
    if not address:
        return None, None
    full = address + ", Charlotte County, FL, USA"
    if full in cache:
        c = cache[full]
        return c.get("lat"), c.get("lon")
    try:
        time.sleep(1.1)
        params = {
            "q": full,
            "format": "json",
            "limit": 1,
            "countrycodes": "us",
        }
        headers = {"User-Agent": "solar-permits/1.0"}
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers=headers,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            cache[full] = {"lat": lat, "lon": lon}
            return lat, lon
    except Exception as e:
        log.warning("Geocode fail %s: %s", full, e)
    cache[full] = {"lat": None, "lon": None}
    return None, None


def main():
    today = datetime.now()
    delta = timedelta(days=LOOKBACK_DAYS)
    start = (today - delta).strftime("%m/%d/%Y")
    end = today.strftime("%m/%d/%Y")

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    all_permits = []
    seen = set()

    for lt in LICENSE_TYPES:
        try:
            permits = search_one(session, lt, start, end)
        except Exception as e:
            log.exception("Search fail %s: %s", lt, e)
            continue
        for p in permits:
            rn = p.get("record_number")
            if not rn or rn in seen:
                continue
            seen.add(rn)
            p["license_type"] = lt
            all_permits.append(p)

    log.info("=" * 50)
    log.info("Total: %d", len(all_permits))

    if all_permits:
        log.info("Geocoding...")
        cache = load_cache()
        for i, p in enumerate(all_permits, 1):
            lat, lon = geocode(p.get("address") or "", cache)
            p["lat"] = lat
            p["lon"] = lon
            if i % 10 == 0:
                save_cache(cache)
        save_cache(cache)

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": SEARCH_URL,
        "lookback_days": LOOKBACK_DAYS,
        "permit_count": len(all_permits),
        "permits": all_permits,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    log.info("Wrote %d permits", len(all_permits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
