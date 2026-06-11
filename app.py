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

TIM_HORTONS_BRAND = "Tim Hortons"
TIM_HORTONS_BRAND_RE = re.compile(r"\b(?:tim\s*hortons?|hortons?|tim'?s)\b", re.IGNORECASE)

KNOWN_COMPETITOR_BRANDS = [
    ("Starbucks", ["starbucks"]),
    ("McCafe", ["mccafe", "mc cafe", "mccafe@"]),
    ("Nescafe", ["nescafe", "nescafé"]),
    ("Maxwell House", ["maxwell house"]),
    ("Nabob", ["nabob"]),
    ("Folgers", ["folgers"]),
    ("Lavazza", ["lavazza"]),
    ("Kicking Horse", ["kicking horse"]),
    ("Balzac's", ["balzac"]),
    ("Illy", ["illy"]),
    ("Muskoka", ["muskoka"]),
    ("Timothy's", ["timothy"]),
    ("Krispy Kreme", ["krispy kreme"]),
    ("PC", ["pc ", "president's choice", "presidents choice"]),
    ("No Name", ["no name"]),
    ("Compliments", ["compliments"]),
    ("Selection", ["selection"]),
    ("Irresistibles", ["irresistibles"]),
    ("Nespresso", ["nespresso"]),
    ("Red Rose", ["red rose"]),
    ("Lipton", ["lipton"]),
]


def offer_brand(product: dict) -> str:
    """Return an offer brand, preserving explicit scan metadata when present."""
    explicit_brand = (
        product.get("brand")
        or product.get("brand_name")
        or product.get("Brand")
        or product.get("brand_seen")
    )
    if explicit_brand:
        return str(explicit_brand).strip()

    text = " ".join(
        str(product.get(field, "") or "")
        for field in ("brand_text_seen", "product_name", "deal_details")
    ).lower()
    if TIM_HORTONS_BRAND_RE.search(text):
        return TIM_HORTONS_BRAND

    padded_text = f" {text} "
    for brand, needles in KNOWN_COMPETITOR_BRANDS:
        if any(needle in padded_text for needle in needles):
            return brand
    return "Other"


def is_tim_hortons_offer(product: dict) -> bool:
    return offer_brand(product).lower() == TIM_HORTONS_BRAND.lower()


def is_tim_hortons_brand(brand: str) -> bool:
    return str(brand or "").strip().lower() == TIM_HORTONS_BRAND.lower()


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
PRICE_RE = re.compile(r'\$?\s*(\d+(?:\.\d{1,2})?)')
MULTI_PRICE_RE = re.compile(r'(?<![\d.$])(\d+)\s*(?:/|for)\s*\$?\s*(\d+(?:\.\d{1,2})?)', re.IGNORECASE)

UMAP_PERIODS = [
    ("2025", "2025-01-01", "2025-04-30"),
    ("2025 LPI2", "2025-05-01", "2026-01-31"),
    ("2026", "2026-02-01", None),
]

