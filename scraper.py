#!/usr/bin/env python3
"""
Charlotte County, FL Solar Permit Scraper
Scrapes the BOCC Accela Citizen Access portal, filters for solar permits
across all statuses, geocodes the addresses, and writes permits.json.
"""

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

BASE_URL = "https://aca-prod.accela.com/BOCC/"
SEARCH_URL = urljoin(BASE_URL, "Cap/CapHome.aspx?module=Building&TabName=Building")

SOLAR_LICENSE_TYPES = [
    "C SOLAR ENERGY",
    "C SOLAR SYSTEM",
    "C SOLAR WAT HEAT",
]

LOOKBACK_DAYS = 365
OUTPUT_FILE = Path(__file__).parent / "permits.json"
CACHE_FILE = Path(__file__).parent / ".geocode_cache.json"

REQUEST_DELAY_SEC = 1.5
PAGE_DELAY_SEC = 2.0

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("solar-scraper")


def extract_form_state(html):
    soup = BeautifulSoup(html, "html.parser")
    state = {}
    for name in (
        "__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
        "__VIEWSTATEENCRYPTED", "__EVENTTARGET", "__EVENTARGUMENT",
    ):
        el = soup.find("input", {"name": name})
        if el is not None:
            state[name] = el.get("value", "")
    return state


def find_input_by_label_fragment(soup, label_fragment):
    for label in soup.find_all(string=re.compile(label_fragment, re.I)):
        parent = label.parent
        for _ in range(6):
            if parent is None:
                break
            ctrl = parent.find(["input", "select"])
            if ctrl is not None and ctrl.get("name"):
                return ctrl["name"]
            parent = parent.parent
    return None


def discover_field_names(html):
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for select in soup.find_all("select"):
        opts = [o.get_text(strip=True) for o in select.find_all("option")]
        if any("SOLAR ENERGY" in o for o in opts):
            fields["license_type"] = select.get("name")
            break
    fields["start_date"] = find_input_by_label_fragment(soup, r"Start Date")
    fields["end_date"] = find_input_by_label_fragment(soup, r"End Date")
    for btn in soup.find_all("a"):
        if btn.get("title") == "Search" and "btnNewSearch" in (btn.get("href") or ""):
            m = re.search(r"WebForm_PostBackOptions\(new WebForm_PostBackOptions\(\"([^\"]+)\"", btn["href"])
            if m:
                fields["search_event_target"] = m.group(1)
                break
    return fields


def run_search(session, license_type, start_date, end_date):
    log.info("Searching license type: %s (%s -> %s)", license_type, start_date, end_date)
    resp = session.get(SEARCH_URL, timeout=30)
    resp.raise_for_status()
    state = extract_form_state(resp.text)
    fields = discover_field_names(resp.text)

    if not fields.get("license_type"):
        log.error("Could not locate License Type field. Site layout may have changed.")
        return []

    payload = {
        "__EVENTTARGET": fields.get("search_event_target", "ctl00$PlaceHolderMain$btnNewSearch"),
        "__EVENTARGUMENT": "",
        **state,
        fields["license_type"]: license_type,
    }
    if fields.get("start_date"):
        payload[fields["start_date"]] = start_date
    if fields.get("end_date"):
        payload[fields["end_date"]] = end_date

    time.sleep(REQUEST_DELAY_SEC)
    resp = session.post(SEARCH_URL, data=payload, timeout=60)
    resp.raise_for_status()

    permits = []
    page_num = 1
    while True:
        page_permits, has_next, next_target = parse_results_page(resp.text)
        log.info("  Page %d: parsed %d permits", page_num, len(page_permits))
        permits.extend(page_permits)
        if not has_next:
            break
        time.sleep(PAGE_DELAY_SEC)
        state = extract_form_state(resp.text)
        payload = {
            "__EVENTTARGET": next_target,
            "__EVENTARGUMENT": "",
            **state,
        }
        resp = session.post(SEARCH_URL, data=payload, timeout=60)
        resp.raise_for_status()
        page_num += 1
        if page_num > 50:
            log.warning("Hit page-count safety limit (50). Stopping.")
            break
    return permits


