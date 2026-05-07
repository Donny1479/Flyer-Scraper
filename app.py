"""
Tim Hortons Flyer Scanner — Streamlit UI
Displays cropped flyer images of Tim Hortons product blocks found across
Ontario grocery flyers. Click any image to jump to the exact SmartCanucks page.
"""

import io
import json
import base64
import sys
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
import streamlit as st
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from scraper import run_scraper, RETAILERS, HEADERS

RESULTS_FILE = Path(__file__).parent / "data" / "results.json"

# Padding added around each detected product block (pixels)
CROP_PADDING = 24

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tim Hortons Flyer Scanner",
    page_icon="☕",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .th-banner {
        background: linear-gradient(135deg, #C8102E 0%, #a50d25 100%);
        color: white;
        padding: 1.25rem 1.75rem;
        border-radius: 10px;
        margin-bottom: 1.25rem;
    }
    .th-banner h1 { margin: 0; font-size: 1.8rem; }
    .th-banner p  { margin: 0.25rem 0 0; opacity: 0.88; font-size: 0.95rem; }

    .flyer-img-link img {
        border-radius: 8px;
        border: 2px solid #E0E0E0;
        cursor: pointer;
        transition: border-color 0.15s;
        width: 100%;
    }
    .flyer-img-link img:hover { border-color: #C8102E; }

    [data-testid="metric-container"] {
        border-left: 3px solid #C8102E;
        padding-left: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_results() -> dict | None:
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return None


def format_ts(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%B %d, %Y — %I:%M %p")


def run_with_progress() -> dict:
    bar = st.progress(0.0)
    status = st.empty()

    def cb(msg: str, pct: float) -> None:
        status.text(msg)
        bar.progress(min(float(pct), 1.0))

    results = run_scraper(progress_callback=cb)
    bar.progress(1.0)
    status.success("Scan complete!")
    return results


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def fetch_and_crop(image_url: str, x1: float, y1: float, x2: float, y2: float) -> bytes:
    """
    Download a flyer page image and crop it to the bounding box with padding.
    Results are cached for 7 days so revisiting the app is instant.
    """
    resp = requests.get(image_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    w, h = img.size

    left   = max(0, int(x1 * w) - CROP_PADDING)
    top    = max(0, int(y1 * h) - CROP_PADDING)
    right  = min(w, int(x2 * w) + CROP_PADDING)
    bottom = min(h, int(y2 * h) + CROP_PADDING)

    cropped = img.crop((left, top, right, bottom))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def clickable_image(img_bytes: bytes, href: str, caption: str) -> None:
    """Render a cropped flyer image that links to the exact SmartCanucks page."""
    b64 = base64.b64encode(img_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"
    st.markdown(
        f'<div class="flyer-img-link">'
        f'<a href="{href}" target="_blank" title="View on SmartCanucks">'
        f'<img src="{data_url}" alt="Tim Hortons product block" />'
        f'</a></div>',
        unsafe_allow_html=True,
    )
    st.caption(caption)


def flatten_products(results: dict) -> list[dict]:
    rows = []
    for r in results["retailers"]:
        for p in r["products"]:
            rows.append({
                "Retailer":     r["name"],
                "Flyer":        p.get("flyer_title", ""),
                "Page":         p.get("page_number", ""),
                "Page URL":     p.get("page_url", p.get("flyer_url", "")),
                "Image URL":    p.get("image_url", ""),
                "crop_box":     p.get("crop_box", {}),
            })
    return rows


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ☕ Tim Hortons Flyer Scanner")
    st.divider()

    results = load_results()

    if results:
        st.success(f"**Last scanned:**\n{format_ts(results['scraped_at'])}")
    else:
        st.info("No scan data yet. Run your first scan!")

    refresh = st.button(
        "🔄 Scan Flyers Now",
        type="primary",
        use_container_width=True,
        help="Analyzes the latest Ontario flyer images via Claude Vision (~5–10 min).",
    )

    st.divider()
    st.markdown("**Retailers monitored (Ontario)**")
    for r in RETAILERS:
        st.caption(f"• {r['name']}")

    st.divider()
    st.caption(
        "Flyers from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · "
        "Detection by Claude Vision"
    )


# ── Banner ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="th-banner">'
    "<h1>☕ Tim Hortons Flyer Scanner</h1>"
    "<p>Ontario grocery flyer monitor · Click any product image to view the exact flyer page</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ── Handle refresh ────────────────────────────────────────────────────────────
if refresh:
    with st.spinner("Scanning flyers — this may take a few minutes…"):
        results = run_with_progress()
    st.rerun()

# ── No data state ─────────────────────────────────────────────────────────────
if not results:
    st.info(
        "No scan data found. Click **Scan Flyers Now** in the sidebar to start.\n\n"
        "The scanner will fetch the current Ontario flyer for each retailer, analyze "
        "every page with Claude Vision, and highlight any Tim Hortons product blocks."
    )
    st.stop()

# ── Flatten all products ──────────────────────────────────────────────────────
all_products = flatten_products(results)

# ── Summary metrics ───────────────────────────────────────────────────────────
retailers_with_deals = sum(1 for r in results["retailers"] if r["products"])
total_flyers = sum(len(r["flyers"]) for r in results["retailers"])
total_pages = sum(
    f.get("pages_scanned", 0)
    for r in results["retailers"]
    for f in r["flyers"]
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("🛒 Tim Hortons Blocks Found", len(all_products))
c2.metric("🏪 Retailers with Deals", f"{retailers_with_deals} / 8")
c3.metric("📰 Flyers Scanned", total_flyers)
c4.metric("📄 Pages Analyzed", total_pages)

st.divider()

# ── Retailer filter ───────────────────────────────────────────────────────────
all_retailer_names = [r["name"] for r in RETAILERS]
selected_retailers = st.multiselect(
    "Filter by Retailer",
    options=all_retailer_names,
    default=all_retailer_names,
    key="retailer_filter",
)

filtered = [p for p in all_products if p["Retailer"] in selected_retailers]

# ── Results ───────────────────────────────────────────────────────────────────
if not all_products:
    st.warning(
        "No Tim Hortons products were detected in this week's flyers. "
        "Try again on Monday when new flyers post, or hit **Scan Flyers Now** to re-run."
    )

elif not filtered:
    st.info("No products match the selected retailer filter.")

else:
    scan_date = results["scraped_at"][:10]
    st.markdown(f"### Week of {scan_date}")

    for retailer_cfg in RETAILERS:
        r_name = retailer_cfg["name"]
        if r_name not in selected_retailers:
            continue

        r_products = [p for p in filtered if p["Retailer"] == r_name]
        r_meta = next((r for r in results["retailers"] if r["name"] == r_name), None)
        pages_scanned = (
            sum(f.get("pages_scanned", 0) for f in r_meta["flyers"]) if r_meta else 0
        )

        if r_products:
            label = f"🛒 **{r_name}** — {len(r_products)} Tim Hortons block(s) found"
        else:
            label = f"🛒 **{r_name}** — no deals found this week"

        with st.expander(label, expanded=bool(r_products)):
            if not r_products:
                if pages_scanned:
                    st.caption(
                        f"Scanned {pages_scanned} page(s) — "
                        "no Tim Hortons products detected."
                    )
                else:
                    st.caption("No Ontario flyer found for this retailer.")
                continue

            # Display cropped product images in a 2-column grid
            cols = st.columns(2)
            for idx, p in enumerate(r_products):
                box = p["crop_box"]
                try:
                    img_bytes = fetch_and_crop(
                        p["Image URL"],
                        box["x1"], box["y1"],
                        box["x2"], box["y2"],
                    )
                except Exception as e:
                    cols[idx % 2].warning(f"Could not load image: {e}")
                    continue

                caption = f"{p['Flyer']} · Page {p['Page']}"
                with cols[idx % 2]:
                    clickable_image(img_bytes, p["Page URL"], caption)

# ── CSV export ────────────────────────────────────────────────────────────────
if all_products:
    st.divider()
    export_df = pd.DataFrame([
        {
            "Retailer": p["Retailer"],
            "Flyer":    p["Flyer"],
            "Page":     p["Page"],
            "SmartCanucks URL": p["Page URL"],
        }
        for p in all_products
    ])
    st.download_button(
        label="⬇ Download Results as CSV",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name=f"tim_hortons_deals_{results['scraped_at'][:10]}.csv",
        mime="text/csv",
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Tim Hortons Canada CPG Team · "
    "Data from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · "
    "Runs every Monday for the upcoming week's flyers"
)
