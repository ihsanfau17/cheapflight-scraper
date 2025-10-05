# Google Flights Scraper

Automated scraper for Google Flights search results built with Selenium and webdriver-manager. The script drives Chrome to open a saved search URL, iterates over all visible flight cards (including those hidden behind "View more" buttons), and exports normalised flight data to the terminal or a CSV file.

## Features
- Extracts airline, departure and arrival timestamps (with arrival dates), duration, stopovers, and ticket price for each flight card.
- Supports individual dates, inclusive ranges, or relative year offsets from the seed Google Flights URL.
- Scrolls through long result lists and clicks "View more" buttons to capture every available card.
- Headless mode enabled by default; can be disabled for debugging.
- Writes clean CSV output that can be combined across months for downstream analysis.

## Repository Layout
```
repo_google_flights/
├── README.md
├── scrape_google_flights.py
├── requirements.txt
├── .gitignore
├── data/
│   ├── flights_oct_04_10.csv
│   ├── flights_oct_2025.csv
│   ├── flights_nov_2025.csv
│   └── flights_dec_2025.csv
├── docs/
│   ├── project_overview.md
│   └── progress_summary.md
└── scripts/
    └── scrape_december_2025.sh (example batch job)
```

## Prerequisites
- Python 3.9 or newer (uses built-in type annotations that require 3.9+).
- Google Chrome installed locally.
- Network access (webdriver-manager downloads the matching ChromeDriver on first run).

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
1. Activate your virtual environment.
2. Run the scraper with the desired date configuration.

```bash
python scrape_google_flights.py \
  --url "<your-google-flights-url>" \
  --range-start 2025-12-01 \
  --range-end 2025-12-31 \
  --csv-output data/flights_dec_2025.csv
```

### Command-Line Options
| Option | Description |
| ------ | ----------- |
| `--url` | Base Google Flights search URL containing origin, destination, and filter preferences. |
| `--target-date` | Date label as shown in the Google Flights calendar (used when not passing explicit dates). |
| `--dates` | Comma-separated ISO dates (`YYYY-MM-DD`). Overrides `--target-date` and `--year-offsets`. |
| `--range-start`, `--range-end` | Inclusive ISO date range to scrape. |
| `--year-offsets` | Comma-separated year offsets applied to the date extracted from `--target-date`. |
| `--max-results` | Maximum number of flight cards to capture per date (`0` = capture all). |
| `--csv-output` | Path to write CSV results. If omitted, data prints to stdout. |
| `--headless/--no-headless` | Toggle headless Chrome (defaults to headless). |
| `--no-table` | Skip printing the formatted table to stdout. |

### Handling Large Date Ranges
Google Flights sometimes throttles very long scraping sessions. The sample script in `scripts/scrape_december_2025.sh` demonstrates splitting a heavy month into smaller batches and combining the CSVs afterward.

## Included Data Sets
The `data/` directory contains CSV exports collected for October–December 2025. Feel free to remove or replace them when running your own searches.

## Troubleshooting
- If ChromeDriver cannot start, ensure your local Chrome browser is up to date.
- When Google Flights changes its DOM, update the CSS selectors in `scrape_google_flights.py` accordingly.
- For debugging, re-run with `--no-headless` to watch the browser session.

## License
Released under the MIT License. See `LICENSE` for details.
