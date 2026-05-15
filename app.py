"""
Tim Hortons Flyer Tracker — Streamlit UI
"""
import html
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from scraper import (
    load_all_history,
    load_scanned_registry,
    format_week_label,
    RETAILERS,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tim Hortons Flyer Tracker",
    page_icon="☕",
    layout="wide",
)

# ── Brand constants ───────────────────────────────────────────────────────────
RETAILER_ACCENTS = {
    "Walmart":       "#0071CE",
    "Sobeys":        "#0B8F2A",
    "No Frills":     "#E31B23",
    "FreshCo":       "#5B8F22",
    "RCSS":          "#004A98",
    "Loblaws":       "#D71920",
    "Metro":         "#E31B23",
    "Food Basics":   "#16803A",
    "Canadian Tire": "#E31B23",
}

LOGO_PATH = Path(__file__).parent / "assets" / "tim-hortons-logo.svg"


def load_tims_logo_svg() -> str:
    try:
        return LOGO_PATH.read_text(encoding="utf-8")
    except OSError:
        return '<span class="logo-text-fallback">Tim Hortons</span>'


TIM_HORTONS_LOGO_SVG = load_tims_logo_svg()


def retailer_label(name: str, class_name: str = "retailer-name") -> str:
    """Return a styled retailer text label."""
    safe_name = html.escape(name, quote=True)
    accent = RETAILER_ACCENTS.get(name, "#C8102E")
    return (
        f'<span class="{class_name}" style="--retailer-color:{accent};">'
        f'{safe_name}</span>'
    )

CATEGORY_RULES = [
    ("Single Serve",   ["k-cup", "kcup", "pod", "capsule", "single serve"]),
    ("Instant",        ["instant"]),
    ("Soup",           ["soup", "broth"]),
    ("Hot Beverages",  ["hot chocolate", "french vanilla", "tea", "latte", "cappuccino", "steeped"]),
    ("Roast & Ground", ["ground", "whole bean", "roast", "blend"]),
]
ALL_CATEGORIES = ["Roast & Ground", "Single Serve", "Instant", "Hot Beverages", "Soup", "Other"]

SIZE_RE = re.compile(
    r'\b(\d+(?:\.\d+)?\s*(?:g|kg|mL|L|oz|pk|pack|ct|count|lb))\b', re.IGNORECASE
)


# ── Utilities ─────────────────────────────────────────────────────────────────
def classify(name: str) -> str:
    n = name.lower()
    for cat, kws in CATEGORY_RULES:
        if any(k in n for k in kws):
            return cat
    return "Other"


def extract_size(name: str) -> str:
    m = SIZE_RE.search(name)
    return m.group(1).strip() if m else "—"


def fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return d


def fmt_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%b %d, %Y")
    except Exception:
        return iso


