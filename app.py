"""
Tim Hortons Flyer Scanner — Streamlit UI
Displays Tim Hortons products found across Ontario grocery flyers.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from scraper import run_scraper, RETAILERS

RESULTS_FILE = Path(__file__).parent / "data" / "results.json"

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
    /* Top banner */
    .th-banner {
        background: linear-gradient(135deg, #C8102E 0%, #a50d25 100%);
        color: white;
        padding: 1.25rem 1.75rem;
        border-radius: 10px;
        margin-bottom: 1.25rem;
    }
    .th-banner h1 { margin: 0; font-size: 1.8rem; }
    .th-banner p  { margin: 0.25rem 0 0; opacity: 0.88; font-size: 0.95rem; }

    /* Per-product row */
    .product-row {
        background: #FFF8F0;
        border-left: 4px solid #C8102E;
        padding: 0.6rem 1rem;
        border-radius: 4px;
        margin-bottom: 0.4rem;
    }

    /* Price pill */
    .price-pill {
        display: inline-block;
        background: #C8102E;
        color: white;
        padding: 0.15rem 0.65rem;
        border-radius: 99px;
        font-weight: 700;
        font-size: 0.88rem;
        white-space: nowrap;
    }

    /* Subtle divider between product rows */
    .row-divider {
        border: none;
        border-top: 1px solid #EEE;
        margin: 0.25rem 0;
    }

    /* Metric card accent */
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


def flatten_products(results: dict) -> list[dict]:
    rows = []
    for r in results["retailers"]:
        for p in r["products"]:
            rows.append(
                {
                    "Retailer": r["name"],
                    "Product": p.get("product_name", ""),
                    "Price": p.get("price", ""),
                    "Deal Details": p.get("deal_details", "") or "—",
                    "Flyer": p.get("flyer_title", ""),
                    "Page": p.get("page_number", ""),
                    "Flyer URL": p.get("flyer_url", ""),
                }
            )
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
        help="Downloads and analyzes the latest Ontario flyer images via Claude Vision.",
    )

    st.divider()
    st.markdown("**Retailers monitored (Ontario)**")
    for r in RETAILERS:
        st.caption(f"• {r['name']}")

    st.divider()
    st.caption(
        "Flyers sourced from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · "
        "Product extraction powered by Claude Vision"
    )


# ── Banner ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="th-banner">'
    "<h1>☕ Tim Hortons Flyer Scanner</h1>"
    "<p>Ontario grocery flyer monitor · Tracks Tim Hortons branded products across 8 major retailers</p>"
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
        "No scan data found. Click **Scan Flyers Now** in the sidebar to run the first scan.\n\n"
        "The scanner will:\n"
        "1. Fetch the current weekly Ontario flyer for each retailer\n"
        "2. Analyze every flyer page image using Claude Vision\n"
        "3. Extract all Tim Hortons products with prices and deal details"
    )
    st.stop()

# ── Flatten products ──────────────────────────────────────────────────────────
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
c1.metric("🛒 Tim Hortons Deals", len(all_products))
c2.metric("🏪 Retailers with Deals", f"{retailers_with_deals} / 8")
c3.metric("📰 Flyers Scanned", total_flyers)
c4.metric("📄 Pages Analyzed", total_pages)

st.divider()

# ── Retailer filter ───────────────────────────────────────────────────────────
all_retailer_names = [r["name"] for r in RETAILERS]
retailers_that_have_deals = sorted({p["Retailer"] for p in all_products})

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
        "No Tim Hortons products were found across this week's flyers.\n\n"
        "Possible reasons: Tim Hortons isn't on promotion this week, or the flyers "
        "haven't been published yet. Try refreshing on Thursday or Monday when new flyers post."
    )
elif not filtered:
    st.info("No products match the selected retailer filter.")
else:
    st.markdown(f"### Deals found — week of {results.get('scraped_at', '')[:10]}")

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
            label = f"🛒 **{r_name}** — {len(r_products)} Tim Hortons deal(s)"
        else:
            label = f"🛒 **{r_name}** — no deals found this week"

        with st.expander(label, expanded=bool(r_products)):
            if not r_products:
                if pages_scanned:
                    st.caption(
                        f"Scanned {pages_scanned} flyer page(s) — "
                        "no Tim Hortons products detected."
                    )
                else:
                    st.caption("No Ontario flyer found for this retailer.")
                continue

            # Column headers
            hcols = st.columns([4, 1.5, 2.5, 1.5])
            hcols[0].markdown("**Product**")
            hcols[1].markdown("**Price**")
            hcols[2].markdown("**Deal Details**")
            hcols[3].markdown("**Flyer**")
            st.markdown('<hr class="row-divider">', unsafe_allow_html=True)

            for p in r_products:
                cols = st.columns([4, 1.5, 2.5, 1.5])
                cols[0].markdown(f"{p['Product']}")
                cols[1].markdown(
                    f'<span class="price-pill">{p["Price"]}</span>',
                    unsafe_allow_html=True,
                )
                cols[2].caption(p["Deal Details"])
                cols[3].markdown(f"[View p.{p['Page']} ↗]({p['Flyer URL']})")
                st.markdown('<hr class="row-divider">', unsafe_allow_html=True)

# ── CSV export ────────────────────────────────────────────────────────────────
if all_products:
    st.divider()
    df = pd.DataFrame(all_products).drop(columns=["Flyer URL", "Flyer"])
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    scan_date = results["scraped_at"][:10]

    st.download_button(
        label="⬇ Download Results as CSV",
        data=csv_bytes,
        file_name=f"tim_hortons_deals_{scan_date}.csv",
        mime="text/csv",
        help="Exports all Tim Hortons deals found in this scan.",
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Tim Hortons Canada CPG Team · "
    "Data sourced from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · "
    "Runs every Monday for the upcoming week's flyers"
)
