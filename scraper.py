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
ORIGIN = "https://aca-prod.accela.com"

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


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": SEARCH_URL,
        "Origin": ORIGIN,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def get_form_state(html):
    soup = BeautifulSoup(html, "html.parser")
    state = {}
    for name in VS_KEYS:
        el = soup.​​​​​​​​​​​​​​​​