def build_full_df(history: list[dict]) -> pd.DataFrame:
    rows = []
    for wd in history:
        ws  = wd.get("week_start", "")
        we  = wd.get("week_end",   "")
        lbl = format_week_label(ws, we)
        for r in wd.get("retailers", []):
            for p in r.get("products", []):
                name = p.get("product_name", "")
                rows.append({
                    "week_start": ws,
                    "Week":       lbl,
                    "Retailer":   r["name"],
                    "Product":    name,
                    "Size":       extract_size(name),
                    "Category":   classify(name),
                    "Price":      p.get("price", ""),
                    "Comments":   p.get("deal_details", "") or "—",
                    "Start":      fmt_date(ws),
                    "End":        fmt_date(we),
                    "View":       p.get("page_url", p.get("flyer_url", "")),
                })
    cols = ["week_start", "Week", "Retailer", "Product", "Size", "Category",
            "Price", "Comments", "Start", "End", "View"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
    --th-red: #C8102E;
    --th-rich-red: #5A111C;
    --th-warm-red: #8B1E2D;
    --th-espresso: #351B1B;
    --th-chocolate: #6F2D25;
    --th-maple: #9B6338;
    --th-cream: #EFE1D1;
    --th-vanilla: #DFCDA3;
    --th-white: #FFFDF8;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at top left, rgba(200,16,46,0.12), transparent 32rem),
        linear-gradient(180deg, #FFF8F1 0%, var(--th-cream) 100%);
}
[data-testid="stHeader"] {
    background: rgba(255, 248, 241, 0.82);
}
.block-container {
    padding-top: 2.35rem;
    padding-bottom: 2.4rem;
}
html, body, [class*="css"] {
    font-family: "Aptos", "Segoe UI", Arial, sans-serif;
    color: var(--th-espresso);
}
div[data-testid="stSidebarContent"] {
    background: #FFF8F1;
    border-right: 1px solid rgba(111,45,37,0.14);
}
section[data-testid="stSidebar"] {
    background: #FFF8F1;
}
/* ── TH Header ── */
.th-header {
    overflow: hidden;
    background: rgba(255,253,248,0.92);
    color: #fff;
    border: 1px solid rgba(111,45,37,0.14);
    border-radius: 12px;
    margin: 0.35rem 0 1.45rem;
    box-shadow: 0 16px 34px rgba(90,17,28,0.13);
}
.brand-lockup {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    min-width: 0;
}
.th-hero {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    width: 100%;
    padding: 1.35rem 1.45rem 1.45rem;
    background:
        radial-gradient(circle at top right, rgba(200,16,46,0.28), transparent 28rem),
        linear-gradient(135deg, rgba(90,17,28,0.98), rgba(139,30,45,0.94));
    border-left: 8px solid var(--th-red);
}
.brand-kicker {
    margin-bottom: 0.18rem;
    color: var(--th-vanilla);
    font-size: 0.72rem;
    font-weight: 850;
    letter-spacing: 0.11em;
    text-transform: uppercase;
}
.th-title {
    min-width: 0;
}
.headline-lockup {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.85rem;
}
.headline-logo {
    display: inline-flex;
    align-items: center;
    width: min(240px, 42vw);
    max-width: 100%;
    padding: 0.46rem 0.7rem 0.38rem;
    background: #fff;
    border: 1px solid rgba(255,255,255,0.62);
    border-radius: 10px;
    box-shadow: 0 10px 22px rgba(53,27,27,0.16);
}
.headline-logo svg,
.sidebar-logo svg {
    display: block;
    width: 100%;
    height: auto;
}
.logo-text-fallback {
    color: var(--th-red);
    font-weight: 900;
}
.th-title h1 {
    margin: 0.12rem 0 0;
    color: #fff;
    font-size: 2rem;
    font-weight: 900;
    letter-spacing: 0;
    line-height: 1.15;
}
.th-title p {
    margin: 0.35rem 0 0;
    color: rgba(255,255,255,0.84);
    font-size: 0.95rem;
    font-weight: 650;
    max-width: 760px;
}
.header-stat {
    flex: 0 0 auto;
    color: #fff;
    border: 1px solid rgba(255,255,255,0.28);
    border-radius: 10px;
    min-width: 128px;
    background: rgba(255,255,255,0.14);
    padding: 0.48rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 800;
}
.header-stat span {
    display: block;
    color: rgba(255,255,255,0.7);
    font-size: 0.66rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.header-stat strong {
    display: block;
    margin-top: 0.1rem;
    color: #fff;
    font-size: 1rem;
}
.sidebar-brand {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    padding: 0;
    overflow: hidden;
    background: #fff;
    border: 1px solid rgba(111,45,37,0.14);
    border-radius: 12px;
    box-shadow: 0 10px 24px rgba(53,27,27,0.06);
}
.sidebar-brand-row {
    display: flex;
    align-items: flex-start;
    flex-direction: column;
    gap: 0.45rem;
    padding: 0.9rem 0.85rem 0.65rem;
    background: #fff;
    color: var(--th-espresso);
    border-bottom: 1px solid rgba(111,45,37,0.12);
}
.sidebar-logo {
    width: 156px;
    max-width: 100%;
}
.sidebar-kicker {
    color: var(--th-red);
    font-size: 0.66rem;
    font-weight: 850;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.sidebar-subtitle {
    color: var(--th-espresso);
    font-size: 0.82rem;
    font-weight: 700;
    padding: 0 0.85rem 0.85rem;
}
.sidebar-retailer-list {
    display: grid;
    gap: 0.45rem;
    margin: 0.3rem 0 0.6rem;
}
.sidebar-retailer-row {
    display: flex;
    align-items: center;
    min-height: 26px;
    padding: 0.35rem 0.55rem;
    background: #fff;
    border: 1px solid rgba(111,45,37,0.12);
    border-radius: 8px;
}
.retailer-name {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--th-espresso);
    font-size: 0.9rem;
    font-weight: 800;
    line-height: 1.2;
    white-space: nowrap;
}
.retailer-name::before {
    content: "";
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 999px;
    background: var(--retailer-color, #C8102E);
    flex: 0 0 auto;
}
.sidebar-retailer-row .retailer-name {
    font-size: 0.82rem;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: var(--th-white);
    border: 1px solid rgba(111,45,37,0.14);
    border-top: 4px solid var(--th-red);
    border-radius: 12px;
    padding: 0.95rem 1rem !important;
    box-shadow: 0 10px 22px rgba(53,27,27,0.06);
}
[data-testid="stMetricValue"] { color: var(--th-red); font-weight: 900; }
[data-testid="stMetricLabel"] {
    color: var(--th-chocolate);
    font-size: 0.82rem;
    font-weight: 850;
}

/* ── Retailer scorecard ── */
.scorecard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.25rem;
}
.scorecard {
    background: var(--th-white);
    border: 1px solid rgba(111,45,37,0.14);
    border-radius: 8px;
    padding: 0.75rem 0.5rem;
    text-align: center;
    min-height: 86px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    box-shadow: 0 6px 14px rgba(53,27,27,0.04);
}
.scorecard-retailer {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 32px;
}
.scorecard-retailer .retailer-name {
    font-size: 0.96rem;
    font-weight: 800;
}
.deal-table-row .retailer-name,
.th-table .retailer-name {
    font-size: 0.86rem;
}
.scorecard-badge {
    display: inline-block;
    background: var(--th-red);
    color: #fff;
    border-radius: 99px;
    padding: 0.1rem 0.55rem;
    font-size: 0.72rem;
    font-weight: 700;
}
.scorecard-none {
    display: inline-block;
    background: #F5E9DD;
    color: #8A6D5C;
    border-radius: 99px;
    padding: 0.1rem 0.55rem;
    font-size: 0.72rem;
}

/* ── Price pill ── */
.price-pill {
    background: var(--th-red);
    color: #fff;
    padding: 0.15rem 0.6rem;
    border-radius: 99px;
    font-size: 0.82rem;
    font-weight: 700;
    white-space: nowrap;
}

/* ── Category pill ── */
.cat-pill {
    display: inline-block;
    background: #FFF4EA;
    color: var(--th-chocolate);
    border: 1px solid rgba(155,99,56,0.22);
    border-radius: 99px;
    padding: 0.1rem 0.55rem;
    font-size: 0.78rem;
    font-weight: 600;
}

/* ── Week deal table ── */
.deal-table-wrap { margin-top: 1rem; }
.deal-table-hdr {
    display: grid;
    grid-template-columns: minmax(124px, 0.9fr) 1.8fr 0.8fr 1fr 1.7fr 0.75fr;
    gap: 0.5rem;
    align-items: center;
    padding: 0.4rem 0.75rem;
    background: var(--th-rich-red);
    border-radius: 8px 8px 0 0;
    font-size: 0.75rem;
    font-weight: 700;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.deal-table-row {
    display: grid;
    grid-template-columns: minmax(124px, 0.9fr) 1.8fr 0.8fr 1fr 1.7fr 0.75fr;
    gap: 0.5rem;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: var(--th-white);
    border-bottom: 1px solid rgba(111,45,37,0.10);
    font-size: 0.87rem;
}
.deal-table-row:last-child { border-bottom: none; }
.deal-table-row:hover { background: #FFF4EA; }
.deal-table-wrap-inner {
    border: 1px solid rgba(111,45,37,0.14);
    border-top: none;
    border-radius: 0 0 8px 8px;
    overflow: hidden;
}
.deal-link {
    color: var(--th-red);
    font-weight: 800;
    text-decoration: none;
    font-size: 0.82rem;
}
.deal-link:hover { text-decoration: underline; }

/* ── Shared HTML table (history + insights) ── */
.th-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
.th-table th {
    background: var(--th-rich-red);
    font-size: 0.74rem;
    font-weight: 700;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.45rem 0.75rem;
    text-align: left;
    border-bottom: 2px solid rgba(53,27,27,0.12);
    white-space: nowrap;
}
.th-table td {
    padding: 0.48rem 0.75rem;
    border-bottom: 1px solid rgba(111,45,37,0.10);
    font-size: 0.87rem;
    vertical-align: middle;
}
.th-table td:first-child {
    width: 130px;
}
.th-table tr:hover td { background: #FFF4EA; }
.th-table-wrap {
    overflow-x: auto;
    border: 1px solid rgba(111,45,37,0.14);
    border-radius: 8px;
    background: var(--th-white);
    box-shadow: 0 8px 20px rgba(53,27,27,0.05);
    max-height: 540px;
    overflow-y: auto;
}
@media (max-width: 780px) {
    .th-hero {
        align-items: flex-start;
        flex-direction: column;
    }
    .headline-lockup {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.55rem;
    }
    .headline-logo {
        width: min(220px, 78vw);
    }
    .th-title h1 {
        font-size: 1.55rem;
    }
    .header-stat {
        width: 100%;
    }
    .deal-table-hdr,
    .deal-table-row {
        grid-template-columns: minmax(116px, 1fr) minmax(180px, 1.4fr) 80px 90px minmax(160px, 1.2fr) 70px;
    }
}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="sidebar-brand">'
        f'  <div class="sidebar-brand-row">'
        f'    <div class="sidebar-logo">{TIM_HORTONS_LOGO_SVG}</div>'
        f'    <div class="sidebar-kicker">CPG Tracker</div>'
        f'  </div>'
        f'  <div class="sidebar-subtitle">Flyer price intelligence</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    history = load_all_history()
    scanned_count = len(load_scanned_registry())

    if history:
        latest_ts = max(w.get("scraped_at", "") for w in history)
        st.success(
            f"**{len(history)} week(s)** in history\n\n"
            f"Last scan: {fmt_ts(latest_ts)}"
        )
        st.caption(f"{scanned_count} flyer(s) in registry")
    else:
        st.info("No history yet. Add weekly JSON files under `data/history` to populate the dashboard.")

    st.caption("Manual update mode: scan results are added through weekly history files.")

    st.divider()
    st.markdown("**Retailers monitored (Ontario)**")
    sidebar_retailers = "".join(
        f'<div class="sidebar-retailer-row">{retailer_label(r["name"])}</div>'
        for r in RETAILERS
    )
    st.markdown(
        f'<div class="sidebar-retailer-list">{sidebar_retailers}</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Data from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · Claude Sonnet 4.6")


# ── Header ────────────────────────────────────────────────────────────────────
latest_cycle = (
    format_week_label(history[0].get("week_start", ""), history[0].get("week_end"))
    if history else "No history loaded"
)
st.markdown(
    f'<div class="th-header">'
    f'  <div class="th-hero">'
    f'    <div class="brand-lockup">'
    f'      <div class="th-title">'
    f'        <div class="brand-kicker">SmartCanucks weekly flyer monitor</div>'
    f'        <h1 class="headline-lockup"><span class="headline-logo">{TIM_HORTONS_LOGO_SVG}</span><span>Flyer Price Tracker</span></h1>'
    f'        <p>Track Tim Hortons CPG placements, pricing, and retailer activity across Ontario flyers.</p>'
    f'      </div>'
    f'    </div>'
    f'    <div class="header-stat"><span>Latest cycle</span><strong>{latest_cycle}</strong></div>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)

if not history:
    st.info(
        "No scan data found.\n\n"
        "Add weekly JSON files to `data/history` to populate this dashboard."
    )
    st.stop()

# ── Global dataframe ──────────────────────────────────────────────────────────
full_df = build_full_df(history)
week_labels = [
    format_week_label(w.get("week_start", ""), w.get("week_end"))
    for w in history
]

total_products = len(full_df)
weeks_tracked  = len(history)
total_pages    = sum(
    f.get("pages_scanned", 0)
    for w in history
    for r in w.get("retailers", [])
    for f in r.get("flyers", [])
)

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total TH Deals Found", total_products)
c2.metric("Weeks of History",      weeks_tracked)
c3.metric("Retailers Scanned",     len(RETAILERS))
c4.metric("Pages Analyzed",        f"{total_pages:,}")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_weekly, tab_history, tab_insights = st.tabs([
    "📅  Weekly Review",
    "🔍  Product History",
    "📊  Flyer Insights",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — WEEKLY REVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_weekly:
    col_week, col_retailer = st.columns([2, 3])

    with col_week:
        selected_week_label = st.selectbox(
            "Flyer Cycle", options=week_labels, index=0, key="wk_week"
        )

    week_data = next(
        (w for w in history
         if format_week_label(w.get("week_start", ""), w.get("week_end")) == selected_week_label),
        None,
    )

    week_products: list[dict] = []
    if week_data:
        for r in week_data.get("retailers", []):
            for p in r.get("products", []):
                week_products.append({
                    "Retailer":     r["name"],
                    "Product":      p.get("product_name", ""),
                    "Size":         extract_size(p.get("product_name", "")),
                    "Price":        p.get("price", ""),
                    "Deal Details": p.get("deal_details", "") or "—",
                    "Page":         p.get("page_number", ""),
                    "View":         p.get("page_url", p.get("flyer_url", "")),
                })

    with col_retailer:
        selected_retailers = st.multiselect(
            "Retailer", options=[r["name"] for r in RETAILERS],
            default=[r["name"] for r in RETAILERS], key="wk_retailer",
        )

    filtered_week = [p for p in week_products if p["Retailer"] in selected_retailers]

    if week_data:
        scraped_at = week_data.get("scraped_at", "")
        st.caption(
            f"**{selected_week_label}** · "
            f"Scanned {fmt_ts(scraped_at) if scraped_at else 'unknown'} · "
            f"{len(filtered_week)} deal(s)"
        )

    # ── Retailer scorecard grid ───────────────────────────────────────────────
    deal_counts: dict[str, int] = {}
    for p in filtered_week:
        deal_counts[p["Retailer"]] = deal_counts.get(p["Retailer"], 0) + 1

    scorecard_items = ""
    for r in RETAILERS:
        if r["name"] not in selected_retailers:
            continue
        n = deal_counts.get(r["name"], 0)
        badge = (
            f'<span class="scorecard-badge">{n} deal{"s" if n != 1 else ""}</span>'
            if n > 0 else
            '<span class="scorecard-none">No deals</span>'
        )
        scorecard_items += (
            f'<div class="scorecard">'
            f'  <div class="scorecard-retailer">{retailer_label(r["name"])}</div>'
            f'  {badge}'
            f'</div>'
        )

    st.markdown(
        f'<div class="scorecard-grid">{scorecard_items}</div>',
        unsafe_allow_html=True,
    )

    # ── Deal table ────────────────────────────────────────────────────────────
    if filtered_week:
        rows_html = ""
        for p in filtered_week:
            rows_html += (
                f'<div class="deal-table-row">'
                f'  <div>{retailer_label(p["Retailer"])}</div>'
                f'  <span>{p["Product"]}</span>'
                f'  <span style="color:#666;">{p["Size"]}</span>'
                f'  <span><span class="price-pill">{p["Price"]}</span></span>'
                f'  <span style="color:#555;font-size:0.82rem;">{p["Deal Details"]}</span>'
                f'  <a class="deal-link" href="{p["View"]}" target="_blank">Page {p["Page"]} ↗</a>'
                f'</div>'
            )

        st.markdown(
            '<div class="deal-table-wrap">'
            '  <div class="deal-table-hdr">'
            '    <span>Retailer</span>'
            '    <span>Product</span>'
            '    <span>Size</span>'
            '    <span>Price</span>'
            '    <span>Deal Details</span>'
            '    <span>Flyer</span>'
            '  </div>'
            f'  <div class="deal-table-wrap-inner">{rows_html}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        df_week = pd.DataFrame(filtered_week)
        st.download_button(
            "⬇ Download This Week as CSV",
            data=df_week.to_csv(index=False).encode("utf-8"),
            file_name=f"tim_hortons_{selected_week_label.replace(' ', '_').replace('–', 'to')}.csv",
            mime="text/csv",
            key="csv_weekly",
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PRODUCT HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    if full_df.empty:
        st.info("No product history yet. Add weekly JSON files to `data/history` first.")
        st.stop()

    # ── Filters ──────────────────────────────────────────────────────────────
    hc1, hc2, hc3, hc4 = st.columns([2, 2, 2, 3])
    with hc1:
        sel_weeks = st.multiselect(
            "Flyer Cycle(s)", options=week_labels, default=week_labels, key="h_weeks"
        )
    with hc2:
        sel_retailers = st.multiselect(
            "Retailer(s)", options=[r["name"] for r in RETAILERS],
            default=[r["name"] for r in RETAILERS], key="h_retailers",
        )
    with hc3:
        sel_cats = st.multiselect(
            "Category", options=ALL_CATEGORIES, default=ALL_CATEGORIES, key="h_cats"
        )
    with hc4:
        search_q = st.text_input(
            "🔍 Search Products",
            placeholder="e.g. K-Cup, Dark Roast, Ground Coffee…",
            key="h_search",
        )

    fdf = full_df.copy()
    if sel_weeks:
        fdf = fdf[fdf["Week"].isin(sel_weeks)]
    if sel_retailers:
        fdf = fdf[fdf["Retailer"].isin(sel_retailers)]
    if sel_cats:
        fdf = fdf[fdf["Category"].isin(sel_cats)]
    if search_q.strip():
        fdf = fdf[fdf["Product"].str.contains(search_q.strip(), case=False, na=False)]

    fdf = fdf.sort_values("week_start", ascending=False).reset_index(drop=True)
    st.caption(f"{len(fdf)} deal(s) match the current filters")

    if fdf.empty:
        st.info("No results match the current filters.")
    else:
        rows_html = ""
        for _, row in fdf.iterrows():
            rows_html += (
                f'<tr>'
                f'<td>{retailer_label(row["Retailer"])}</td>'
                f'<td>{row["Product"]}</td>'
                f'<td style="color:#666;">{row["Size"]}</td>'
                f'<td><span class="cat-pill">{row["Category"]}</span></td>'
                f'<td><span class="price-pill">{row["Price"]}</span></td>'
                f'<td style="color:#555;font-size:0.82rem;">{row["Comments"]}</td>'
                f'<td style="color:#888;font-size:0.82rem;white-space:nowrap;">{row["Start"]}</td>'
                f'<td style="color:#888;font-size:0.82rem;white-space:nowrap;">{row["End"]}</td>'
                f'<td><a class="deal-link" href="{row["View"]}" target="_blank">View ↗</a></td>'
                f'</tr>'
            )

        st.markdown(
            '<div class="th-table-wrap">'
            '<table class="th-table">'
            '<thead><tr>'
            '<th>Retailer</th><th>Product</th><th>Size</th><th>Category</th>'
            '<th>Price</th><th>Deal Details</th><th>Sale Start</th><th>Sale End</th><th>Flyer</th>'
            '</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            '</table></div>',
            unsafe_allow_html=True,
        )

        st.download_button(
            "⬇ Download Filtered History as CSV",
            data=fdf[["Week", "Retailer", "Product", "Size", "Category",
                       "Price", "Comments", "Start", "End", "View"]].to_csv(index=False).encode("utf-8"),
            file_name="tim_hortons_flyer_history.csv",
            mime="text/csv",
            key="csv_history",
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — FLYER INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_insights:
    if full_df.empty:
        st.info("No data yet. Add weekly JSON files to `data/history` first.")
        st.stop()

    # ── Time window filter ───────────────────────────────────────────────────
    TIME_OPTIONS: dict[str, int | None] = {
        "L12 Weeks": 12,
        "L26 Weeks": 26,
        "L52 Weeks": 52,
        "All Available": None,
    }
    time_sel = st.radio(
        "Time Window",
        list(TIME_OPTIONS.keys()),
        index=3,
        horizontal=True,
        key="ins_time",
        label_visibility="collapsed",
    )
    n_weeks_filter = TIME_OPTIONS[time_sel]
    if n_weeks_filter is not None:
        cutoff = (datetime.today() - timedelta(weeks=n_weeks_filter)).strftime("%Y-%m-%d")
        ins_df = full_df[full_df["week_start"] >= cutoff].copy()
    else:
        ins_df = full_df.copy()

    st.caption(
        f"Showing **{len(ins_df)}** deal(s) across "
        f"**{ins_df['week_start'].nunique() if not ins_df.empty else 0}** week(s)"
    )

    if ins_df.empty:
        st.info("No data in this time window.")
        st.stop()

    # ── KPIs ─────────────────────────────────────────────────────────────────
    top_retailer = ins_df["Retailer"].value_counts().idxmax()
    top_category = ins_df["Category"].value_counts().idxmax()

    ic1, ic2, ic3, ic4 = st.columns(4)
    ic1.metric("Total TH Appearances",  len(ins_df))
    ic2.metric("Retailers with Deals",  ins_df["Retailer"].nunique())
    ic3.metric("Most Active Retailer",  top_retailer)
    ic4.metric("Top Product Category",  top_category)

    st.divider()

    left_col, right_col = st.columns([1, 1])

    # ── Deals by Retailer ────────────────────────────────────────────────────
    with left_col:
        st.markdown("#### 🏪 Deals by Retailer")

        retailer_counts = (
            ins_df.groupby("Retailer").size()
            .reset_index(name="Deals")
            .sort_values("Deals", ascending=False)
        )

        rows_html = ""
        for _, row in retailer_counts.iterrows():
            rows_html += (
                f'<tr>'
                f'<td>{retailer_label(row["Retailer"])}</td>'
                f'<td style="font-weight:700;color:#222;">{int(row["Deals"])}</td>'
                f'</tr>'
            )

        st.markdown(
            '<div class="th-table-wrap" style="max-height:340px;">'
            '<table class="th-table">'
            '<thead><tr><th>Retailer</th><th># Deals</th></tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            '</table></div>',
            unsafe_allow_html=True,
        )

    # ── Category Breakdown ───────────────────────────────────────────────────
    with right_col:
        st.markdown("#### 📦 Product Category Breakdown")

        cat_counts = (
            ins_df.groupby("Category").size()
            .reindex(ALL_CATEGORIES, fill_value=0)
            .reset_index()
        )
        cat_counts.columns = ["Category", "Count"]
        cat_counts = cat_counts[cat_counts["Count"] > 0]

        st.dataframe(
            cat_counts,
            column_config={
                "Category": st.column_config.TextColumn("Category"),
                "Count":    st.column_config.ProgressColumn(
                    "# of Deals",
                    min_value=0,
                    max_value=int(cat_counts["Count"].max()) if not cat_counts.empty else 1,
                    format="%d",
                ),
            },
            width="stretch",
            hide_index=True,
            height=68 + 40 * len(cat_counts),
        )

    st.divider()

    # ── Category × Retailer heatmap ───────────────────────────────────────────
    st.markdown("#### 🔥 Category × Retailer Summary")
    st.caption("Number of Tim Hortons deals found per category per retailer in the selected window.")

    pivot = (
        ins_df.groupby(["Category", "Retailer"]).size()
        .unstack(fill_value=0)
        .reindex(ALL_CATEGORIES, fill_value=0)
    )
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot[pivot["Total"] > 0]

    if not pivot.empty:
        max_val = pivot.drop(columns=["Total"]).values.max() or 1

        def _cell_color(val):
            if val == 0:
                return "background-color: #f5f5f5; color: #bbb;"
            intensity = int(200 - (val / max_val) * 160)
            return f"background-color: rgb(200,{intensity},{intensity}); color: #000;"

        numeric_cols = [c for c in pivot.columns if c != "Total"]
        _styler = pivot.style
        _applyfn = getattr(_styler, "map", None) or getattr(_styler, "applymap")
        styled = (
            _applyfn(_cell_color, subset=numeric_cols)
            .format("{:.0f}")
            .set_properties(**{"text-align": "center"})
        )
        st.dataframe(styled, width="stretch")
    else:
        st.info("Not enough data for breakdown.")


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    '<p style="text-align:center;font-size:0.8rem;color:#999;">'
    '☕ Tim Hortons Canada CPG Team &nbsp;·&nbsp; '
    'Data from <a href="https://flyers.smartcanucks.ca" target="_blank">SmartCanucks.ca</a>'
    ' &nbsp;·&nbsp; Powered by <strong>Claude Sonnet 4.6</strong> &amp; <strong>GPT Codex 5.5</strong>'
    '</p>',
    unsafe_allow_html=True,
)
