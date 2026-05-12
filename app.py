"""
Tim Hortons Flyer Tracker — Streamlit UI
"""
import re
import sys
from pathlib import Path
from datetime import datetime

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
TH_LOGO_URL = "https://upload.wikimedia.org/wikipedia/en/b/bf/Tim_Hortons_Logo.svg"

RETAILER_LOGOS = {
    "Walmart":       "https://www.google.com/s2/favicons?domain=walmart.ca&sz=64",
    "Sobeys":        "https://www.google.com/s2/favicons?domain=sobeys.com&sz=64",
    "No Frills":     "https://www.google.com/s2/favicons?domain=nofrills.ca&sz=64",
    "FreshCo":       "https://www.google.com/s2/favicons?domain=freshco.com&sz=64",
    "RCSS":          "https://www.google.com/s2/favicons?domain=realcanadiansuperstore.ca&sz=64",
    "Loblaws":       "https://www.google.com/s2/favicons?domain=loblaws.ca&sz=64",
    "Metro":         "https://www.google.com/s2/favicons?domain=metro.ca&sz=64",
    "Food Basics":   "https://www.google.com/s2/favicons?domain=foodbasics.ca&sz=64",
    "Canadian Tire": "https://www.google.com/s2/favicons?domain=canadiantire.ca&sz=64",
}

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
                    "Logo":       RETAILER_LOGOS.get(r["name"], ""),
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
    cols = ["week_start","Week","Logo","Retailer","Product","Size","Category",
            "Price","Comments","Start","End","View"]
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
.th-header img { height: 54px; }
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
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.25rem;
}
.scorecard {
    background: #fff;
    border: 1px solid #EEE;
    border-radius: 10px;
    padding: 0.75rem;
    text-align: center;
}
.scorecard img { height: 28px; width: 28px; object-fit: contain; border-radius: 4px; }
.scorecard-name { font-size: 0.75rem; color: #444; margin: 0.35rem 0 0.25rem; font-weight: 600; }
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

/* ── Week deal table ── */
.deal-table-wrap { margin-top: 1rem; }
.deal-table-hdr {
    display: grid;
    grid-template-columns: 40px 1fr 1.6fr 0.9fr 1.5fr 1.5fr 0.8fr;
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
    grid-template-columns: 40px 1fr 1.6fr 0.9fr 1.5fr 1.5fr 0.8fr;
    gap: 0.5rem;
    align-items: center;
    padding: 0.5rem 0.75rem;
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
.retailer-name-cell {
    font-weight: 600;
    color: #222;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.retailer-name-cell img {
    height: 20px;
    width: 20px;
    object-fit: contain;
    border-radius: 3px;
}
.deal-link {
    color: #C8102E;
    font-weight: 600;
    text-decoration: none;
    font-size: 0.82rem;
}
.deal-link:hover { text-decoration: underline; }

/* ── Insights ── */
.cat-pill {
    display: inline-block;
    background: #FFF0F3;
    color: #C8102E;
    border: 1px solid #F5C0C8;
    border-radius: 99px;
    padding: 0.15rem 0.65rem;
    font-size: 0.8rem;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    try:
        st.image(TH_LOGO_URL, width=160)
    except Exception:
        st.markdown("## ☕ Tim Hortons")
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
    f'  <img src="{TH_LOGO_URL}" alt="Tim Hortons">'
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

total_products  = len(full_df)
weeks_tracked   = len(history)
total_pages     = sum(
    f.get("pages_scanned", 0)
    for w in history
    for r in w.get("retailers", [])
    for f in r.get("flyers", [])
)

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total TH Deals Found",   total_products)
c2.metric("Weeks of History",        weeks_tracked)
c3.metric("Retailers Scanned",       len(RETAILERS))
c4.metric("Pages Analyzed",          f"{total_pages:,}")

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

    # Build product list for this week
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
    deal_counts = {}
    for p in filtered_week:
        deal_counts[p["Retailer"]] = deal_counts.get(p["Retailer"], 0) + 1

    scorecard_items = ""
    for r in RETAILERS:
        if r["name"] not in selected_retailers:
            continue
        logo = RETAILER_LOGOS.get(r["name"], "")
        n    = deal_counts.get(r["name"], 0)
        badge = (
            f'<span class="scorecard-badge">{n} deal{"s" if n!=1 else ""}</span>'
            if n > 0 else
            '<span class="scorecard-none">No deals</span>'
        )
        scorecard_items += (
            f'<div class="scorecard">'
            f'  <img src="{logo}" alt="{r["name"]}">'
            f'  <div class="scorecard-name">{r["name"]}</div>'
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
            logo = RETAILER_LOGOS.get(p["Retailer"], "")
            rows_html += (
                f'<div class="deal-table-row">'
                f'  <img src="{logo}" alt="{p["Retailer"]}" '
                f'       style="height:22px;width:22px;object-fit:contain;border-radius:3px;">'
                f'  <span class="retailer-name-cell" style="display:block;">{p["Retailer"]}</span>'
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
            '    <span></span>'
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
            file_name=f"tim_hortons_{selected_week_label.replace(' ','_').replace('–','to')}.csv",
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

    # Apply filters
    fdf = full_df.copy()
    if sel_weeks:     fdf = fdf[fdf["Week"].isin(sel_weeks)]
    if sel_retailers: fdf = fdf[fdf["Retailer"].isin(sel_retailers)]
    if sel_cats:      fdf = fdf[fdf["Category"].isin(sel_cats)]
    if search_q.strip():
        fdf = fdf[fdf["Product"].str.contains(search_q.strip(), case=False, na=False)]

    fdf = fdf.sort_values("week_start", ascending=False).reset_index(drop=True)

    st.caption(f"{len(fdf)} deal(s) match the current filters")

    if fdf.empty:
        st.info("No results match the current filters.")
    else:
        display_df = fdf[[
            "Logo", "Retailer", "Product", "Size", "Category",
            "Price", "Comments", "Start", "End", "View"
        ]].copy()

        st.dataframe(
            display_df,
            column_config={
                "Logo":     st.column_config.ImageColumn("", width="small"),
                "Retailer": st.column_config.TextColumn("Retailer", width="medium"),
                "Product":  st.column_config.TextColumn("Product"),
                "Size":     st.column_config.TextColumn("Size", width="small"),
                "Category": st.column_config.TextColumn("Category", width="medium"),
                "Price":    st.column_config.TextColumn("Price", width="small"),
                "Comments": st.column_config.TextColumn("Deal Details"),
                "Start":    st.column_config.TextColumn("Sale Start", width="medium"),
                "End":      st.column_config.TextColumn("Sale End",   width="medium"),
                "View":     st.column_config.LinkColumn(
                    "Flyer Page", display_text="View ↗", width="small"
                ),
            },
            use_container_width=True,
            hide_index=True,
            height=min(520, 68 + 40 * len(display_df)),
        )

        st.download_button(
            "⬇ Download Filtered History as CSV",
            data=fdf[[
                "Week", "Retailer", "Product", "Size", "Category",
                "Price", "Comments", "Start", "End", "View"
            ]].to_csv(index=False).encode("utf-8"),
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

    # ── KPIs ─────────────────────────────────────────────────────────────────
    top_retailer = full_df["Retailer"].value_counts().idxmax()
    top_category = full_df["Category"].value_counts().idxmax()

    ic1, ic2, ic3, ic4 = st.columns(4)
    ic1.metric("Total TH Appearances",   total_products)
    ic2.metric("Retailers with Deals",   full_df["Retailer"].nunique())
    ic3.metric("Most Active Retailer",   top_retailer)
    ic4.metric("Top Product Category",   top_category)

    st.divider()

    left_col, right_col = st.columns([1, 1])

    # ── Deals by Retailer ────────────────────────────────────────────────────
    with left_col:
        st.markdown("#### 🏪 Deals by Retailer")

        retailer_counts = (
            full_df.groupby("Retailer").size()
            .reset_index(name="Deals")
            .sort_values("Deals", ascending=False)
        )
        retailer_counts["Logo"] = retailer_counts["Retailer"].map(RETAILER_LOGOS)

        st.dataframe(
            retailer_counts[["Logo", "Retailer", "Deals"]],
            column_config={
                "Logo":     st.column_config.ImageColumn("", width="small"),
                "Retailer": st.column_config.TextColumn("Retailer"),
                "Deals":    st.column_config.NumberColumn("# Deals", format="%d"),
            },
            use_container_width=True,
            hide_index=True,
            height=68 + 40 * len(retailer_counts),
        )

    # ── Category Breakdown ───────────────────────────────────────────────────
    with right_col:
        st.markdown("#### 📦 Product Category Breakdown")

        cat_counts = (
            full_df.groupby("Category").size()
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

    # ── Category × Retailer heat map table ───────────────────────────────────
    st.markdown("#### 🔥 Category × Retailer Summary")
    st.caption("Number of Tim Hortons deals found per category per retailer, across all scanned weeks.")

    pivot = (
        full_df.groupby(["Category", "Retailer"]).size()
        .unstack(fill_value=0)
        .reindex(ALL_CATEGORIES, fill_value=0)
    )
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot[pivot["Total"] > 0]

    if not pivot.empty:
        # style: highlight non-zero cells in red gradient
        numeric_cols = [c for c in pivot.columns if c != "Total"]
        styled = (
            pivot.style
            .background_gradient(cmap="Reds", subset=numeric_cols, vmin=0)
            .format("{:.0f}")
            .set_properties(**{"text-align": "center"})
        )
        st.dataframe(styled, use_container_width=True)
    else:
        st.info("Not enough data for breakdown.")


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Tim Hortons Canada CPG Team · "
    "Data from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · "
    "Powered by Claude Sonnet 4.6"
)
