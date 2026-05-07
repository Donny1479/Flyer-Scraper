#!/usr/bin/env python3
"""
Tim Hortons Flyer Scanner
Scrapes SmartCanucks.ca for Tim Hortons products in Ontario grocery flyers.
Uses Claude Vision (Haiku) to analyze each flyer page image.
"""

import os
import json
import time
import base64
import re
import requests
import anthropic
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://flyers.smartcanucks.ca"
DATA_DIR = Path(__file__).parent / "data"
RESULTS_FILE = DATA_DIR / "results.json"

# Polite browser headers for web requests
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
    "Referer": "https://flyers.smartcanucks.ca/",
}

# Each retailer has a listing page and Ontario-specific URL patterns.
# url_patterns match against the /canada/<slug> path to identify Ontario flyers.
# The scraper takes the FIRST match per pattern (newest = current week's flyer).
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
        # Food Basics has no regional split — one national flyer covers Ontario
        "url_patterns": ["/canada/food-basics-flyer-"],
    },
]

VISION_MODEL = "claude-haiku-4-5-20251001"

EXTRACTION_PROMPT = """\
You are analyzing a Canadian grocery store flyer page image.

Your task: Identify ALL Tim Hortons branded products visible on this page.

Tim Hortons products include (but are not limited to):
- Ground coffee, whole bean coffee, instant coffee
- K-Cup pods / coffee pods / espresso capsules
- Steeped tea bags, iced tea, hot chocolate
- Timbiebs merchandise or collab products
- Any product that displays the Tim Hortons name or logo

For each Tim Hortons product found, return a JSON object with:
  "product_name"  — full product name as printed (include size/quantity/variety if shown)
  "price"         — price as displayed (e.g. "$5.99", "2 for $10.00", "Sale $7.99")
  "deal_details"  — any extra context (e.g. "Save $2.00", "with PC Optimum", "limit 2 per customer"), or ""

Respond ONLY with a valid JSON array. No prose, no markdown fences.
If no Tim Hortons products are visible, respond with exactly: []

Example:
[{"product_name": "Tim Hortons Original Blend K-Cup Coffee Pods 30pk", "price": "$9.99", "deal_details": "Save $3.00"}]
"""


