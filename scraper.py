#!/usr/bin/env python3
"""
Tim Hortons Flyer Scanner
Scrapes SmartCanucks.ca for Tim Hortons products in Ontario grocery flyers.
Supports per-week history and smart incremental scanning via a scanned registry.
"""

import os
import json
import time
import base64
import re
import requests
import anthropic
from pathlib import Path
from datetime import datetime, date as _date, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()


def _get_api_key() -> str:
    """Return Anthropic API key from Streamlit secrets (cloud) or .env (local)."""
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY", "")


BASE_URL    = "https://flyers.smartcanucks.ca"
DATA_DIR    = Path(__file__).parent / "data"
HISTORY_DIR = DATA_DIR / "history"
REGISTRY_FILE = DATA_DIR / "scanned_registry.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
    "Referer": "https://flyers.smartcanucks.ca/",
}

RETAILERS = [
    {
        "name": "Walmart",
        "listing_url": f"{BASE_URL}/walmart-canada",
        "url_patterns": ["/canada/walmart-on-flyer-"],
    },
    {
        "name": "Sobeys",
        "listing_url": f"{BASE_URL}/sobeys-canada",
        "url_patterns": ["/canada/sobeys-on-flyer-"],
    },
    {
        "name": "No Frills",
        "listing_url": f"{BASE_URL}/no-frills-canada",
        # GTA is within Ontario — scan both regional flyers
        "url_patterns": ["/canada/no-frills-on-flyer-", "/canada/no-frills-gta-flyer-"],
    },
    {
        "name": "FreshCo",
        "listing_url": f"{BASE_URL}/freshco-chalo-freshco-canada",
        "url_patterns": ["/canada/freshco-on-flyer-"],
    },
    {
        "name": "RCSS",
        "listing_url": f"{BASE_URL}/real-canadian-superstore-canada",
        "url_patterns": ["/canada/real-canadian-superstore-on-flyer-"],
    },
    {
        "name": "Loblaws",
        "listing_url": f"{BASE_URL}/loblaws-canada",
        "url_patterns": ["/canada/loblaws-on-flyer-"],
    },
    {
        "name": "Metro",
        "listing_url": f"{BASE_URL}/metro-canada",
        "url_patterns": ["/canada/metro-on-flyer-"],
    },
    {
        "name": "Food Basics",
        "listing_url": f"{BASE_URL}/food-basics-canada",
        # No regional split — one national flyer covers Ontario
        "url_patterns": ["/canada/food-basics-flyer-"],
    },
]

VISION_MODEL = "claude-sonnet-4-6"

EXTRACTION_PROMPT = """\
You are analyzing a Canadian grocery store flyer page image.

GOAL: Find products where the brand name "Tim Hortons" is EXPLICITLY printed and clearly readable on the product packaging or product label.

VERIFICATION PROCESS — for every candidate product, you MUST:
1. Read the brand text directly from the product packaging in the image (do NOT guess or infer from context)
2. Quote that text VERBATIM in the "brand_text_seen" field
3. The quoted text MUST literally contain the words "Tim Hortons"
4. If you cannot clearly read the words "Tim Hortons" on the product itself, EXCLUDE it

REJECT — these are NOT Tim Hortons (do not return them under any circumstances):
• Maxwell House, Folgers, Nescafé, Starbucks, Keurig, McCafé, Lavazza
• Nespresso, Nabob, Van Houtte, Kicking Horse, Kirkland, Mother Parkers
• PC / President's Choice, No Name, Selection, Compliments, Great Value
• Any generic K-Cup, coffee pod, ground coffee, or instant coffee box that does not show "Tim Hortons" branding

For each VERIFIED Tim Hortons product, return a JSON object with these fields:
{
  "brand_text_seen": "<exact text quoted from the product packaging — must include 'Tim Hortons'>",
  "product_name":    "<full product name including size/quantity if shown>",
  "price":           "<price as displayed, e.g. '$5.99', '2 for $10.00', 'Sale $7.99'>",
  "deal_details":    "<any extra info like 'Save $2.00', 'with PC Optimum', 'limit 2', or empty string>"
}

If you have ANY doubt about whether the words "Tim Hortons" are visible on the product, EXCLUDE it.

Respond ONLY with a valid JSON array. No explanation, no markdown fences.
If no Tim Hortons products are visible: []

Example response:
[{
  "brand_text_seen": "Tim Hortons Original Blend",
  "product_name":    "Tim Hortons Original Blend Coffee Pods 30pk",
  "price":           "$9.99",
  "deal_details":    "Save $3.00"
}]
"""

