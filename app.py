"""
Tim Hortons Flyer Scanner — Streamlit UI
Weekly flyer monitor with full history, product search, and smart incremental scanning.
"""

import json
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
    get_past_week_starts,
    RETAILERS,
)

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

    .price-pill {
        display: inline-block;
        background: #C8102E;
        color: white;
        padding: 0.18rem 0.7rem;
        border-radius: 99px;
        font-weight: 700;
        font-size: 0.88rem;
        white-space: nowrap;
    }
    .row-divider {
        border: none;
        border-top: 1px solid #EEE;
        margin: 0.25rem 0;
    }
    [data-testid="metric-container"] {
        border-left: 3px solid #C8102E;
        padding-left: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def format_ts(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%b %d, %Y — %I:%M %p")


def run_with_progress() -> list[dict]:
    bar    = st.progress(0.0)
    status = st.empty()

    def cb(msg: str, pct: float) -> None:
        status.text(msg)
        bar.progress(min(float(pct), 1.0))

    results = run_historical_scan(n_weeks=8, progress_callback=cb)
    bar.progress(1.0)
    status.success("Scan complete!")
    return results


def build_dataframe(history: list[dict]) -> pd.DataFrame:
    """Flatten all history into a single DataFrame for search / table views."""
    rows = []
    for week_data in history:
        week_label = format_week_label(
            week_data.get("week_start", ""),
            week_data.get("week_end"),
        )
        for r in week_data.get("retailers", []):
            for p in r.get("products", []):
                rows.append({
                    "week_start":    week_data.get("week_start", ""),
                    "Week":          week_label,
                    "Retailer":      r["name"],
                    "Product":       p.get("product_name", ""),
                    "Price":         p.get("price", ""),
                    "Deal Details":  p.get("deal_details", "") or "—",
                    "Page":          p.get("page_number", ""),
                    "View":          p.get("page_url", p.get("flyer_url", "")),
                })
    cols = ["week_start", "Week", "Retailer", "Product", "Price", "Deal Details", "Page", "View"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def retailer_sections(products: list[dict], week_label: str) -> None:
    """Render per-retailer expandable sections for a given product list."""
    for retailer_cfg in RETAILERS:
        r_name    = retailer_cfg["name"]
        r_products = [p for p in products if p["Retailer"] == r_name]

        if r_products:
            label = f"🛒 **{r_name}** — {len(r_products)} deal(s)"
        else:
            label = f"🛒 **{r_name}** — no deals this week"

        with st.expander(label, expanded=bool(r_products)):
            if not r_products:
                st.caption("No Tim Hortons products detected in this retailer's flyer.")
                continue

            hcols = st.columns([4, 1.5, 2.5, 1.5])
            hcols[0].markdown("**Product**")
            hcols[1].markdown("**Price**")
            hcols[2].markdown("**Deal Details**")
            hcols[3].markdown("**Flyer Page**")
            st.markdown('<hr class="row-divider">', unsafe_allow_html=True)

            for p in r_products:
                cols = st.columns([4, 1.5, 2.5, 1.5])
                cols[0].markdown(p["Product"])
                cols[1].markdown(
                    f'<span class="price-pill">{p["Price"]}</span>',
                    unsafe_allow_html=True,
                )
                cols[2].caption(p["Deal Details"])
                cols[3].markdown(f"[Page {p['Page']} ↗]({p['View']})")
                st.markdown('<hr class="row-divider">', unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ☕ Tim Hortons Flyer Scanner")
    st.divider()

    history = load_all_history()
    scanned_count = len(load_scanned_registry())

    if history:
        latest_ts = max(w.get("scraped_at", "") for w in history)
        st.success(f"**{len(history)} week(s)** in history\nLast scan: {format_ts(latest_ts)}")
        st.caption(f"{scanned_count} flyer(s) in registry")
    else:
        st.info("No history yet. Click **Scan New Flyers** to start.")

    scan_btn = st.button(
        "🔄 Scan New Flyers",
        type="primary",
        use_container_width=True,
        help=(
            "Checks the last 8 flyer cycles. Skips any already in the registry "
            "so you only pay for genuinely new flyers."
        ),
    )

    with st.expander("⚙ Advanced"):
        force_rescan = st.checkbox(
            "Ignore registry (rescan everything)",
            value=False,
            help="Forces re-analysis of all flyers in the last 8 weeks, even if already scanned.",
        )

    st.divider()
    st.markdown("**Retailers monitored (Ontario)**")
    for r in RETAILERS:
        st.caption(f"• {r['name']}")
    st.divider()
    st.caption("Data from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · Claude Sonnet 4.6")


# ── Banner ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="th-banner">'
    "<h1>☕ Tim Hortons Flyer Scanner</h1>"
    "<p>Ontario grocery flyer monitor · 4-week history · Smart incremental scanning</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ── Handle scan button ────────────────────────────────────────────────────────
if scan_btn:
    if force_rescan:
        # Wipe the registry so everything gets re-scanned
        from scraper import save_scanned_registry
        save_scanned_registry(set())

    with st.spinner("Scanning flyers — this may take several minutes…"):
        run_with_progress()
    st.rerun()

# ── No history yet ────────────────────────────────────────────────────────────
if not history:
    st.info(
        "No scan data found.\n\n"
        "Click **Scan New Flyers** in the sidebar. On first run it will scan the "
        "last 4 flyer cycles (Thu–Wed weeks) and build a history. "
        "Subsequent scans only process new, unscanned flyers."
    )
    st.stop()

# ── Global metrics (across all history) ──────────────────────────────────────
full_df = build_dataframe(history)

total_products   = len(full_df)
weeks_tracked    = len(history)
retailers_active = full_df["Retailer"].nunique() if not full_df.empty else 0
total_pages      = sum(
    f.get("pages_scanned", 0)
    for w in history
    for r in w.get("retailers", [])
    for f in r.get("flyers", [])
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("🛒 Total TH Deals Found",   total_products)
c2.metric("📅 Weeks of History",        weeks_tracked)
c3.metric("🏪 Retailers with Deals",    retailers_active)
c4.metric("📄 Total Pages Analyzed",    total_pages)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_weekly, tab_history = st.tabs(["📅 Weekly Review", "🔍 Product History"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — WEEKLY REVIEW
# Shows the retailer-section UI for a single selected week.
# ══════════════════════════════════════════════════════════════════════════════
with tab_weekly:
    week_labels = [
        format_week_label(w.get("week_start", ""), w.get("week_end"))
        for w in history
    ]

    col_week, col_retailer = st.columns([2, 3])

    with col_week:
        selected_week_label = st.selectbox(
            "Flyer Cycle",
            options=week_labels,
            index=0,
            key="weekly_week",
        )

    # Find the corresponding week data
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
                    "Price":        p.get("price", ""),
                    "Deal Details": p.get("deal_details", "") or "—",
                    "Page":         p.get("page_number", ""),
                    "View":         p.get("page_url", p.get("flyer_url", "")),
                })

    with col_retailer:
        retailer_names     = [r["name"] for r in RETAILERS]
        selected_retailers = st.multiselect(
            "Retailer",
            options=retailer_names,
            default=retailer_names,
            key="weekly_retailer",
        )

    filtered_week = [p for p in week_products if p["Retailer"] in selected_retailers]

    if week_data:
        scraped_at = week_data.get("scraped_at", "")
        st.caption(f"**{selected_week_label}** · Scanned {format_ts(scraped_at) if scraped_at else 'unknown'} · {len(filtered_week)} deal(s)")

    if not filtered_week:
        st.info("No Tim Hortons products found for the selected week and retailer filter.")
    else:
        retailer_sections(filtered_week, selected_week_label)

    # Per-week CSV download
    if filtered_week:
        df_week = pd.DataFrame(filtered_week).drop(columns=["View"])
        st.download_button(
            "⬇ Download This Week as CSV",
            data=df_week.to_csv(index=False).encode("utf-8"),
            file_name=f"tim_hortons_{selected_week_label.replace(' ', '_').replace('–','to')}.csv",
            mime="text/csv",
            key="csv_weekly",
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PRODUCT HISTORY
# Searchable, filterable flat table across all weeks.
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    if full_df.empty:
        st.info("No product history yet. Run a scan first.")
        st.stop()

    # Filters
    fcol1, fcol2, fcol3 = st.columns([2, 2, 3])

    with fcol1:
        all_week_labels    = week_labels  # already ordered newest first
        selected_hist_weeks = st.multiselect(
            "Flyer Cycle(s)",
            options=all_week_labels,
            default=all_week_labels,
            key="hist_weeks",
            help="Select one or more flyer cycles to include.",
        )

    with fcol2:
        retailer_names_all  = [r["name"] for r in RETAILERS]
        selected_hist_retailers = st.multiselect(
            "Retailer(s)",
            options=retailer_names_all,
            default=retailer_names_all,
            key="hist_retailers",
        )

    with fcol3:
        search_query = st.text_input(
            "Search Products",
            placeholder="e.g. K-Cup, Dark Roast, Steeped Tea…",
            key="hist_search",
        )

    # Apply filters
    filtered_df = full_df.copy()

    if selected_hist_weeks:
        filtered_df = filtered_df[filtered_df["Week"].isin(selected_hist_weeks)]

    if selected_hist_retailers:
        filtered_df = filtered_df[filtered_df["Retailer"].isin(selected_hist_retailers)]

    if search_query.strip():
        q = search_query.strip()
        filtered_df = filtered_df[
            filtered_df["Product"].str.contains(q, case=False, na=False)
        ]

    st.caption(f"{len(filtered_df)} deal(s) match the current filters")

    if filtered_df.empty:
        st.info("No results match the current filters.")
    else:
        display_df = filtered_df[
            ["Week", "Retailer", "Product", "Price", "Deal Details", "View"]
        ].sort_values(
            by=["Week", "Retailer"],
            ascending=[False, True],
            key=lambda col: col if col.name != "Week" else col.map(
                {label: i for i, label in enumerate(week_labels)}
            ),
        ).reset_index(drop=True)

        st.dataframe(
            display_df,
            column_config={
                "View": st.column_config.LinkColumn(
                    "Flyer Page",
                    display_text="View ↗",
                    help="Opens the exact SmartCanucks flyer page.",
                ),
            },
            use_container_width=True,
            hide_index=True,
        )

        # Full history CSV download
        csv_df = filtered_df[["Week", "Retailer", "Product", "Price", "Deal Details", "View"]]
        st.download_button(
            "⬇ Download Filtered History as CSV",
            data=csv_df.to_csv(index=False).encode("utf-8"),
            file_name="tim_hortons_flyer_history.csv",
            mime="text/csv",
            key="csv_history",
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Tim Hortons Canada CPG Team · "
    "Data from [SmartCanucks.ca](https://flyers.smartcanucks.ca) · "
    "New flyers scan every Monday · Powered by Claude Sonnet 4.6"
)
