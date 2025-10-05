#!/usr/bin/env python3
"""Scrape flight information from Google Flights using Selenium.

The script automatically adjusts the departure date, loads the results
section, and extracts airline, price, departure/arrival times, duration,
stop count, and full travel dates for each flight card. Results are
printed in a readable table and can optionally be exported to CSV.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import re
import sys
import time
import unicodedata
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


DEFAULT_URL = (
    "https://www.google.com/travel/flights/search?"
    "tfs=CBwQAhooEgoyMDI1LTEwLTA0agwIAhIIL20vMDQ0cnZyDAgCEggvbS8wN2Rma0AB"
    "SAFwAYIBCwj___________8BmAED&tfu=EgYIABABGAA&tcfs=ChMKCC9tLzA0NHJ2GgdKYWthcnRhUgRgAXgB"
)
DEFAULT_DATE_LABEL = "Wed, Oct 8"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Google Flights results.")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Base Google Flights search URL (defaults to provided sample).",
    )
    parser.add_argument(
        "--target-date",
        default=DEFAULT_DATE_LABEL,
        help="Departure date label as shown in the date input, e.g. 'Wed, Oct 8'.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=0,
        help="Maximum number of flight cards to capture for each date (0 means all).",
    )
    parser.add_argument(
        "--csv-output",
        help="Optional path to write the scraped data to CSV.",
    )
    parser.add_argument(
        "--dates",
        help="Comma-separated list of departure dates (YYYY-MM-DD). Overrides --target-date and --year-offsets.",
    )
    parser.add_argument(
        "--range-start",
        help="Start date (YYYY-MM-DD) for an inclusive range.",
    )
    parser.add_argument(
        "--range-end",
        help="End date (YYYY-MM-DD) for an inclusive range.",
    )
    parser.add_argument(
        "--year-offsets",
        default="0,1",
        help="Comma-separated year offsets relative to the base filter year (default: '0,1' to include the same date next year).",
    )
    parser.add_argument(
        "--headless/--no-headless",
        dest="headless",
        action="store_true",
        default=True,
        help="Run Chrome in headless mode (default: on).",
    )
    parser.add_argument(
        "--no-table",
        action="store_true",
        help="Skip printing the full results table to stdout.",
    )
    return parser.parse_args()


def build_url_for_date(base_url: str, target_date: date) -> str:
    """Return a new Google Flights URL with the departure date swapped."""

    parsed = urllib.parse.urlparse(base_url)
    query = urllib.parse.parse_qs(parsed.query)
    tfs_value = query.get("tfs", [None])[0]
    if not tfs_value:
        return base_url

    pad = "=" * (-len(tfs_value) % 4)
    try:
        decoded = base64.urlsafe_b64decode(tfs_value + pad)
    except (ValueError, binascii.Error):
        return base_url

    date_match = re.search(rb"\d{4}-\d{2}-\d{2}", decoded)
    if not date_match:
        return base_url

    new_date_bytes = target_date.strftime("%Y-%m-%d").encode("ascii")
    updated = decoded[: date_match.start()] + new_date_bytes + decoded[date_match.end() :]
    new_tfs = base64.urlsafe_b64encode(updated).decode("ascii").rstrip("=")

    query["tfs"] = [new_tfs]
    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))




def extract_year_from_url(base_url: str) -> Optional[int]:
    """Try to recover the departure year embedded inside the tfs parameter."""
    parsed = urllib.parse.urlparse(base_url)
    query = urllib.parse.parse_qs(parsed.query)
    tfs_value = query.get("tfs", [None])[0]
    if not tfs_value:
        return None
    match = re.search(r"Egoy[A-Za-z0-9_-]{4}", tfs_value)
    if not match:
        return None
    chunk = match.group(0)
    pad = "=" * ((4 - len(chunk) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(chunk + pad)
    except (binascii.Error, ValueError):
        return None
    year_match = re.search(rb"(20\d{2})", decoded)
    if year_match:
        return int(year_match.group(1).decode())
    return None


def label_to_date(label: str, year: int) -> date:
    """Convert a date label like 'Wed, Oct 8' into a date object."""
    try:
        _dow, month_day = label.split(', ')
    except ValueError:
        raise ValueError(f"Unexpected date label format: {label!r}") from None
    parts = month_day.split(' ')
    if len(parts) != 2:
        raise ValueError(f"Unexpected month/day format in label: {label!r}")
    month_name, day_str = parts
    try:
        month = datetime.strptime(month_name, '%b').month
    except ValueError:
        month = datetime.strptime(month_name, '%B').month
    day = int(day_str)
    return date(year, month, day)


def date_to_label(target: date) -> str:
    return f"{target.strftime('%a')}, {target.strftime('%b')} {target.day}"


def shift_year_safe(target: date, offset: int) -> date:
    year = target.year + offset
    try:
        return target.replace(year=year)
    except ValueError:
        # handle Feb 29 -> Feb 28 fallback
        return target.replace(year=year, day=target.day - 1)

def configure_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,1080")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(180)
    return driver


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ").strip()
    text = re.sub(r"([AP]M)(\+\d)", r"\1 \2", text)
    return text


def extract_airlines(container) -> str:
    try:
        airline_block = container.find_element(By.CSS_SELECTOR, ".Ir0Voe > .sSHqwe.tPgKwe.ogfYpf")
    except NoSuchElementException:
        return "Unknown"

    spans = airline_block.find_elements(By.TAG_NAME, "span")
    names: List[str] = []
    for span in spans:
        value = normalise(span.text)
        if value and value not in names:
            names.append(value)
    if not names:
        names.append(normalise(airline_block.text))
    return " + ".join(names) if names else "Unknown"


def _parse_date_fragment(fragment: str, travel_year: int) -> str:
    match = re.search(r"on ([A-Za-z]+, [A-Za-z]+ \d{1,2})", fragment)
    if not match:
        return ""
    date_text = match.group(1).strip()
    for fmt in ("%A, %B %d", "%A, %b %d", "%a, %B %d", "%a, %b %d"):
        try:
            return datetime.strptime(f"{date_text} {travel_year}", fmt + " %Y").date().isoformat()
        except ValueError:
            continue
    return ""


def _parse_dates_from_label(label: str, travel_year: int) -> Tuple[str, str]:
    label = label.replace("\u202f", " ")
    if " and arrives " in label:
        dep_fragment, arr_fragment = label.split(" and arrives ", 1)
    else:
        dep_fragment, arr_fragment = label, ""

    dep_iso = _parse_date_fragment(dep_fragment, travel_year)
    arr_iso = _parse_date_fragment(arr_fragment, travel_year)

    if dep_iso and arr_iso:
        dep_dt = datetime.fromisoformat(dep_iso)
        arr_dt = datetime.fromisoformat(arr_iso)
        while arr_dt < dep_dt:
            arr_dt += timedelta(days=1)
        arr_iso = arr_dt.date().isoformat()

    return dep_iso, arr_iso


def extract_times(container, travel_year: int) -> Dict[str, str]:
    times = container.find_elements(By.CSS_SELECTOR, ".zxVSec span[role='text']")
    depart = normalise(times[0].text) if times else ""
    arrive = normalise(times[1].text) if len(times) > 1 else ""

    dep_date_iso = ""
    arr_date_iso = ""
    try:
        label_span = container.find_element(By.CSS_SELECTOR, ".zxVSec.YMlIz.tPgKwe.ogfYpf .mv1WYe")
        label = label_span.get_attribute("aria-label") or ""
    except NoSuchElementException:
        label = ""

    if label:
        dep_date_iso, arr_date_iso = _parse_dates_from_label(normalise(label), travel_year)

    if dep_date_iso and not arr_date_iso:
        increment_match = re.search(r"\+(\d)", arrive)
        if increment_match:
            dep_dt = datetime.fromisoformat(dep_date_iso)
            arr_date_iso = (dep_dt + timedelta(days=int(increment_match.group(1)))).date().isoformat()

    return {
        "departure": depart,
        "arrival": arrive,
        "departure_date": dep_date_iso,
        "arrival_date": arr_date_iso,
    }




def normalise_output_rows(raw_rows: List[Dict[str, Optional[str]]], target_date: date) -> List[Dict[str, str]]:
    final: List[Dict[str, str]] = []
    for row in raw_rows:
        departure_date = row.get("departure_date") or target_date.isoformat()
        arrival_label = row.get("arrival") or ""
        arrival_date = row.get("arrival_date") or ""
        if arrival_date:
            if arrival_label:
                arrival_display = f"{arrival_label} ({arrival_date})"
            else:
                arrival_display = arrival_date
        else:
            arrival_display = arrival_label

        stops_text = row.get("stops_text") or ""
        if stops_text:
            transit = stops_text
        elif row.get("stops_count") == 0:
            transit = "Nonstop"
        else:
            transit = "Unknown"

        final.append(
            {
                "Maskapai": row.get("airlines", ""),
                "Tanggal": departure_date,
                "Waktu Berangkat": row.get("departure", ""),
                "Waktu Datang": arrival_display,
                "Durasi": row.get("duration", ""),
                "Transit": transit,
                "Harga Tiket": row.get("price", ""),
            }
        )
    return final

def extract_duration(container) -> str:
    try:
        return normalise(container.find_element(By.CSS_SELECTOR, ".gvkrdb.AdWm1c.tPgKwe.ogfYpf").text)
    except NoSuchElementException:
        return ""


def extract_stops(container) -> Dict[str, Optional[int]]:
    try:
        stops_text = normalise(
            container.find_element(By.CSS_SELECTOR, ".EfT7Ae.AdWm1c.tPgKwe span.ogfYpf").text
        )
    except NoSuchElementException:
        return {"stops_text": "", "stops_count": None}

    lower = stops_text.lower()
    if "nonstop" in lower:
        count = 0
    else:
        match = re.search(r"(\d+)", stops_text)
        count = int(match.group(1)) if match else None
    return {"stops_text": stops_text, "stops_count": count}


def extract_price(container) -> str:
    try:
        price_span = container.find_element(By.CSS_SELECTOR, ".YMlIz.FpEdX span")
        return normalise(price_span.text)
    except NoSuchElementException:
        return ""


def gather_cards(driver, max_results: int, travel_year: int) -> List[Dict[str, Optional[str]]]:
    wait = WebDriverWait(driver, 45)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[jscontroller='yGdjUc']")))
    except TimeoutException:
        return []

    seen_ids: set[Optional[str]] = set()
    results: List[Dict[str, Optional[str]]] = []

    view_more_locators = [
        (By.XPATH, "//button[.//span[contains(text(),'More flights')]]"),
        (By.XPATH, "//button[.//span[contains(text(),'View more flights')]]"),
        (By.XPATH, "//button[.//span[contains(text(),'Show more flights')]]"),
        (By.XPATH, "//div[@role='button'][.//span[contains(text(),'More flights')]]"),
    ]

    while True:
        cards = driver.find_elements(By.CSS_SELECTOR, "div[jscontroller='yGdjUc']")
        for card in cards:
            card_id = card.get_attribute("data-id")
            if card_id in seen_ids:
                continue
            try:
                price = extract_price(card)
                airlines = extract_airlines(card)
                times = extract_times(card, travel_year)
                duration = extract_duration(card)
                stops = extract_stops(card)
            except StaleElementReferenceException:
                continue

            results.append(
                {
                    "airlines": airlines,
                    "price": price,
                    "departure": times.get("departure", ""),
                    "departure_date": times.get("departure_date", ""),
                    "arrival": times.get("arrival", ""),
                    "arrival_date": times.get("arrival_date", ""),
                    "duration": duration,
                    "stops_text": stops.get("stops_text", ""),
                    "stops_count": stops.get("stops_count"),
                }
            )
            seen_ids.add(card_id)

            if max_results and len(results) >= max_results:
                return results

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)

        clicked_more = False
        for by, locator in view_more_locators:
            elements = driver.find_elements(by, locator)
            for element in elements:
                if not element.is_displayed():
                    continue
                try:
                    driver.execute_script("arguments[0].click();", element)
                except Exception:
                    continue
                time.sleep(1.5)
                clicked_more = True
                break
            if clicked_more:
                break
        if clicked_more:
            continue

        prev_count = len(cards)
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(1.2)
        if len(driver.find_elements(By.CSS_SELECTOR, "div[jscontroller='yGdjUc']")) <= prev_count:
            break

    return results


def format_output(rows: List[Dict[str, str]]) -> None:
    if not rows:
        print("No flight results captured.")
        return

    headers = [
        "Maskapai",
        "Tanggal",
        "Waktu Berangkat",
        "Waktu Datang",
        "Durasi",
        "Transit",
        "Harga Tiket",
    ]
    widths = [len(h) for h in headers]

    for row in rows:
        widths[0] = max(widths[0], len(row.get("Maskapai", "")))
        widths[1] = max(widths[1], len(row.get("Tanggal", "")))
        widths[2] = max(widths[2], len(row.get("Waktu Berangkat", "")))
        widths[3] = max(widths[3], len(row.get("Waktu Datang", "")))
        widths[4] = max(widths[4], len(row.get("Durasi", "")))
        widths[5] = max(widths[5], len(row.get("Transit", "")))
        widths[6] = max(widths[6], len(row.get("Harga Tiket", "")))

    row_format = (
        f"{{:<{widths[0]}}}  {{:<{widths[1]}}}  {{:<{widths[2]}}}  "
        f"{{:<{widths[3]}}}  {{:<{widths[4]}}}  {{:<{widths[5]}}}  {{:<{widths[6]}}}"
    )

    print(row_format.format(*headers))
    print("-" * (sum(widths) + 12))
    for row in rows:
        print(
            row_format.format(
                row.get("Maskapai", ""),
                row.get("Tanggal", ""),
                row.get("Waktu Berangkat", ""),
                row.get("Waktu Datang", ""),
                row.get("Durasi", ""),
                row.get("Transit", ""),
                row.get("Harga Tiket", ""),
            )
        )


def write_csv(rows: List[Dict[str, str]], path: str) -> None:
    fieldnames = [
        "Maskapai",
        "Tanggal",
        "Waktu Berangkat",
        "Waktu Datang",
        "Durasi",
        "Transit",
        "Harga Tiket",
    ]
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = parse_arguments()

    if args.dates:
        dates: List[date] = []
        for chunk in args.dates.split(','):
            value = chunk.strip()
            if not value:
                continue
            try:
                dates.append(datetime.fromisoformat(value).date())
            except ValueError as exc:
                raise SystemExit(f"Invalid date in --dates: {value}") from exc
    elif args.range_start and args.range_end:
        try:
            start = datetime.fromisoformat(args.range_start).date()
            end = datetime.fromisoformat(args.range_end).date()
        except ValueError as exc:
            raise SystemExit("Invalid --range-start or --range-end format; use YYYY-MM-DD") from exc
        if end < start:
            raise SystemExit("--range-end must be on or after --range-start")
        days = (end - start).days
        dates = [start + timedelta(days=offset) for offset in range(days + 1)]
    else:
        base_year = extract_year_from_url(args.url) or datetime.now().year
        base_date = label_to_date(args.target_date, base_year)
        offsets = []
        for chunk in args.year_offsets.split(','):
            value = chunk.strip()
            if not value:
                continue
            try:
                offsets.append(int(value))
            except ValueError as exc:
                raise SystemExit(f"Invalid year offset: {value}") from exc
        if not offsets:
            offsets = [0]
        dates = [shift_year_safe(base_date, offset) for offset in offsets]

    unique_dates: List[date] = []
    seen_dates = set()
    for dt in dates:
        if dt not in seen_dates:
            unique_dates.append(dt)
            seen_dates.add(dt)

    driver = configure_driver(headless=args.headless)
    all_rows: List[Dict[str, str]] = []
    try:
        for dt in unique_dates:
            url = build_url_for_date(args.url, dt)
            driver.get(url)
            raw_rows = gather_cards(driver, args.max_results, dt.year)
            normalised = normalise_output_rows(raw_rows, dt)
            if normalised:
                print(f"Collected {len(normalised)} flights for {dt.isoformat()}")
            else:
                print(f"No flights found for {dt.isoformat()}")
            all_rows.extend(normalised)
    finally:
        driver.quit()

    if not args.no_table:
        format_output(all_rows)
    else:
        print(f"Total flights collected: {len(all_rows)} across {len(unique_dates)} dates.")

    if args.csv_output:
        write_csv(all_rows, args.csv_output)
        print(f"\nSaved {len(all_rows)} flight rows to {args.csv_output}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