UMAP_REFERENCE = [
    {"key": "R&G | Small Bag | 300g", "Format": "R&G", "Segment": "Small Bag", "Size": "283g / 300g", "2025": 8.45, "2025 LPI2": 8.45, "2026": 9.45},
    {"key": "R&G | Large Bag | 652g", "Format": "R&G", "Segment": "Large Bag", "Size": "652g", "2025": 15.95, "2025 LPI2": 16.86, "2026": 17.86},
    {"key": "R&G | Large Can | 825g-930g", "Format": "R&G", "Segment": "Large Can", "Size": "825g - 930g", "2025": 18.95, "2025 LPI2": 19.86, "2026": 22.86},
    {"key": "R&G | Large Bag | 907g", "Format": "R&G", "Segment": "Large Bag", "Size": "907g", "2025": 18.95, "2025 LPI2": 19.86, "2026": 22.86},
    {"key": "R&G | Small Can | 640g", "Format": "R&G", "Segment": "Small Can", "Size": "640g", "2025": 15.95, "2025 LPI2": 18.45, "2026": 22.86},
    {"key": "R&G | Small Can | 640g Decaf", "Format": "R&G", "Segment": "Small Can", "Size": "640g Decaf", "2025": 15.95, "2025 LPI2": 18.45, "2026": 22.86},
    {"key": "Single Serve | Tassimo | Discs", "Format": "Single Serve", "Segment": "Tassimo", "Size": "Discs", "2025": 7.95, "2025 LPI2": 8.86, "2026": 8.86},
    {"key": "Single Serve | Small K-Cup | 10/12ct", "Format": "Single Serve", "Segment": "Small K-Cup", "Size": "10/12ct", "2025": 7.95, "2025 LPI2": 8.45, "2026": 9.45},
    {"key": "Single Serve | Hot Choc | 20ct", "Format": "Single Serve", "Segment": "Hot Choc", "Size": "20ct", "2025": None, "2025 LPI2": 17.45, "2026": 17.45},
    {"key": "Single Serve | Large K-Cup | 24/30ct", "Format": "Single Serve", "Segment": "Large K-Cup", "Size": "24/30ct", "2025": 19.95, "2025 LPI2": 19.86, "2026": 19.86},
    {"key": "Single Serve | Club K-Cup | 48ct", "Format": "Single Serve", "Segment": "Club K-Cup", "Size": "48ct", "2025": 30.95, "2025 LPI2": 31.86, "2026": 31.86},
    {"key": "Single Serve | NCC | NCC 10ct", "Format": "Single Serve", "Segment": "NCC", "Size": "NCC 10ct", "2025": 5.96, "2025 LPI2": 6.86, "2026": 6.86},
    {"key": "Hot Beverages | Hot Choc | 500g", "Format": "Hot Beverages", "Segment": "Hot Choc", "Size": "500g", "2025": 4.45, "2025 LPI2": 4.86, "2026": 4.86},
    {"key": "Hot Beverages | Sachets | 8ct", "Format": "Hot Beverages", "Segment": "Sachets", "Size": "8ct", "2025": 4.45, "2025 LPI2": 4.86, "2026": 4.86},
    {"key": "Hot Beverages | Sachets | 24ct", "Format": "Hot Beverages", "Segment": "Sachets", "Size": "24ct", "2025": 8.95, "2025 LPI2": 9.86, "2026": 9.86},
    {"key": "Hot Beverages | Hot Choc | 1.5Kg", "Format": "Hot Beverages", "Segment": "Hot Choc", "Size": "1.5Kg", "2025": 9.96, "2025 LPI2": 12.86, "2026": 12.86},
    {"key": "Hot Beverages | FVCapp | 454g", "Format": "Hot Beverages", "Segment": "FVCapp", "Size": "454g", "2025": 5.96, "2025 LPI2": 6.86, "2026": 6.86},
    {"key": "Instant | Jar | 100g", "Format": "Instant", "Segment": "Jar", "Size": "100g", "2025": 4.45, "2025 LPI2": 6.45, "2026": 6.76},
    {"key": "Instant | Jar | 300g", "Format": "Instant", "Segment": "Jar", "Size": "300g", "2025": 8.95, "2025 LPI2": 13.86, "2026": 13.86},
    {"key": "Tea Bags | Specialty | 20ct", "Format": "Tea Bags", "Segment": "Specialty", "Size": "20ct", "2025": 2.45, "2025 LPI2": 2.45, "2026": 2.45},
    {"key": "Granola | Bars | 5ct", "Format": "Granola", "Segment": "Bars", "Size": "5ct", "2025": 1.95, "2025 LPI2": 1.95, "2026": 1.95},
    {"key": "Soup | Can | 540mL", "Format": "Soup", "Segment": "Can", "Size": "540mL", "2025": 2.33, "2025 LPI2": 2.33, "2026": 2.33},
    {"key": "Chili | Can | 425g", "Format": "Chili", "Segment": "Can", "Size": "425g", "2025": 2.95, "2025 LPI2": 2.95, "2026": 2.95},
    {"key": "Creamers | DC - Conventional | 750ml", "Format": "Creamers", "Segment": "DC - Conventional", "Size": "750ml", "2025": 4.97, "2025 LPI2": 4.97, "2026": 4.97},
    {"key": "Condensed | Can | 284mL", "Format": "Condensed", "Segment": "Can", "Size": "284mL", "2025": 0.86, "2025 LPI2": 0.86, "2026": 0.86},
    {"key": "Creamers | Bottle | 1.42L", "Format": "Creamers", "Segment": "Bottle", "Size": "1.42L", "2025": None, "2025 LPI2": None, "2026": None},
    {"key": "Instant | Bottle | 470ml", "Format": "Instant", "Segment": "Bottle", "Size": "470ml", "2025": None, "2025 LPI2": 6.45, "2026": 6.45},
    {"key": "RTD Iced Coffee | Bottle | 1.42L", "Format": "RTD Iced Coffee", "Segment": "Bottle", "Size": "1.42L", "2025": None, "2025 LPI2": 6.45, "2026": 6.45},
    {"key": "Sauces | Bottle | 473mL", "Format": "Sauces", "Segment": "Bottle", "Size": "473mL", "2025": None, "2025 LPI2": None, "2026": 3.86},
    {"key": "Baking | BiscuitMix | 322g", "Format": "Baking", "Segment": "BiscuitMix", "Size": "322g", "2025": None, "2025 LPI2": None, "2026": 2.86},
    {"key": "Bagged Tea | SteepedTea | 72ct", "Format": "Bagged Tea", "Segment": "SteepedTea", "Size": "72ct", "2025": None, "2025 LPI2": None, "2026": 5.45},
    {"key": "Instant | Sweet&Creamy | 350g", "Format": "Instant", "Segment": "Sweet&Creamy", "Size": "350g", "2025": None, "2025 LPI2": None, "2026": 4.45},
    {"key": "Soups | Loaded | 540mL", "Format": "Soups", "Segment": "Loaded", "Size": "540mL", "2025": None, "2025 LPI2": None, "2026": 2.95},
]