# Month names used to build the URL slugs SmartCanucks embeds in flyer URLs
MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


# ── Date utilities ─────────────────────────────────────────────────────────────

def get_week_start(target: _date | None = None) -> _date:
    """Return the Thursday on or before target (defaults to today)."""
    if target is None:
        target = _date.today()
    days_back = (target.weekday() - 3) % 7  # Thursday = weekday 3
    return target - timedelta(days=days_back)


def get_week_end(week_start: _date) -> _date:
    """Return the Wednesday that ends the flyer week starting on week_start."""
    return week_start + timedelta(days=6)


def date_to_url_slug(d: _date) -> str:
    """Convert a date to the SmartCanucks URL slug, e.g. May 7 → 'may-7'."""
    return f"{MONTH_NAMES[d.month - 1]}-{d.day}"


def get_past_week_starts(n: int = 4) -> list[_date]:
    """Return the last n Thursday week-start dates, most recent first."""
    current = get_week_start()
    return [current - timedelta(weeks=i) for i in range(n)]


def format_week_label(week_start, week_end=None) -> str:
    """Return a human-readable label like 'May 7–13, 2026' or 'Apr 30 – May 6, 2026'."""
    try:
        if isinstance(week_start, str):
            week_start = _date.fromisoformat(week_start)
        if week_end is None:
            week_end = get_week_end(week_start)
        elif isinstance(week_end, str):
            week_end = _date.fromisoformat(week_end)

        if week_start.month == week_end.month:
            return (
                f"{week_start.strftime('%b')} {week_start.day}"
                f"–{week_end.day}, {week_start.year}"
            )
        return (
            f"{week_start.strftime('%b')} {week_start.day} – "
            f"{week_end.strftime('%b')} {week_end.day}, {week_start.year}"
        )
    except Exception:
        return str(week_start)


# ── Scanned-flyer registry ─────────────────────────────────────────────────────
# Tracks which flyer URLs have already been fully scanned so the "Scan New
# Flyers" button can skip them and avoid redundant Claude API calls.

def load_scanned_registry() -> set:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE) as f:
                return set(json.load(f).get("scanned_urls", []))
        except (json.JSONDecodeError, OSError):
            pass
    return set()


def save_scanned_registry(urls: set) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump({"scanned_urls": sorted(urls)}, f, indent=2)


# ── History loader ─────────────────────────────────────────────────────────────

def load_all_history() -> list[dict]:
    """Return all weekly scan result dicts from data/history/, newest first."""
    if not HISTORY_DIR.exists():
        return []
    files = sorted(HISTORY_DIR.glob("*.json"), reverse=True)
    history = []
    for fp in files:
        try:
            with open(fp) as f:
                history.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return history


# ── Core scraping ─────────────────────────────────────────────────────────────

