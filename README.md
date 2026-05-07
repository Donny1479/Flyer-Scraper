# ☕ Tim Hortons Flyer Scanner

Scans Ontario grocery flyers on SmartCanucks.ca for Tim Hortons branded products and presents them in a clean Streamlit dashboard with product name, price, deal details, and a direct link to the flyer page.

## Retailers monitored (Ontario)

| Retailer | Region |
|---|---|
| Walmart | ON |
| Sobeys | ON |
| No Frills | ON + GTA |
| FreshCo | ON |
| RCSS (Real Canadian Superstore) | ON |
| Loblaws | ON |
| Metro | ON |
| Food Basics | National / ON |

## How it works

1. **Scraper** fetches each retailer's current Ontario flyer listing from SmartCanucks.ca
2. All flyer page images (JPGs) are downloaded for each flyer
3. **Claude Vision** (`claude-haiku-4-5-20251001`) analyzes every page image and extracts Tim Hortons products, prices, and deal details
4. Results are cached to `data/results.json`
5. **Streamlit UI** renders the results in a filterable dashboard with CSV export

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your Anthropic API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### Streamlit dashboard (recommended)

```bash
streamlit run app.py
```

Then click **Scan Flyers Now** in the sidebar. The first scan takes ~5–10 minutes
(downloads and analyzes ~150–200 flyer page images via Claude Vision).
Results are cached — subsequent visits load instantly until you refresh.

### Command-line scan

```bash
python scraper.py
```

Results are saved to `data/results.json`.

## Monday automation

To run every Monday automatically (cron example):

```cron
0 8 * * 1 cd /path/to/Flyer-Scraper && python scraper.py
```

New Canadian grocery flyers post on Thursdays; Monday morning is the ideal time
to scan the full week's active flyers.

## Project structure

```
Flyer-Scraper/
├── scraper.py        # Web scraping + Claude Vision extraction
├── app.py            # Streamlit dashboard
├── requirements.txt
├── .env.example
└── data/
    └── results.json  # Cached scan results (auto-created)
```
