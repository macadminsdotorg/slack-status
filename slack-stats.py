#!/usr/bin/env python3
"""Slack workspace statistics gatherer for MacAdmins.

Pulls user, message, and file statistics from the Slack API using
admin.analytics and users.list endpoints.

Requires a User Token (xoxp-) with scopes:
    users:read, users:read.email, admin.analytics:read, files:read
"""

import csv
import gzip
import io
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()


def log(msg: str):
    """Print diagnostic messages to stderr so stdout stays clean for data."""
    print(msg, file=sys.stderr, flush=True)


class SlackStats:
    """Gathers and reports workspace statistics from Slack."""

    def __init__(self, user_token: str, bot_token: str = None):
        self.user_token = user_token
        self.user_client = WebClient(token=user_token)
        self.bot_client = WebClient(token=bot_token) if bot_token else self.user_client

    def get_user_stats(self) -> dict:
        """Fetch all users and compute membership statistics."""
        log("Fetching user list...")
        users = []
        cursor = None
        rate_limit_retries = 0
        max_rate_limit_retries = 5

        while True:
            try:
                kwargs = {"limit": 200}
                if cursor:
                    kwargs["cursor"] = cursor

                response = self.bot_client.users_list(**kwargs)
                members = response.get("members", [])
                users.extend(members)
                rate_limit_retries = 0

                log(f"  {len(users):,} users fetched...")

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

                time.sleep(1.5)

            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    rate_limit_retries += 1
                    if rate_limit_retries > max_rate_limit_retries:
                        log("  [!] Rate limit not clearing, skipping user stats.")
                        return None
                    retry_after = int(e.response.headers.get("Retry-After", 10))
                    log(f"  Rate limited, waiting {retry_after}s (attempt {rate_limit_retries}/{max_rate_limit_retries})...")
                    time.sleep(retry_after)
                    continue
                raise

        log(f"  Done: {len(users):,} total users fetched.")

        # Filter out Slackbot and workflow bots from the count
        real_users = [u for u in users if not u.get("is_bot") and u.get("id") != "USLACKBOT"]
        bots = [u for u in users if u.get("is_bot") or u.get("id") == "USLACKBOT"]

        active = [u for u in real_users if not u.get("deleted")]
        deactivated = [u for u in real_users if u.get("deleted")]
        admins = [u for u in active if u.get("is_admin")]
        owners = [u for u in active if u.get("is_owner")]
        primary_owner = [u for u in active if u.get("is_primary_owner")]

        # Guest breakdown
        ultra_restricted = [u for u in active if u.get("is_ultra_restricted")]
        restricted = [u for u in active if u.get("is_restricted") and not u.get("is_ultra_restricted")]

        full_members = [
            u for u in active
            if not u.get("is_restricted") and not u.get("is_ultra_restricted")
        ]

        return {
            "total_registered": len(real_users),
            "active": len(active),
            "deactivated": len(deactivated),
            "full_members": len(full_members),
            "guests_multi_channel": len(restricted),
            "guests_single_channel": len(ultra_restricted),
            "admins": len(admins),
            "owners": len(owners),
            "primary_owner": len(primary_owner),
            "bots": len(bots),
            "admin_names": [u.get("real_name", u.get("name", "Unknown")) for u in admins],
            "owner_names": [u.get("real_name", u.get("name", "Unknown")) for u in owners],
        }

    def _fetch_analytics_file(self, analytics_type: str, date: str) -> list:
        """Fetch an analytics file via direct HTTP (handles gzip responses).

        Args:
            analytics_type: 'member' or 'public_channel'.
            date: Date string in YYYY-MM-DD format.

        Returns:
            List of parsed JSON records, or None on error.
        """
        url = "https://slack.com/api/admin.analytics.getFile?" + urlencode({
            "type": analytics_type,
            "date": date,
        })
        req = Request(url, headers={
            "Authorization": f"Bearer {self.user_token}",
        })

        try:
            resp = urlopen(req)
            raw = resp.read()
        except Exception as e:
            log(f"  [!] HTTP error fetching {analytics_type} analytics: {e}")
            return None

        # Decompress if gzipped
        try:
            body = gzip.decompress(raw).decode("utf-8")
        except (gzip.BadGzipFile, OSError):
            body = raw.decode("utf-8")

        # Check for JSON error response
        try:
            data = json.loads(body)
            if isinstance(data, dict) and not data.get("ok", True):
                error = data.get("error", "unknown")
                log(f"  [!] {analytics_type} analytics error: {error}")
                return None
        except json.JSONDecodeError:
            pass

        # Parse NDJSON
        lines = body.strip().split("\n")
        return [json.loads(line) for line in lines if line.strip()]

    def get_analytics_stats(self, date: str = None) -> dict:
        """Fetch workspace analytics via admin.analytics.getFile.

        Tries member analytics first; falls back to channel analytics
        if member data is blocked (e.g. by email display settings).

        Args:
            date: Date string in YYYY-MM-DD format. Defaults to 2 days ago.

        Returns:
            Aggregated message and activity statistics.
        """
        if date is None:
            # Yesterday's data often isn't ready until late; default to 2 days ago
            date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

        result = {"date": date}

        # Try member analytics
        log(f"Fetching member analytics for {date}...")
        member_records = self._fetch_analytics_file("member", date)

        if member_records:
            total_messages = 0
            total_files = 0
            active_users = 0
            active_posters = 0
            active_readers = 0
            reactions_added = 0

            for record in member_records:
                msgs = record.get("messages_posted", 0)
                files = record.get("files_added_count", 0)
                total_messages += msgs
                total_files += files
                reactions_added += record.get("reactions_added_count", 0)

                if record.get("is_active", False):
                    active_users += 1
                if msgs > 0:
                    active_posters += 1
                if record.get("messages_read_count", 0) > 0:
                    active_readers += 1

            result.update({
                "source": "member",
                "members_in_analytics": len(member_records),
                "active_users": active_users,
                "active_posters": active_posters,
                "active_readers": active_readers,
                "messages_posted": total_messages,
                "files_shared": total_files,
                "reactions_added": reactions_added,
            })
        else:
            log("  Member analytics unavailable, trying channel analytics...")

        # Always fetch channel analytics for channel-level stats
        log(f"Fetching channel analytics for {date}...")
        channel_records = self._fetch_analytics_file("public_channel", date)

        if channel_records:
            ch_messages = sum(r.get("messages_posted_count", 0) for r in channel_records)
            ch_reactions = sum(r.get("reactions_added_count", 0) for r in channel_records)
            ch_files = sum(r.get("files_added_count", 0) for r in channel_records)
            ch_viewers = sum(r.get("members_who_viewed_count", 0) for r in channel_records)
            ch_posters = sum(r.get("members_who_posted_count", 0) for r in channel_records)

            result.update({
                "channels_in_analytics": len(channel_records),
                "channel_messages_posted": ch_messages,
                "channel_files_shared": ch_files,
                "channel_reactions": ch_reactions,
                "channel_unique_viewers": ch_viewers,
                "channel_unique_posters": ch_posters,
            })

            # If member analytics failed, use channel data as primary source
            if "source" not in result:
                result["source"] = "public_channel"
                result["messages_posted"] = ch_messages
                result["reactions_added"] = ch_reactions

        if len(result) <= 2:
            return None

        return result

    def get_file_stats(self) -> dict:
        """Fetch file statistics from files.list."""
        log("Fetching file statistics...")

        total_files = 0
        total_size = 0
        file_types = Counter()
        page = 1
        rate_limit_retries = 0

        while True:
            try:
                response = self.user_client.files_list(
                    count=100,
                    page=page,
                )

                files = response.get("files", [])
                paging = response.get("paging", {})

                for f in files:
                    total_files += 1
                    total_size += f.get("size", 0)
                    file_types[f.get("filetype", "unknown")] += 1

                if page >= paging.get("pages", 1):
                    break

                page += 1
                time.sleep(0.5)

            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    rate_limit_retries += 1
                    if rate_limit_retries > 5:
                        log("  [!] Rate limit not clearing, returning partial file stats.")
                        break
                    retry_after = int(e.response.headers.get("Retry-After", 10))
                    log(f"  Rate limited, waiting {retry_after}s (attempt {rate_limit_retries}/5)...")
                    time.sleep(retry_after)
                    continue
                elif e.response["error"] == "missing_scope":
                    log("  [!] files:read scope not available.")
                    return None
                raise

        total_from_paging = response.get("paging", {}).get("total", total_files)

        # Top 10 file types
        top_types = file_types.most_common(10)

        def format_size(size_bytes: int) -> str:
            for unit in ("B", "KB", "MB", "GB", "TB"):
                if size_bytes < 1024:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024
            return f"{size_bytes:.1f} PB"

        return {
            "total_files": total_from_paging,
            "total_size": format_size(total_size),
            "total_size_bytes": total_size,
            "top_file_types": top_types,
            "files_sampled": total_files,
        }

    def get_channel_stats(self) -> dict:
        """Fetch basic channel statistics."""
        log("Fetching channel statistics...")
        channels = []
        cursor = None
        rate_limit_retries = 0

        while True:
            try:
                kwargs = {"limit": 200, "exclude_archived": False}
                if cursor:
                    kwargs["cursor"] = cursor

                response = self.bot_client.conversations_list(**kwargs)
                channels.extend(response.get("channels", []))
                rate_limit_retries = 0

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

                time.sleep(1.5)

            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    rate_limit_retries += 1
                    if rate_limit_retries > 5:
                        log("  [!] Rate limit not clearing, skipping channel stats.")
                        return None
                    retry_after = int(e.response.headers.get("Retry-After", 10))
                    log(f"  Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                raise

        active = [c for c in channels if not c.get("is_archived")]
        archived = [c for c in channels if c.get("is_archived")]

        return {
            "total_channels": len(channels),
            "active_channels": len(active),
            "archived_channels": len(archived),
        }


def format_text_report(user_stats: dict, analytics: dict, file_stats: dict, channel_stats: dict) -> str:
    """Format statistics as a readable text report."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("MacAdmins Slack -- Workspace Statistics")
    lines.append(f"Generated: {now}")
    lines.append("=" * 50)

    if user_stats:
        lines.append("")
        lines.append("MEMBERSHIP")
        lines.append("-" * 30)
        lines.append(f"  Total registered:       {user_stats['total_registered']:,}")
        lines.append(f"  Active:                 {user_stats['active']:,}")
        lines.append(f"  Deactivated:            {user_stats['deactivated']:,}")
        lines.append(f"  Full members:           {user_stats['full_members']:,}")
        lines.append(f"  Multi-channel guests:   {user_stats['guests_multi_channel']:,}")
        lines.append(f"  Single-channel guests:  {user_stats['guests_single_channel']:,}")
        lines.append(f"  Bots:                   {user_stats['bots']:,}")
        lines.append("")
        lines.append("ADMINISTRATION")
        lines.append("-" * 30)
        lines.append(f"  Primary owner:          {user_stats['primary_owner']}")
        lines.append(f"  Owners:                 {user_stats['owners']}")
        lines.append(f"  Admins:                 {user_stats['admins']}")
        if user_stats["owner_names"]:
            lines.append(f"  Owner list:             {', '.join(user_stats['owner_names'])}")
        if user_stats["admin_names"]:
            lines.append(f"  Admin list:             {', '.join(user_stats['admin_names'])}")

    if channel_stats:
        lines.append("")
        lines.append("CHANNELS")
        lines.append("-" * 30)
        lines.append(f"  Total:                  {channel_stats['total_channels']:,}")
        lines.append(f"  Active:                 {channel_stats['active_channels']:,}")
        lines.append(f"  Archived:               {channel_stats['archived_channels']:,}")

    if analytics:
        source = analytics.get("source", "unknown")
        lines.append("")
        lines.append(f"ACTIVITY ({analytics['date']}, source: {source})")
        lines.append("-" * 30)

        if source == "member":
            lines.append(f"  Active users:           {analytics['active_users']:,}")
            lines.append(f"  Active posters:         {analytics['active_posters']:,}")
            lines.append(f"  Active readers:         {analytics['active_readers']:,}")
            lines.append(f"  Messages posted:        {analytics['messages_posted']:,}")
            lines.append(f"  Files shared:           {analytics['files_shared']:,}")
            lines.append(f"  Reactions added:        {analytics['reactions_added']:,}")

        if "channels_in_analytics" in analytics:
            lines.append(f"  Channels tracked:       {analytics['channels_in_analytics']:,}")
            lines.append(f"  Channel messages:       {analytics['channel_messages_posted']:,}")
            lines.append(f"  Channel files:          {analytics['channel_files_shared']:,}")
            lines.append(f"  Channel reactions:      {analytics['channel_reactions']:,}")
            lines.append(f"  Unique viewers:         {analytics['channel_unique_viewers']:,}")
            lines.append(f"  Unique posters:         {analytics['channel_unique_posters']:,}")

        if source == "public_channel" and "channels_in_analytics" not in analytics:
            lines.append(f"  Messages posted:        {analytics.get('messages_posted', 0):,}")
            lines.append(f"  Reactions added:        {analytics.get('reactions_added', 0):,}")

    if file_stats:
        lines.append("")
        lines.append("FILES (all time)")
        lines.append("-" * 30)
        lines.append(f"  Total files:            {file_stats['total_files']:,}")
        lines.append(f"  Total size:             {file_stats['total_size']}")
        if file_stats["top_file_types"]:
            lines.append("  Top file types:")
            for ftype, count in file_stats["top_file_types"]:
                lines.append(f"    {ftype:20s}  {count:,}")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def format_json_report(user_stats: dict, analytics: dict, file_stats: dict, channel_stats: dict) -> str:
    """Format statistics as JSON."""
    report = {
        "generated": datetime.now().isoformat(),
        "membership": user_stats,
        "channels": channel_stats,
        "activity": analytics,
        "files": file_stats,
    }
    return json.dumps(report, indent=2, default=str)


def format_csv_report(user_stats: dict, analytics: dict, file_stats: dict, channel_stats: dict) -> str:
    """Format key statistics as a flat CSV row."""
    output = io.StringIO()
    writer = csv.writer(output)

    headers = ["date"]
    values = [datetime.now().strftime("%Y-%m-%d")]

    if user_stats:
        for key in ("total_registered", "active", "deactivated", "full_members",
                     "guests_multi_channel", "guests_single_channel", "admins", "owners", "bots"):
            headers.append(key)
            values.append(user_stats.get(key, ""))

    if channel_stats:
        for key in ("total_channels", "active_channels", "archived_channels"):
            headers.append(key)
            values.append(channel_stats.get(key, ""))

    if analytics:
        for key in ("active_users", "active_posters", "active_readers",
                     "messages_posted", "files_shared", "reactions_added"):
            headers.append(key)
            values.append(analytics.get(key, ""))

    if file_stats:
        headers.append("total_files")
        values.append(file_stats.get("total_files", ""))
        headers.append("total_file_size_bytes")
        values.append(file_stats.get("total_size_bytes", ""))

    writer.writerow(headers)
    writer.writerow(values)
    return output.getvalue()


def format_snapshot(user_stats: dict, analytics: dict, channel_stats: dict) -> dict:
    """Build a snapshot dict suitable for historical storage.

    Strips PII (admin/owner names) and focuses on numeric data
    that is useful for trend analysis.
    """
    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated": datetime.now().isoformat(),
    }

    if user_stats:
        snapshot["membership"] = {
            k: v for k, v in user_stats.items()
            if k not in ("admin_names", "owner_names")
        }

    if channel_stats:
        snapshot["channels"] = channel_stats

    if analytics:
        snapshot["activity"] = analytics

    return snapshot


def main():
    user_token = os.getenv("SLACK_USER_TOKEN")
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    output_format = os.getenv("OUTPUT_FORMAT", "text").lower()
    output_file = os.getenv("OUTPUT_FILE")
    analytics_date = os.getenv("ANALYTICS_DATE")

    if not user_token:
        log("Error: SLACK_USER_TOKEN is required.")
        log("Copy .env.example to .env and fill in your token.")
        sys.exit(1)

    stats = SlackStats(user_token=user_token, bot_token=bot_token)

    # Analytics uses direct HTTP, not subject to SDK rate limits
    analytics = stats.get_analytics_stats(date=analytics_date)
    channel_stats = stats.get_channel_stats()

    # Skip slow file stats for snapshot format
    file_stats = None
    if output_format not in ("snapshot",):
        file_stats = stats.get_file_stats()

    user_stats = stats.get_user_stats()

    if output_format == "snapshot":
        snapshot = format_snapshot(user_stats, analytics, channel_stats)
        result = json.dumps(snapshot, indent=2)
    elif output_format == "json":
        result = format_json_report(user_stats, analytics, file_stats, channel_stats)
    elif output_format == "csv":
        result = format_csv_report(user_stats, analytics, file_stats, channel_stats)
    else:
        result = "\n" + format_text_report(user_stats, analytics, file_stats, channel_stats)

    if output_file:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w") as f:
            f.write(result)
        log(f"Output written to {output_file}")
    else:
        print(result)


if __name__ == "__main__":
    main()