UMAP_BY_KEY = {row["key"]: row for row in UMAP_REFERENCE}


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


def fmt_money(value) -> str:
    if isinstance(value, (int, float)) and not pd.isna(value):
        sign = "-" if value < 0 else ""
        return f"{sign}${abs(value):.2f}"
    return "—"


def normalize_text(*parts: str) -> str:
    return " ".join(str(p or "").lower().replace("‑", "-").replace("–", "-") for p in parts)


def extract_numeric_unit_values(text: str, units: tuple[str, ...], multipliers: dict[str, float] | None = None) -> list[float]:
    unit_alt = "|".join(re.escape(u) for u in units)
    values: list[float] = []
    multipliers = multipliers or {u: 1 for u in units}

    range_re = re.compile(
        rf'\b(\d+(?:\.\d+)?)\s*(?:-|/|to)\s*(\d+(?:\.\d+)?)\s*({unit_alt})\b',
        re.IGNORECASE,
    )
    for m in range_re.finditer(text):
        unit = m.group(3).lower()
        mult = multipliers.get(unit, 1)
        values.extend([float(m.group(1)) * mult, float(m.group(2)) * mult])

    single_re = re.compile(rf'\b(\d+(?:\.\d+)?)\s*({unit_alt})\b', re.IGNORECASE)
    for m in single_re.finditer(text):
        unit = m.group(2).lower()
        mult = multipliers.get(unit, 1)
        values.append(float(m.group(1)) * mult)

    return values


def extract_gram_values(text: str) -> list[float]:
    return extract_numeric_unit_values(text, ("kg", "g"), {"kg": 1000, "g": 1})


def extract_ml_values(text: str) -> list[float]:
    return extract_numeric_unit_values(text, ("ml", "l"), {"ml": 1, "l": 1000})


def extract_count_values(text: str) -> list[float]:
    return extract_numeric_unit_values(text, ("count", "ct", "pack", "pk"), {"count": 1, "ct": 1, "pack": 1, "pk": 1})


def parse_price_points(price_text: str) -> list[float]:
    text = normalize_text(price_text)
    if "point" in text:
        return []

    prices: list[float] = []
    for count, total in MULTI_PRICE_RE.findall(text):
        count_num = float(count)
        total_num = float(total)
        if count_num:
            prices.append(total_num / count_num)

    for amount in re.findall(r'\$\s*(\d+(?:\.\d{1,2})?)', text):
        prices.append(float(amount))

    if not prices:
        for amount in PRICE_RE.findall(text):
            prices.append(float(amount))

    return sorted(p for p in prices if p > 0)


def umap_period_for_week(week_start: str) -> str:
    for label, start, end in reversed(UMAP_PERIODS):
        if week_start >= start and (end is None or week_start <= end):
            return label
    return "2025"


