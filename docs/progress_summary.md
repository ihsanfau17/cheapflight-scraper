# Google Flights Scraping Progress

- Environment: created `.venv` with Selenium + webdriver-manager; built `scrape_google_flights.py` to load Google Flights URLs, adjust departure dates, scroll through "Top flights" and "Other flights" (including *View more* buttons), and extract Maskapai, Tanggal, Waktu Berangkat, Waktu Datang (with arrival date), Durasi, Transit, and Harga Tiket.
- CLI Improvements: added options `--dates`, `--range-start/--range-end`, `--year-offsets`, `--max-results` (0 = all flights per date), and `--no-table`; output normalized data to CSV and optional console table.
- Data Collected:
  - `flights_oct_04_10.csv` — all flights for 2025-10-04 through 2025-10-10 (1,888 rows).
  - `flights_oct_2025.csv` — complete October 2025 range (7,939 rows).
  - `flights_nov_2025.csv` — complete November 2025 range (8,971 rows).

## Next Steps
- Continue with December 2025 (e.g., `--range-start 2025-12-01 --range-end 2025-12-31 --max-results 0 --csv-output flights_dec_2025.csv --no-table`).
- Review CSV outputs for downstream analysis or combine as needed.