def parse_results_page(html):
    soup = BeautifulSoup(html, "html.parser")
    permits = []
    rows = soup.select("tr[id*='trDataRow']")
    if not rows:
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if any("record" in h for h in headers) and any("date" in h for h in headers):
                rows = table.find_all("tr")[1:]
                break

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        texts = [c.get_text(" ", strip=True) for c in cells]
        permit = {
            "raw_cells": texts,
            "date": _first_match(texts, r"^\d{1,2}/\d{1,2}/\d{2,4}$"),
            "record_number": _first_match(texts, r"^[A-Z0-9-]{5,}$"),
            "status": _last_status(texts),
            "address": _first_address(texts),
            "description": _longest_text(texts),
        }
        link = row.find("a", href=re.compile(r"CapDetail|Cap/.*Detail"))
        if link:
            permit["detail_url"] = urljoin(BASE_URL, link["href"])
            if not permit["record_number"]:
                permit["record_number"] = link.get_text(strip=True)
        if permit["record_number"]:
            permits.append(permit)

    has_next = False
    next_target = None
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        if text in ("next", ">", "next >"):
            href = a.get("href", "")
            m = re.search(r"__doPostBack\('([^']+)'", href)
            if m:
                has_next = True
                next_target = m.group(1)
                break
    return permits, has_next, next_target


def _first_match(texts, pattern):
    rx = re.compile(pattern)
    for t in texts:
        if rx.match(t):
            return t
    return None


def _longest_text(texts):
    return max(texts, key=len) if texts else ""


def _first_address(texts):
    for t in texts:
        if re.match(r"^\d+\s+\S+", t) and any(
            tok in t.upper()
            for tok in (" RD", " ST", " AVE", " BLVD", " DR", " LN", " CT",
                        " PKWY", " WAY", " TER", " CIR", " HWY", " TRL", " PL")
        ):
            return t
    return None


def _last_status(texts):
    status_keywords = (
        "issued", "review", "submitted", "pending", "approved", "void",
        "expired", "finaled", "closed", "hold", "withdrawn", "in process",
        "incomplete", "ready",
    )
    for t in reversed(texts):
        if any(k in t.lower() for k in status_keywords) and len(t) < 60:
            return t
    return None


def load_geocode_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_geocode_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def geocode(address, cache):
    if not address:
        return None, None
    full = f"{address}, Charlotte County, FL, USA"
    if full in cache:
        return cache[full].get("lat"), cache[full].get("lon")
    try:
        time.sleep(1.1)
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": full, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": "charlotte-county-solar-permits/1.0"},
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
        log.warning("Geocode failed for %s: %s", full, e)
    cache[full] = {"lat": None, "lon": None}
    return None, None


def main():
    today = datetime.now()
    start = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%m/%d/%Y")
    end = today.strftime("%m/%d/%Y")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    all_permits = []
    seen = set()

    for lt in SOLAR_LICENSE_TYPES:
        try:
            permits = run_search(session, lt, start, end)
        except Exception as e:
            log.exception("Search failed for %s: %s", lt, e)
            continue
        for p in permits:
            rn = p.get("record_number")
            if not rn or rn in seen:
                continue
            seen.add(rn)
            p["license_type"] = lt
            all_permits.append(p)

    log.info("Total unique solar permits scraped: %d", len(all_permits))

    log.info("Geocoding addresses...")
    cache = load_geocode_cache()
    for i, p in enumerate(all_permits, 1):
        lat, lon = geocode(p.get("address") or "", cache)
        p["lat"] = lat
        p["lon"] = lon
        if i % 10 == 0:
            log.info("  geocoded %d/%d", i, len(all_permits))
            save_geocode_cache(cache)
    save_geocode_cache(cache)

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": SEARCH_URL,
        "lookback_days": LOOKBACK_DAYS,
        "permit_count": len(all_permits),
        "permits": all_permits,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    log.info("Wrote %s (%d permits)", OUTPUT_FILE, len(all_permits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
