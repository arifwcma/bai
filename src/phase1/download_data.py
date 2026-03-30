"""
Download GH Archive hourly JSON files.

GH Archive stores every public GitHub event as gzipped JSON,
one file per hour. Each line in the file is one JSON event object.

Usage:
    python src/phase1/download_data.py --date 2026-03-28 --hours 12 13 14

This downloads 3 hours of data from March 28, 2026 into data/.
"""

import argparse
import os
import sys
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
BASE_URL = "https://data.gharchive.org"


def download_hour(date: str, hour: int) -> str | None:
    """Download a single hourly archive file. Returns the local file path."""
    filename = f"{date}-{hour}.json.gz"
    url = f"{BASE_URL}/{filename}"
    local_path = os.path.join(DATA_DIR, filename)

    if os.path.exists(local_path):
        print(f"  Already exists: {filename}")
        return local_path

    print(f"  Downloading: {url}")
    resp = requests.get(url, stream=True)

    if resp.status_code != 200:
        print(f"  FAILED ({resp.status_code}): {url}")
        return None

    os.makedirs(DATA_DIR, exist_ok=True)
    total = 0
    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            total += len(chunk)
            print(f"\r  {filename}: {total / (1024*1024):.1f} MB downloaded", end="")
    print()
    return local_path


def main():
    parser = argparse.ArgumentParser(description="Download GH Archive data")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    parser.add_argument(
        "--hours",
        nargs="+",
        type=int,
        default=[12, 13, 14],
        help="Hour(s) to download (0-23). Default: 12 13 14",
    )
    args = parser.parse_args()

    print(f"Downloading GH Archive data for {args.date}, hours: {args.hours}")
    print(f"Saving to: {os.path.abspath(DATA_DIR)}\n")

    downloaded = []
    for hour in args.hours:
        path = download_hour(args.date, hour)
        if path:
            downloaded.append(path)

    print(f"\nDone. Downloaded {len(downloaded)}/{len(args.hours)} files.")
    for p in downloaded:
        size_mb = os.path.getsize(p) / (1024 * 1024)
        print(f"  {os.path.basename(p)}: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