def get_current_ontario_flyers(retailer: dict) -> list[dict]:
    """
    Fetch the retailer's SmartCanucks listing page and return the current
    Ontario flyer(s). Returns at most one result per URL pattern (the first
    match, which SmartCanucks lists as the most recent / current flyer).
    """
    print(f"  Fetching: {retailer['listing_url']}")
    try:
        resp = requests.get(retailer["listing_url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching listing page: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    seen_patterns: set[str] = set()
    seen_urls: set[str] = set()
    flyers: list[dict] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"]

        # Match against Ontario-specific URL patterns
        matched_pattern = next(
            (pat for pat in retailer["url_patterns"] if pat in href), None
        )
        if not matched_pattern:
            continue

        # One result per pattern keeps us on the current week's flyer
        if matched_pattern in seen_patterns:
            continue

        full_url = BASE_URL + href if href.startswith("/") else href
        if full_url in seen_urls:
            continue

        seen_patterns.add(matched_pattern)
        seen_urls.add(full_url)

        # Derive a human-readable title from the URL slug
        slug = href.rstrip("/").split("/")[-1]
        title = slug.replace("-", " ").title()

        flyers.append({"title": title, "url": full_url})

    return flyers


def get_flyer_images(flyer_url: str) -> list[str]:
    """
    Fetch the /all view of a flyer and return all full-resolution page image
    URLs, sorted by page number.
    """
    all_url = flyer_url.rstrip("/") + "/all"
    print(f"    Fetching page list: {all_url}")

    try:
        resp = requests.get(all_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ERROR fetching /all page: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    images: list[str] = []
    seen: set[str] = set()

    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy")
            or ""
        )
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
        name = url.split("/")[-1].rsplit(".", 1)[0]
        parts = name.rsplit("-", 1)
        try:
            return int(parts[-1])
        except (ValueError, IndexError):
            return 0

    images.sort(key=_page_num)
    return images


def analyze_page_for_tim_hortons(
    image_url: str, client: anthropic.Anthropic
) -> list[dict]:
    """
    Download a flyer page image and use Claude Vision to identify Tim Hortons
    products. Returns a (possibly empty) list of product dicts.
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
    elif "gif" in content_type:
        media_type = "image/gif"
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

    # Strip markdown code fences if the model added them despite instructions
    if raw.startswith("```"):
        lines = raw.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[start:end]).strip()

    try:
        products = json.loads(raw)
        if isinstance(products, list):
            return products
    except json.JSONDecodeError:
        # Last-ditch attempt: find a JSON array anywhere in the response
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            try:
                products = json.loads(match.group())
                if isinstance(products, list):
                    return products
            except json.JSONDecodeError:
                pass

    return []


def run_scraper(progress_callback=None) -> dict:
    """
    Run the full Tim Hortons flyer scanning pipeline across all configured
    Ontario retailers.

    Args:
        progress_callback: Optional callable(message: str, fraction: float)
                           for real-time progress updates (used by Streamlit).

    Returns:
        Results dict with all found products grouped by retailer,
        also written to data/results.json.
    """
    DATA_DIR.mkdir(exist_ok=True)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )

    client = anthropic.Anthropic(api_key=api_key)

    results: dict = {
        "scraped_at": datetime.now().isoformat(),
        "retailers": [],
    }

    total = len(RETAILERS)

    for i, retailer in enumerate(RETAILERS):
        if progress_callback:
            progress_callback(f"Scanning {retailer['name']}…", i / total)

        print(f"\n{'=' * 60}")
        print(f"[{i + 1}/{total}] {retailer['name']}")
        print("=" * 60)

        retailer_result: dict = {
            "name": retailer["name"],
            "flyers": [],
            "products": [],
        }

        # ── Step 1: find current Ontario flyers ──────────────────────────────
        flyers = get_current_ontario_flyers(retailer)
        if not flyers:
            print("  No Ontario flyers found — skipping.")
            results["retailers"].append(retailer_result)
            continue

        print(f"  Found {len(flyers)} flyer(s):")
        for f in flyers:
            print(f"    • {f['title']}")

        # ── Step 2: process each flyer ────────────────────────────────────────
        for flyer in flyers:
            print(f"\n  ► {flyer['title']}")

            images = get_flyer_images(flyer["url"])
            print(f"    Pages to scan: {len(images)}")

            if not images:
                retailer_result["flyers"].append(
                    {
                        "title": flyer["title"],
                        "url": flyer["url"],
                        "pages_scanned": 0,
                        "products_found": 0,
                    }
                )
                continue

            flyer_products: list[dict] = []

            # ── Step 3: Vision analysis per page ─────────────────────────────
            for page_idx, image_url in enumerate(images):
                page_num = page_idx + 1
                filename = image_url.split("/")[-1]
                print(
                    f"    Page {page_num:2d}/{len(images)}  {filename} …",
                    end=" ",
                    flush=True,
                )

                products = analyze_page_for_tim_hortons(image_url, client)

                if products:
                    print(f"✓ {len(products)} product(s) found")
                else:
                    print("—")

                for p in products:
                    p["page_number"] = page_num
                    p["image_url"] = image_url
                    p["flyer_title"] = flyer["title"]
                    p["flyer_url"] = flyer["url"]
                    flyer_products.append(p)

                # Be polite to the server and the API
                time.sleep(0.4)

            retailer_result["flyers"].append(
                {
                    "title": flyer["title"],
                    "url": flyer["url"],
                    "pages_scanned": len(images),
                    "products_found": len(flyer_products),
                }
            )
            retailer_result["products"].extend(flyer_products)

        count = len(retailer_result["products"])
        print(f"\n  Tim Hortons products found: {count}")
        results["retailers"].append(retailer_result)

        # Brief pause between retailers
        time.sleep(1)

    # ── Save results ─────────────────────────────────────────────────────────
    if progress_callback:
        progress_callback("Saving results…", 0.98)

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    grand_total = sum(len(r["products"]) for r in results["retailers"])
    print(f"\n{'=' * 60}")
    print(f"Scan complete! {grand_total} Tim Hortons product(s) found.")
    print(f"Results saved to: {RESULTS_FILE}")

    if progress_callback:
        progress_callback("Done!", 1.0)

    return results


if __name__ == "__main__":
    run_scraper()