def get_current_ontario_flyers(
    retailer: dict, week_start: _date | None = None
) -> list[dict]:
    """
    Fetch the retailer's SmartCanucks listing page and return Ontario flyers.

    If week_start is provided, only flyers whose URL contains that date slug
    are returned (e.g. '-may-7-' for May 7). This allows finding historical
    (now-expired) flyers. Without week_start, returns the first/most-recent
    flyer per URL pattern — the current week's flyer.
    """
    print(f"  Fetching: {retailer['listing_url']}")
    try:
        resp = requests.get(retailer["listing_url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching listing page: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    date_slug = date_to_url_slug(week_start) if week_start else None

    seen_patterns: set[str] = set()
    seen_urls: set[str] = set()
    flyers: list[dict] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"]

        matched_pattern = next(
            (pat for pat in retailer["url_patterns"] if pat in href), None
        )
        if not matched_pattern:
            continue

        # Historical week filter: the URL must contain the date slug
        # e.g. "-may-7-" for May 7, "-april-30-" for April 30
        if date_slug and f"-{date_slug}-" not in href:
            continue

        # One result per URL pattern (first hit = most recent / target week)
        if matched_pattern in seen_patterns:
            continue

        full_url = BASE_URL + href if href.startswith("/") else href
        if full_url in seen_urls:
            continue

        seen_patterns.add(matched_pattern)
        seen_urls.add(full_url)

        slug = href.rstrip("/").split("/")[-1]
        title = slug.replace("-", " ").title()
        flyers.append({"title": title, "url": full_url})

    return flyers


def get_flyer_images(flyer_url: str) -> list[str]:
    """Fetch the /all view of a flyer and return all page image URLs, sorted by page number."""
    all_url = flyer_url.rstrip("/") + "/all"
    print(f"    Fetching page list: {all_url}")
    try:
        resp = requests.get(all_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ERROR fetching /all: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    images: list[str] = []
    seen: set[str] = set()

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy") or ""
        if not src or "/uploads/pages/" not in src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = BASE_URL + src
        if src not in seen:
            seen.add(src)
            images.append(src)

    def _page_num(url: str) -> int:
        try:
            return int(url.split("/")[-1].rsplit(".", 1)[0].rsplit("-", 1)[-1])
        except (ValueError, IndexError):
            return 0

    images.sort(key=_page_num)
    return images


def analyze_page_for_tim_hortons(
    image_url: str, client: anthropic.Anthropic
) -> list[dict]:
    """
    Download a flyer page image and use Claude Sonnet Vision to identify
    Tim Hortons products.

    Two-layer verification:
    1. Prompt requires Claude to quote the brand text it reads verbatim.
    2. Server-side filter: any result whose brand_text_seen doesn't literally
       contain 'tim hortons' is dropped — catches hallucinated attributions.
    """
    try:
        img_resp = requests.get(image_url, headers=HEADERS, timeout=30)
        img_resp.raise_for_status()
    except requests.RequestException as e:
        print(f"      WARN: Could not download image: {e}")
        return []

    image_data = base64.standard_b64encode(img_resp.content).decode("utf-8")
    content_type = img_resp.headers.get("Content-Type", "image/jpeg").lower()
    if "png" in content_type:
        media_type = "image/png"
    elif "webp" in content_type:
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"

    try:
        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }
            ],
        )
    except anthropic.APIError as e:
        print(f"      WARN: Claude API error: {e}")
        return []

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[start:end]).strip()

    def _parse(text: str) -> list[dict]:
        items = json.loads(text)
        if not isinstance(items, list):
            return []
        verified = []
        for item in items:
            if not isinstance(item, dict):
                continue
            brand_text = str(item.get("brand_text_seen", "")).lower()
            if "tim hortons" not in brand_text:
                continue
            verified.append({
                "product_name":    str(item.get("product_name", "")).strip(),
                "price":           str(item.get("price", "")).strip(),
                "deal_details":    str(item.get("deal_details", "")).strip(),
                "brand_text_seen": str(item.get("brand_text_seen", "")).strip(),
            })
        return verified

    try:
        return _parse(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return _parse(match.group())
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
    return []


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_scraper(
    week_start: _date | None = None,
    skip_scanned: bool = True,
    progress_callback=None,
) -> dict:
    """
    Scan Tim Hortons flyers for a single week.

    For each retailer, flyer URLs already in the scanned registry are skipped
    and their cached data is restored from the existing history file. Only
    genuinely new flyers cost Claude API tokens.

    Results are saved to data/history/{week_start}.json.
    """
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. "
            "Local: copy .env.example to .env. "
            "Streamlit Cloud: add it under App Settings → Secrets."
        )

    client = anthropic.Anthropic(api_key=api_key)

    if week_start is None:
        week_start = get_week_start()
    week_end = get_week_end(week_start)

    history_file = HISTORY_DIR / f"{week_start.isoformat()}.json"

    # Load existing data for this week so we can restore cached retailer results
    existing_by_retailer: dict[str, dict] = {}
    if history_file.exists():
        try:
            with open(history_file) as f:
                for r in json.load(f).get("retailers", []):
                    existing_by_retailer[r["name"]] = r
        except (json.JSONDecodeError, OSError):
            pass

    scanned = load_scanned_registry() if skip_scanned else set()

    results: dict = {
        "scraped_at": datetime.now().isoformat(),
        "week_start": week_start.isoformat(),
        "week_end":   week_end.isoformat(),
        "retailers":  [],
    }

    total = len(RETAILERS)

    for i, retailer in enumerate(RETAILERS):
        if progress_callback:
            progress_callback(
                f"Checking {retailer['name']}…",
                i / total,
            )

        print(f"\n{'=' * 60}")
        print(f"[{i + 1}/{total}] {retailer['name']} — {format_week_label(week_start)}")
        print("=" * 60)

        retailer_result: dict = {"name": retailer["name"], "flyers": [], "products": []}

        # Find flyers for this specific week
        flyers = get_current_ontario_flyers(retailer, week_start=week_start)

        if not flyers:
            print("  No Ontario flyer found for this week.")
            if retailer["name"] in existing_by_retailer:
                results["retailers"].append(existing_by_retailer[retailer["name"]])
            else:
                results["retailers"].append(retailer_result)
            continue

        # Separate new flyers from already-scanned ones
        new_flyers      = [f for f in flyers if f["url"] not in scanned]
        done_flyer_urls = {f["url"] for f in flyers if f["url"] in scanned}

        # Restore cached product data for already-scanned flyers
        if done_flyer_urls and retailer["name"] in existing_by_retailer:
            ex = existing_by_retailer[retailer["name"]]
            for ef in ex.get("flyers", []):
                if ef.get("url") in done_flyer_urls:
                    retailer_result["flyers"].append(ef)
            for ep in ex.get("products", []):
                if ep.get("flyer_url") in done_flyer_urls:
                    retailer_result["products"].append(ep)

        if not new_flyers:
            print(
                f"  All flyers already scanned — "
                f"restoring {len(retailer_result['products'])} cached product(s)."
            )
            results["retailers"].append(retailer_result)
            continue

        # Scan each new flyer
        for flyer in new_flyers:
            print(f"\n  ► {flyer['title']}")

            images = get_flyer_images(flyer["url"])
            print(f"    Pages to scan: {len(images)}")

            if not images:
                retailer_result["flyers"].append({
                    "title": flyer["title"], "url": flyer["url"],
                    "pages_scanned": 0, "products_found": 0,
                })
                scanned.add(flyer["url"])
                save_scanned_registry(scanned)
                continue

            flyer_products: list[dict] = []

            for page_idx, image_url in enumerate(images):
                page_num = page_idx + 1
                filename = image_url.split("/")[-1]
                print(
                    f"    Page {page_num:2d}/{len(images)}  {filename} …",
                    end=" ", flush=True,
                )

                products = analyze_page_for_tim_hortons(image_url, client)
                print(f"✓ {len(products)} verified" if products else "—")

                page_url = f"{flyer['url'].rstrip('/')}/single/{page_num - 1}"
                for product in products:
                    product["page_number"] = page_num
                    product["page_url"]    = page_url
                    product["image_url"]   = image_url
                    product["flyer_title"] = flyer["title"]
                    product["flyer_url"]   = flyer["url"]
                    flyer_products.append(product)

                time.sleep(0.4)

            retailer_result["flyers"].append({
                "title":          flyer["title"],
                "url":            flyer["url"],
                "pages_scanned":  len(images),
                "products_found": len(flyer_products),
            })
            retailer_result["products"].extend(flyer_products)

            # Add to registry only after all pages have been processed
            scanned.add(flyer["url"])
            save_scanned_registry(scanned)

        count = len(retailer_result["products"])
        print(f"\n  Tim Hortons products verified: {count}")
        results["retailers"].append(retailer_result)

        time.sleep(1)

    # Persist this week's results
    with open(history_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {history_file}")

    return results


def run_historical_scan(n_weeks: int = 4, progress_callback=None) -> list[dict]:
    """
    Scan the last n flyer cycles (Thursday–Wednesday weeks), skipping any
    flyer URLs already in the scanned registry to avoid redundant API calls.

    On first run this scans all n weeks.
    On subsequent Monday runs only the new week's flyers are processed.
    Returns a list of per-week result dicts, newest first.
    """
    week_starts = get_past_week_starts(n_weeks)
    all_results: list[dict] = []

    for i, week_start in enumerate(week_starts):
        label = format_week_label(week_start)

        def _cb(msg: str, pct: float, _i: int = i, _label: str = label) -> None:
            if progress_callback:
                overall = (_i + pct) / n_weeks
                progress_callback(f"Week {_i + 1}/{n_weeks} ({_label}): {msg}", overall)

        print(f"\n{'#' * 70}")
        print(f"# WEEK {i + 1}/{n_weeks}: {label}")
        print(f"{'#' * 70}")

        result = run_scraper(
            week_start=week_start,
            skip_scanned=True,
            progress_callback=_cb,
        )
        all_results.append(result)

    if progress_callback:
        progress_callback("All weeks processed!", 1.0)

    return all_results


if __name__ == "__main__":
    run_historical_scan(n_weeks=4)
