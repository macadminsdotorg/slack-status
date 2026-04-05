#!/usr/bin/env python3
"""Backfill historical channel analytics into history.json.

Fetches daily channel analytics from the Slack API for a date range
and merges them into the existing history. Since users.list only
returns current state, membership data is not backfilled.

Usage:
    python backfill-history.py --from 2025-03-03 --to 2026-04-02
"""

import argparse
import gzip
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent
HISTORY_FILE = BASE_DIR / "data" / "history.json"


def fetch_channel_analytics(token: str, date: str) -> dict:
    """Fetch channel analytics for a single date."""
    url = "https://slack.com/api/admin.analytics.getFile?" + urlencode({
        "type": "public_channel",
        "date": date,
    })
    req = Request(url, headers={"Authorization": f"Bearer {token}"})

    try:
        resp = urlopen(req)
        raw = resp.read()
    except Exception as e:
        print(f"  [!] HTTP error: {e}", file=sys.stderr)
        return None

    try:
        body = gzip.decompress(raw).decode("utf-8")
    except (gzip.BadGzipFile, OSError):
        body = raw.decode("utf-8")

    try:
        data = json.loads(body)
        if isinstance(data, dict) and not data.get("ok", True):
            return None
    except json.JSONDecodeError:
        pass

    lines = body.strip().split("\n")
    records = [json.loads(line) for line in lines if line.strip()]

    ch_messages = sum(r.get("messages_posted_count", 0) for r in records)
    ch_reactions = sum(r.get("reactions_added_count", 0) for r in records)
    ch_files = sum(r.get("files_added_count", 0) for r in records)
    ch_viewers = sum(r.get("members_who_viewed_count", 0) for r in records)
    ch_posters = sum(r.get("members_who_posted_count", 0) for r in records)

    return {
        "date": date,
        "source": "public_channel",
        "channels_in_analytics": len(records),
        "channel_messages_posted": ch_messages,
        "channel_files_shared": ch_files,
        "channel_reactions": ch_reactions,
        "channel_unique_viewers": ch_viewers,
        "channel_unique_posters": ch_posters,
        "messages_posted": ch_messages,
        "reactions_added": ch_reactions,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill historical analytics")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between API calls (default: 1.5)")
    args = parser.parse_args()

    token = os.getenv("SLACK_USER_TOKEN")
    if not token:
        print("Error: SLACK_USER_TOKEN required.", file=sys.stderr)
        sys.exit(1)

    # Load existing history
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    else:
        history = {"workspace": "macadmins", "snapshots": []}

    existing_dates = {s["date"] for s in history["snapshots"]}

    start = datetime.strptime(args.from_date, "%Y-%m-%d")
    end = datetime.strptime(args.to_date, "%Y-%m-%d")
    total_days = (end - start).days + 1

    print(f"Backfilling {total_days} days from {args.from_date} to {args.to_date}", file=sys.stderr)

    added = 0
    skipped = 0
    failed = 0

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")

        if date_str in existing_dates:
            print(f"  {date_str}: already exists, skipping", file=sys.stderr)
            skipped += 1
            current += timedelta(days=1)
            continue

        activity = fetch_channel_analytics(token, date_str)

        if activity is None:
            print(f"  {date_str}: no data available", file=sys.stderr)
            failed += 1
            current += timedelta(days=1)
            time.sleep(args.delay)
            continue

        snapshot = {
            "date": date_str,
            "generated": f"{date_str}T10:00:00",
            "activity": activity,
        }

        history["snapshots"].append(snapshot)
        existing_dates.add(date_str)
        added += 1

        msgs = activity["channel_messages_posted"]
        viewers = activity["channel_unique_viewers"]
        print(f"  {date_str}: {msgs:,} messages, {viewers:,} viewers", file=sys.stderr)

        current += timedelta(days=1)
        time.sleep(args.delay)

    # Sort and save
    history["snapshots"].sort(key=lambda s: s.get("date", ""))

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nDone: {added} added, {skipped} skipped, {failed} failed", file=sys.stderr)
    print(f"Total snapshots: {len(history['snapshots'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