def match_umap_category(product: str, comments: str = "") -> tuple[str, str]:
    text = normalize_text(product, comments)
    grams = extract_gram_values(text)
    counts = extract_count_values(text)
    mls = extract_ml_values(text)
    max_grams = max(grams) if grams else None
    max_count = max(counts) if counts else None
    max_ml = max(mls) if mls else None
    has = lambda *needles: any(n in text for n in needles)

    if has("chili"):
        return "Chili | Can | 425g", "Matched chili wording"

    if has("soup"):
        if has("condensed") or (max_ml and max_ml <= 300):
            return "Condensed | Can | 284mL", "Matched condensed soup or 284mL"
        if has("loaded"):
            return "Soups | Loaded | 540mL", "Matched loaded soup"
        return "Soup | Can | 540mL", "Matched soup wording or 540mL"

    if has("iced coffee") and max_ml and max_ml >= 1000:
        return "RTD Iced Coffee | Bottle | 1.42L", "Matched iced coffee bottle"

    if has("creamer"):
        if max_ml and max_ml >= 1000:
            return "Creamers | Bottle | 1.42L", "Matched creamer bottle"
        return "Creamers | DC - Conventional | 750ml", "Matched creamer 750mL"

    is_single_serve = has("k-cup", "k cup", "k-cups", "k cups", "pod", "pods", "capsule", "capsules", "single serve", "single-serve", "coffee cups")
    if has("tassimo"):
        return "Single Serve | Tassimo | Discs", "Matched Tassimo"
    if has("nespresso", "ncc"):
        return "Single Serve | NCC | NCC 10ct", "Matched Nespresso/NCC"
    if is_single_serve:
        if has("hot chocolate") and max_count and max_count <= 20:
            return "Single Serve | Hot Choc | 20ct", "Matched single serve hot chocolate 20ct"
        if max_count and max_count >= 48:
            return "Single Serve | Club K-Cup | 48ct", "Matched 48ct single serve"
        if max_count and max_count >= 24:
            return "Single Serve | Large K-Cup | 24/30ct", "Matched 24/30ct single serve"
        return "Single Serve | Small K-Cup | 10/12ct", "Matched 10/12ct single serve"

    if has("hot chocolate"):
        if max_grams and max_grams >= 1000:
            return "Hot Beverages | Hot Choc | 1.5Kg", "Matched hot chocolate 1.5kg"
        if max_count and max_count >= 24:
            return "Hot Beverages | Sachets | 24ct", "Matched hot beverage sachets 24ct"
        if max_count:
            return "Hot Beverages | Sachets | 8ct", "Matched hot beverage packets"
        return "Hot Beverages | Hot Choc | 500g", "Matched hot chocolate 450-500g"

    if has("french vanilla", "cappuccino", "fvcapp"):
        return "Hot Beverages | FVCapp | 454g", "Matched French Vanilla/Cappuccino"

    if has("tea bag", "steeped tea") and max_count and max_count >= 70:
        return "Bagged Tea | SteepedTea | 72ct", "Matched steeped tea 72ct"
    if has("tea"):
        return "Tea Bags | Specialty | 20ct", "Matched tea wording"

    if has("granola"):
        return "Granola | Bars | 5ct", "Matched granola bars"

    if has("sauce"):
        return "Sauces | Bottle | 473mL", "Matched sauce bottle"
    if has("biscuit"):
        return "Baking | BiscuitMix | 322g", "Matched biscuit mix"

    if has("instant", "sweet & creamy", "sweet&creamy"):
        if has("sweet & creamy", "sweet&creamy") or (max_grams and 325 <= max_grams <= 375):
            return "Instant | Sweet&Creamy | 350g", "Matched sweet and creamy instant"
        if max_ml and max_ml >= 400:
            return "Instant | Bottle | 470ml", "Matched instant bottle"
        if max_grams and max_grams >= 250:
            return "Instant | Jar | 300g", "Matched instant 300g"
        return "Instant | Jar | 100g", "Matched instant 100-150g"

    is_roast_ground = has("ground coffee", "roast and ground", "roast & ground", "whole bean", "coffee")
    if is_roast_ground and max_grams:
        if max_grams <= 330:
            return "R&G | Small Bag | 300g", "Matched R&G 283-300g small bag"
        if max_grams >= 800:
            if has("bag") and any(890 <= g <= 920 for g in grams):
                return "R&G | Large Bag | 907g", "Matched R&G 907g large bag"
            return "R&G | Large Can | 825g-930g", "Matched R&G 825-930g large can"
        if any(620 <= g <= 650 for g in grams):
            return (
                "R&G | Small Can | 640g Decaf" if has("decaf") else "R&G | Small Can | 640g",
                "Matched R&G 640g small can",
            )
        if any(651 <= g <= 700 for g in grams):
            return "R&G | Large Bag | 652g", "Matched R&G 652g large bag"

    return "", "Needs manual review: no UMAP match"


