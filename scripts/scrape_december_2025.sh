#!/usr/bin/env bash
set -euo pipefail

# Example batch runner that splits December 2025 into smaller chunks
# to avoid Google Flights throttling during long Selenium sessions.

python scrape_google_flights.py \
  --range-start 2025-12-01 \
  --range-end 2025-12-10 \
  --max-results 0 \
  --csv-output data/flights_dec_2025_part1.csv \
  --no-table

python scrape_google_flights.py \
  --range-start 2025-12-11 \
  --range-end 2025-12-20 \
  --max-results 0 \
  --csv-output data/flights_dec_2025_part2.csv \
  --no-table

python scrape_google_flights.py \
  --range-start 2025-12-21 \
  --range-end 2025-12-31 \
  --max-results 0 \
  --csv-output data/flights_dec_2025_part3.csv \
  --no-table

python - <<'PY'
from pathlib import Path
files = [
    Path('data/flights_dec_2025_part1.csv'),
    Path('data/flights_dec_2025_part2.csv'),
    Path('data/flights_dec_2025_part3.csv'),
]
output = Path('data/flights_dec_2025.csv')
with output.open('w', encoding='utf-8', newline='') as outfh:
    header_written = False
    for path in files:
        with path.open('r', encoding='utf-8') as infh:
            header = infh.readline()
            if not header:
                continue
            if not header_written:
                outfh.write(header)
                header_written = True
            for line in infh:
                outfh.write(line)
print('Combined into data/flights_dec_2025.csv')
PY
