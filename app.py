"""
Tim Hortons Flyer Tracker — Streamlit UI
"""
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from scraper import (
    run_historical_scan,
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
# Inline monogram — no external image dependency, always renders
TH_MONOGRAM_HTML = (
    '<div style="width:54px;height:54px;background:white;border-radius:50%;'
    'display:flex;align-items:center;justify-content:center;flex-shrink:0;'
    'font-family:Georgia,serif;font-size:1.45rem;font-weight:800;color:#C8102E;'
    'box-shadow:0 1px 4px rgba(0,0,0,0.18);">TH</div>'
)

# Static SVG logos served by Streamlit's static file server
_LOGO_SLUGS = {
    "Walmart":       "walmart",
    "Sobeys":        "sobeys",
    "No Frills":     "nofrills",
    "FreshCo":       "freshco",
    "RCSS":          "rcss",
    "Loblaws":       "loblaws",
    "Metro":         "metro",
    "Food Basics":   "foodbasics",
    "Canadian Tire": "canadiantire",
}

# Text fallback (used in onerror and anywhere images can't render)
RETAILER_LOGO_HTML = {
    "Walmart":
        '<span style="color:#0071CE;font-weight:800;font-size:0.92rem;">'
        'Walmart <span style="color:#FFC220;">✱</span></span>',
    "Sobeys":
        '<span style="color:#00703C;font-weight:700;font-style:italic;font-size:0.92rem;">Sobeys</span>',
    "No Frills":
        '<span style="background:#003087;color:white;font-weight:900;font-size:0.82rem;'
        'padding:2px 6px;border-radius:3px;display:inline-block;">NOFRILLS</span>',
    "FreshCo":
        '<span style="background:#5C7A1A;color:white;font-weight:900;font-size:0.82rem;'
        'padding:2px 7px;border-radius:3px;display:inline-block;">FRESH CO</span>',
    "RCSS":
        '<span style="color:#003087;font-weight:700;font-size:0.82rem;">Real Canadian Superstore</span>',
    "Loblaws":
        '<span style="color:#5C1A1A;font-weight:700;font-size:0.92rem;">Loblaws</span>',
    "Metro":
        '<span style="color:#CC0000;font-weight:900;font-size:0.95rem;">metro</span>',
    "Food Basics":
        '<span style="background:#2E8B2E;color:#FFD700;font-weight:900;font-size:0.82rem;'
        'padding:2px 6px;border-radius:3px;display:inline-block;">food Basics</span>',
    "Canadian Tire":
        '<span style="color:#CC0000;font-weight:700;font-size:0.9rem;">Canadian Tire</span>',
}


def retailer_img(name: str, height: int = 32) -> str:
    """Return an <img> tag using the static SVG logo, with text fallback."""
    slug = _LOGO_SLUGS.get(name)
    if slug:
        url = f"/app/static/logos/{slug}.svg"
        fb = RETAILER_LOGO_HTML.get(name, name).replace('"', "'")
        return (
            f'<img src="{url}" alt="{name}" height="{height}" '
            f'style="max-width:160px;object-fit:contain;vertical-align:middle;" '
            f'onerror="this.outerHTML=\'{fb}\';">'
        )
    return RETAILER_LOGO_HTML.get(name, name)

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


def run_with_progress() -> None:
    bar = st.progress(0.0)
    status = st.empty()

    def cb(msg: str, pct: float) -> None:
        status.text(msg)
        bar.progress(min(float(pct), 1.0))

    run_historical_scan(n_weeks=8, progress_callback=cb)
    bar.progress(1.0)
    status.success("Scan complete!")


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
/* ── TH Header ── */
.th-header {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    background: linear-gradient(135deg, #C8102E 0%, #7D0A1E 100%);
    padding: 1.1rem 1.8rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 8px rgba(200,16,46,0.25);
}
.th-title h1 {
    margin: 0;
    color: #fff;
    font-size: 1.7rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.15;
}
.th-title p {
    margin: 0.2rem 0 0;
    color: rgba(255,255,255,0.78);
    font-size: 0.88rem;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: #FFF5F7;
    border: 1px solid #F5D0D8;
    border-left: 4px solid #C8102E;
    border-radius: 10px;
    padding: 0.85rem 1rem !important;
}
[data-testid="stMetricValue"] { color: #C8102E; font-weight: 800; }
[data-testid="stMetricLabel"] { color: #666; font-size: 0.82rem; }

/* ── Retailer scorecard ── */
.scorecard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.25rem;
}
.scorecard {
    background: #fff;
    border: 1px solid #EEE;
    border-radius: 10px;
    padding: 0.75rem 0.5rem;
    text-align: center;
    min-height: 72px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
}
.scorecard-badge {
    display: inline-block;
    background: #C8102E;
    color: #fff;
    border-radius: 99px;
    padding: 0.1rem 0.55rem;
    font-size: 0.72rem;
    font-weight: 700;
}
.scorecard-none {
    display: inline-block;
    background: #F0F0F0;
    color: #999;
    border-radius: 99px;
    padding: 0.1rem 0.55rem;
    font-size: 0.72rem;
}

/* ── Price pill ── */
.price-pill {
    background: #C8102E;
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
    background: #FFF0F3;
    color: #C8102E;
    border: 1px solid #F5C0C8;
    border-radius: 99px;
    padding: 0.1rem 0.55rem;
    font-size: 0.78rem;
    font-weight: 600;
}

/* ── Week deal table ── */
.deal-table-wrap { margin-top: 1rem; }
.deal-table-hdr {
    display: grid;
    grid-template-columns: 1.3fr 1.8fr 0.9fr 1.2fr 1.8fr 0.8fr;
    gap: 0.5rem;
    align-items: center;
    padding: 0.4rem 0.75rem;
    background: #F8F8F8;
    border-radius: 8px 8px 0 0;
    font-size: 0.75rem;
    font-weight: 700;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.deal-table-row {
    display: grid;
    grid-template-columns: 1.3fr 1.8fr 0.9fr 1.2fr 1.8fr 0.8fr;
    gap: 0.5rem;
    align-items: center;
    padding: 0.55rem 0.75rem;
    border-bottom: 1px solid #F2F2F2;
    font-size: 0.87rem;
}
.deal-table-row:last-child { border-bottom: none; }
.deal-table-row:hover { background: #FFF5F7; }
.deal-table-wrap-inner {
    border: 1px solid #EEE;
    border-top: none;
    border-radius: 0 0 8px 8px;
    overflow: hidden;
}
.deal-link {
    color: #C8102E;
    font-weight: 600;
    text-decoration: none;
    font-size: 0.82rem;
}
.deal-link:hover { text-decoration: underline; }

/* ── Shared HTML table (history + insights) ── */
.th-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
.th-table th {
    background: #F8F8F8;
    font-size: 0.74rem;
    font-weight: 700;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.45rem 0.75rem;
    text-align: left;
    border-bottom: 2px solid #EEE;
    white-space: nowrap;
}
.th-table td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #F2F2F2;
    font-size: 0.87rem;
    vertical-align: middle;
}
.th-table tr:hover td { background: #FFF5F7; }
.th-table-wrap {
    overflow-x: auto;
    border: 1px solid #EEE;
    border-radius: 8px;
    max-height: 540px;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="text-align:center;padding:0.5rem 0 1rem;">'
        '<div style="width:72px;height:72px;background:#C8102E;border-radius:50%;'
        'display:inline-flex;align-items:center;justify-content:center;'
        'font-family:Georgia,serif;font-size:1.85rem;font-weight:800;color:white;'
        'box-shadow:0 2px 8px rgba(200,16,46,0.4);">TH</div>'
        '</div>',
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
        st.info("No history yet — click **Scan New Flyers** to start.")

    scan_btn = st.button("🔄 Scan New Flyers", type="primary", use_container_width=True)

    with st.expander("⚙ Advanced"):
        force_rescan = st.checkbox(
            "Ignore registry (rescan everything)", value=False,
            help="Forces re-analysis of all flyers, even if already scanned."
        )

    st.divider()
    st.markdown("**Retailers monitored (Ontario)**")
    for r in RETAILERS:
        st.caption(f"• {r['name']}")
    st.divider()
    st.caption("Data from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · Claude Sonnet 4.6")


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="th-header">'
    f'  {TH_MONOGRAM_HTML}'
    f'  <div class="th-title">'
    f'    <h1>Flyer Price Tracker</h1>'
    f'    <p>Ontario retail monitor — updated weekly</p>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Scan handler ──────────────────────────────────────────────────────────────
if scan_btn:
    if force_rescan:
        from scraper import save_scanned_registry
        save_scanned_registry(set())
    with st.spinner("Scanning flyers — this may take several minutes…"):
        run_with_progress()
    st.rerun()

if not history:
    st.info(
        "No scan data found.\n\n"
        "Click **Scan New Flyers** in the sidebar to build 8 weeks of history."
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
            f'  <div>{retailer_img(r["name"], height=30)}</div>'
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
                f'  <div>{retailer_img(p["Retailer"], height=28)}</div>'
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
        st.info("No product history yet. Run a scan first.")
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
                f'<td>{retailer_img(row["Retailer"], height=28)}</td>'
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
        st.info("No data yet. Run a scan first.")
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
                f'<td>{retailer_img(row["Retailer"], height=28)}</td>'
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
            use_container_width=True,
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
        st.dataframe(styled, use_container_width=True)
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