def build_umap_review_df(full_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in full_df.iterrows():
        match_key, _basis = match_umap_category(row["Product"])
        period = umap_period_for_week(row["week_start"])
        ref = UMAP_BY_KEY.get(match_key, {})
        umap = ref.get(period)
        prices = parse_price_points(row["Price"])
        lowest_price = prices[0] if prices else None

        if not match_key:
            status = "Unmatched"
            delta = None
        elif umap is None:
            status = "No UMAP"
            delta = None
        elif lowest_price is None:
            status = "Needs Review"
            delta = None
        else:
            delta = lowest_price - umap
            status = "Violation" if delta < -0.005 else "Compliant"

        rows.append({
            "week_start": row["week_start"],
            "Year": row["week_start"][:4],
            "Week": row["Week"],
            "Retailer": row["Retailer"],
            "Product": row["Product"],
            "Advertised Price": row["Price"],
            "Matched UMAP Category": match_key or "—",
            "UMAP": umap,
            "Lowest Comparable Price": lowest_price,
            "Difference": delta,
            "Status": status,
            "View": row["View"],
        })

    return pd.DataFrame(rows)


def status_class(status: str) -> str:
    return "status-" + status.lower().replace(" ", "-")


def build_full_df(history: list[dict]) -> pd.DataFrame:
    rows = []
    for wd in history:
        ws  = wd.get("week_start", "")
        we  = wd.get("week_end",   "")
        lbl = format_week_label(ws, we)
        for r in wd.get("retailers", []):
            for p in r.get("products", []):
                name = p.get("product_name", "")
                brand = offer_brand(p)
                rows.append({
                    "week_start": ws,
                    "Week":       lbl,
                    "Retailer":   r["name"],
                    "Brand":      brand,
                    "Product":    name,
                    "Size":       extract_size(name),
                    "Category":   classify(name),
                    "Price":      p.get("price", ""),
                    "Comments":   p.get("deal_details", "") or "—",
                    "Start":      fmt_date(ws),
                    "End":        fmt_date(we),
                    "View":       p.get("page_url", p.get("flyer_url", "")),
                })
    cols = ["week_start", "Week", "Retailer", "Brand", "Product", "Size", "Category",
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
.sidebar-mini-stats {
    display: grid;
    gap: 0.42rem;
    margin: 0.35rem 0 0.45rem;
}
.sidebar-mini-stat {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.38rem 0.55rem;
    background: #fff;
    border: 1px solid rgba(111,45,37,0.12);
    border-radius: 8px;
}
.sidebar-mini-stat span {
    color: var(--th-chocolate);
    font-size: 0.7rem;
    font-weight: 750;
    line-height: 1.2;
}
.sidebar-mini-stat strong {
    color: var(--th-red);
    font-size: 0.78rem;
    font-weight: 900;
    line-height: 1.2;
    white-space: nowrap;
}
.sidebar-note {
    color: #7C6254;
    font-size: 0.72rem;
    line-height: 1.35;
    margin: 0.2rem 0 0;
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
.status-pill {
    display: inline-block;
    border-radius: 99px;
    padding: 0.12rem 0.58rem;
    font-size: 0.76rem;
    font-weight: 800;
    white-space: nowrap;
}
.status-compliant { background: #E8F5E9; color: #1B5E20; }
.status-violation { background: #FDE7EA; color: var(--th-red); }
.status-needs-review { background: #FFF3CD; color: #7A4E00; }
.status-unmatched,
.status-no-umap { background: #F3E9DE; color: var(--th-chocolate); }

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
.deal-table-hdr.competitive,
.deal-table-row.competitive {
    grid-template-columns: minmax(124px, 0.9fr) 1fr 1.7fr 0.75fr 0.9fr 1.6fr 0.7fr;
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
    .deal-table-hdr.competitive,
    .deal-table-row.competitive {
        grid-template-columns: minmax(112px, 1fr) minmax(110px, 1fr) minmax(170px, 1.4fr) 76px 90px minmax(150px, 1.2fr) 70px;
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
    if history:
        sidebar_total_products = sum(
            sum(1 for p in r.get("products", []) if is_tim_hortons_offer(p))
            for w in history
            for r in w.get("retailers", [])
        )
        sidebar_total_pages = sum(
            f.get("pages_scanned", 0)
            for w in history
            for r in w.get("retailers", [])
            for f in r.get("flyers", [])
        )
        st.markdown(
            f'<div class="sidebar-mini-stats">'
            f'  <div class="sidebar-mini-stat"><span>TH deals found</span><strong>{sidebar_total_products:,}</strong></div>'
            f'  <div class="sidebar-mini-stat"><span>Weeks in history</span><strong>{len(history):,}</strong></div>'
            f'  <div class="sidebar-mini-stat"><span>Retailers tracked</span><strong>{len(RETAILERS):,}</strong></div>'
            f'  <div class="sidebar-mini-stat"><span>Pages scanned</span><strong>{sidebar_total_pages:,}</strong></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("No history yet. Add weekly JSON files under `data/history` to populate the dashboard.")

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
    f'        <h1 class="headline-lockup"><span class="headline-logo">{TIM_HORTONS_LOGO_SVG}</span><span>Flyer Price Tracker</span></h1>'
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
tim_hortons_df = full_df[full_df["Brand"].map(is_tim_hortons_brand)].copy()
week_labels = [
    format_week_label(w.get("week_start", ""), w.get("week_end"))
    for w in history
]
weekly_offer_counts = {
    format_week_label(w.get("week_start", ""), w.get("week_end")): sum(
        sum(1 for p in r.get("products", []) if is_tim_hortons_offer(p))
        for r in w.get("retailers", [])
    )
    for w in history
}


def weekly_cycle_option_label(label: str) -> str:
    offer_count = weekly_offer_counts.get(label, 0)
    if offer_count <= 0:
        return label
    offer_word = "offer" if offer_count == 1 else "offers"
    return f"{label}  |  {offer_count} {offer_word}"

# ── Metrics ───────────────────────────────────────────────────────────────────
# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_weekly, tab_history, tab_insights, tab_umap = st.tabs([
    "📅  Weekly Review",
    "🔍  Product History",
    "📊  Flyer Insights",
    "⚠️  UMAP Check",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — WEEKLY REVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_weekly:
    col_week, col_retailer = st.columns([2, 3])

    with col_week:
        selected_week_label = st.selectbox(
            "Flyer Cycle",
            options=week_labels,
            index=0,
            key="wk_week",
            format_func=weekly_cycle_option_label,
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
                brand = offer_brand(p)
                week_products.append({
                    "Retailer":     r["name"],
                    "Brand":        brand,
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

    tim_week_products = [p for p in week_products if is_tim_hortons_brand(p["Brand"])]
    competitive_week_products = [p for p in week_products if not is_tim_hortons_brand(p["Brand"])]
    filtered_week = [p for p in tim_week_products if p["Retailer"] in selected_retailers]
    filtered_competitive_week = [
        p for p in competitive_week_products
        if p["Retailer"] in selected_retailers
    ]

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

    with st.expander("Competitive offers"):
        st.caption(f"{len(filtered_competitive_week)} competitive offer(s) match the current retailer filter")
        if not filtered_competitive_week:
            st.info("No competitive offers found for this cycle.")
        else:
            rows_html = ""
            for p in filtered_competitive_week:
                rows_html += (
                    f'<div class="deal-table-row competitive">'
                    f'  <div>{retailer_label(p["Retailer"])}</div>'
                    f'  <span>{html.escape(str(p["Brand"]))}</span>'
                    f'  <span>{html.escape(str(p["Product"]))}</span>'
                    f'  <span style="color:#666;">{html.escape(str(p["Size"]))}</span>'
                    f'  <span><span class="price-pill">{html.escape(str(p["Price"]))}</span></span>'
                    f'  <span style="color:#555;font-size:0.82rem;">{html.escape(str(p["Deal Details"]))}</span>'
                    f'  <a class="deal-link" href="{html.escape(str(p["View"]), quote=True)}" target="_blank">Page {html.escape(str(p["Page"]))} ↗</a>'
                    f'</div>'
                )

            st.markdown(
                '<div class="deal-table-wrap">'
                '  <div class="deal-table-hdr competitive">'
                '    <span>Retailer</span>'
                '    <span>Brand</span>'
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

            df_competitive_week = pd.DataFrame(filtered_competitive_week)
            st.download_button(
                "⬇ Download Competitive Offers as CSV",
                data=df_competitive_week.to_csv(index=False).encode("utf-8"),
                file_name=f"competitive_offers_{selected_week_label.replace(' ', '_').replace('–', 'to')}.csv",
                mime="text/csv",
                key="csv_weekly_competitive",
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PRODUCT HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    if full_df.empty:
        st.info("No product history yet. Add weekly JSON files to `data/history` first.")
        st.stop()

    # ── Filters ──────────────────────────────────────────────────────────────
    brand_options = sorted(full_df["Brand"].dropna().unique().tolist())
    if TIM_HORTONS_BRAND in brand_options:
        brand_options = [TIM_HORTONS_BRAND] + [b for b in brand_options if b != TIM_HORTONS_BRAND]
    default_brands = [TIM_HORTONS_BRAND] if TIM_HORTONS_BRAND in brand_options else brand_options

    hc1, hc_brand, hc2, hc3, hc4 = st.columns([2, 1.6, 2, 2, 3])
    with hc1:
        sel_weeks = st.multiselect(
            "Flyer Cycle(s)", options=week_labels, default=week_labels, key="h_weeks"
        )
    with hc_brand:
        sel_brands = st.multiselect(
            "Brand", options=brand_options, default=default_brands, key="h_brands"
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
    fdf = fdf[fdf["Brand"].isin(sel_brands)]
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
                f'<td>{html.escape(str(row["Brand"]))}</td>'
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
            '<th>Retailer</th><th>Brand</th><th>Product</th><th>Size</th><th>Category</th>'
            '<th>Price</th><th>Deal Details</th><th>Sale Start</th><th>Sale End</th><th>Flyer</th>'
            '</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            '</table></div>',
            unsafe_allow_html=True,
        )

        st.download_button(
            "⬇ Download Filtered History as CSV",
            data=fdf[["Week", "Retailer", "Brand", "Product", "Size", "Category",
                       "Price", "Comments", "Start", "End", "View"]].to_csv(index=False).encode("utf-8"),
            file_name="tim_hortons_flyer_history.csv",
            mime="text/csv",
            key="csv_history",
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — FLYER INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_insights:
    if tim_hortons_df.empty:
        st.info("No Tim Hortons data yet. Add weekly JSON files to `data/history` first.")
        st.stop()

    # ── Time window filter ───────────────────────────────────────────────────
    TIME_OPTIONS: dict[str, int | str | None] = {
        "L12 Weeks": 12,
        "L24 Weeks": 24,
        "L52 Weeks": 52,
        "2025": "year:2025",
        "2026": "year:2026",
        "All Available": None,
    }
    time_sel = st.radio(
        "Time Window",
        list(TIME_OPTIONS.keys()),
        index=list(TIME_OPTIONS.keys()).index("All Available"),
        horizontal=True,
        key="ins_time",
        label_visibility="collapsed",
    )
    time_filter = TIME_OPTIONS[time_sel]
    if isinstance(time_filter, int):
        cutoff = (datetime.today() - timedelta(weeks=time_filter)).strftime("%Y-%m-%d")
        ins_df = tim_hortons_df[tim_hortons_df["week_start"] >= cutoff].copy()
    elif isinstance(time_filter, str) and time_filter.startswith("year:"):
        selected_year = time_filter.split(":", 1)[1]
        ins_df = tim_hortons_df[tim_hortons_df["week_start"].str.startswith(f"{selected_year}-")].copy()
    else:
        ins_df = tim_hortons_df.copy()

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


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — UMAP CHECK
# ══════════════════════════════════════════════════════════════════════════════
with tab_umap:
    if tim_hortons_df.empty:
        st.info("No Tim Hortons data yet. Add weekly JSON files to `data/history` first.")
        st.stop()

    umap_df = build_umap_review_df(tim_hortons_df).sort_values("week_start", ascending=False).reset_index(drop=True)
    exception_statuses = ["Violation", "Needs Review", "Unmatched", "No UMAP"]
    umap_exception_df = umap_df[umap_df["Status"].isin(exception_statuses)].copy()

    total_checked = len(umap_df)
    violation_count = int((umap_exception_df["Status"] == "Violation").sum())
    review_count = int(umap_exception_df["Status"].isin(["Needs Review", "Unmatched", "No UMAP"]).sum())
    exception_count = len(umap_exception_df)

    uc1, uc2, uc3, uc4 = st.columns(4)
    uc1.metric("Offers Reviewed", total_checked)
    uc2.metric("UMAP Violations", violation_count)
    uc3.metric("Needs Review", review_count)
    uc4.metric("Exceptions Shown", exception_count)

    st.divider()

    uf1, uf2, uf3, uf4 = st.columns([2, 2, 2, 3])
    with uf1:
        umap_statuses = st.multiselect(
            "Status",
            options=exception_statuses,
            default=exception_statuses,
            key="umap_status",
        )
    with uf2:
        umap_years = st.multiselect(
            "Year",
            options=sorted(umap_df["Year"].dropna().unique().tolist(), reverse=True),
            default=sorted(umap_df["Year"].dropna().unique().tolist(), reverse=True),
            key="umap_year",
        )
    with uf3:
        umap_retailers = st.multiselect(
            "Retailer(s)",
            options=[r["name"] for r in RETAILERS],
            default=[r["name"] for r in RETAILERS],
            key="umap_retailers",
        )
    with uf4:
        umap_search = st.text_input(
            "Search UMAP Matches",
            placeholder="e.g. Large Can, K-Cup, Soup, 300g",
            key="umap_search",
        )

    udf = umap_exception_df.copy()
    if umap_statuses:
        udf = udf[udf["Status"].isin(umap_statuses)]
    if umap_years:
        udf = udf[udf["Year"].isin(umap_years)]
    if umap_retailers:
        udf = udf[udf["Retailer"].isin(umap_retailers)]
    if umap_search.strip():
        q = umap_search.strip()
        mask = (
            udf["Product"].str.contains(q, case=False, na=False) |
            udf["Matched UMAP Category"].str.contains(q, case=False, na=False)
        )
        udf = udf[mask]

    st.caption(f"{len(udf)} exception offer(s) match the current UMAP filters")

    if udf.empty:
        st.info("No UMAP exceptions match the current filters.")
    else:
        rows_html = ""
        for _, row in udf.iterrows():
            status = row["Status"]
            diff = row["Difference"]
            diff_text = fmt_money(diff) if isinstance(diff, (int, float)) and not pd.isna(diff) else "—"
            rows_html += (
                f'<tr>'
                f'<td>{retailer_label(row["Retailer"])}</td>'
                f'<td>{html.escape(str(row["Product"]))}</td>'
                f'<td><span class="price-pill">{html.escape(str(row["Advertised Price"]))}</span></td>'
                f'<td>{html.escape(str(row["Matched UMAP Category"]))}</td>'
                f'<td style="font-weight:800;">{fmt_money(row["UMAP"])}</td>'
                f'<td>{fmt_money(row["Lowest Comparable Price"])}</td>'
                f'<td>{diff_text}</td>'
                f'<td><span class="status-pill {status_class(status)}">{html.escape(status)}</span></td>'
                f'<td style="white-space:nowrap;color:#888;font-size:0.82rem;">{html.escape(str(row["Week"]))}</td>'
                f'<td><a class="deal-link" href="{html.escape(str(row["View"]), quote=True)}" target="_blank">View ↗</a></td>'
                f'</tr>'
            )

        st.markdown(
            '<div class="th-table-wrap">'
            '<table class="th-table">'
            '<thead><tr>'
            '<th>Retailer</th><th>Product</th><th>Advertised Price</th><th>Matched UMAP Category</th>'
            '<th>UMAP</th><th>Lowest Price</th><th>Diff</th><th>Status</th><th>Week</th><th>Flyer</th>'
            '</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            '</table></div>',
            unsafe_allow_html=True,
        )

        download_df = udf.copy()
        for col in ["UMAP", "Lowest Comparable Price", "Difference"]:
            download_df[col] = download_df[col].map(lambda v: "" if pd.isna(v) else round(float(v), 2))
        st.download_button(
            "⬇ Download UMAP Check as CSV",
            data=download_df[[
                "Week", "Retailer", "Product", "Advertised Price", "Matched UMAP Category",
                "UMAP", "Lowest Comparable Price", "Difference", "Status", "View"
            ]].to_csv(index=False).encode("utf-8"),
            file_name="tim_hortons_umap_check.csv",
            mime="text/csv",
            key="csv_umap",
        )

    with st.expander("UMAP reference used"):
        ref_df = pd.DataFrame(UMAP_REFERENCE)[["Format", "Segment", "Size", "2025", "2025 LPI2", "2026"]]
        st.dataframe(
            ref_df,
            column_config={
                "2025": st.column_config.NumberColumn("2025", format="$%.2f"),
                "2025 LPI2": st.column_config.NumberColumn("2025 LPI2", format="$%.2f"),
                "2026": st.column_config.NumberColumn("2026", format="$%.2f"),
            },
            width="stretch",
            hide_index=True,
        )


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
