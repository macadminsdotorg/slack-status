#!/usr/bin/env python3
"""Generate the MacAdmins Slack statistics dashboard.

Reads a snapshot JSON file, merges it into the historical data store,
and generates a static HTML dashboard with interactive charts.

Usage:
    python generate-dashboard.py --snapshot-file output/snapshot.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
HISTORY_FILE = DATA_DIR / "history.json"
DASHBOARD_FILE = DOCS_DIR / "index.html"


def load_history() -> dict:
    """Load existing history or create a new structure."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"workspace": "macadmins", "snapshots": []}


def save_history(history: dict):
    """Write history back to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def upsert_snapshot(history: dict, snapshot: dict) -> dict:
    """Add or replace a snapshot in the history by date."""
    date = snapshot.get("date")
    snapshots = history["snapshots"]

    # Replace existing snapshot for same date
    snapshots = [s for s in snapshots if s.get("date") != date]
    snapshots.append(snapshot)

    # Sort chronologically
    snapshots.sort(key=lambda s: s.get("date", ""))
    history["snapshots"] = snapshots
    return history


def generate_dashboard(history: dict):
    """Generate the static HTML dashboard from historical data."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    snapshots = history.get("snapshots", [])
    latest = snapshots[-1] if snapshots else {}

    # Extract current stats for the header cards
    membership = latest.get("membership", {})
    channels = latest.get("channels", {})
    activity = latest.get("activity", {})
    generated = latest.get("generated", "")

    try:
        last_updated = datetime.fromisoformat(generated).strftime("%-d %B %Y")
    except (ValueError, TypeError):
        last_updated = latest.get("date", "Unknown")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MacAdmins Slack -- Workspace Statistics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        :root {{
            --bg-primary: #0a0e14;
            --bg-secondary: #0d1117;
            --bg-panel: #0f1419;
            --bg-card: #131920;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-blue: #58a6ff;
            --accent-sky: #0ea5e9;
            --accent-green: #3fb950;
            --accent-amber: #d29922;
            --accent-red: #da3633;
            --accent-purple: #a855f7;
            --accent-teal: #10b981;
            --border-subtle: #161b22;
            --border: #1a2028;
            --border-emphasis: #2d333b;
            --grid-line: #1a2028;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 14px 14px;
        }}

        header {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            padding: 10px 0;
            margin-bottom: 14px;
            border-bottom: 1px solid var(--border);
        }}

        header h1 {{
            font-size: 15px;
            font-weight: 600;
            letter-spacing: 0.02em;
        }}

        header .updated {{
            color: var(--text-muted);
            font-size: 11px;
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 10px;
            margin-bottom: 14px;
        }}

        .card {{
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 10px;
        }}

        .card .label {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 4px;
            display: block;
        }}

        .card .value {{
            font-size: 22px;
            font-weight: 600;
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace;
            color: var(--text-primary);
            display: block;
            line-height: 1.2;
        }}

        .card .status-dot {{
            display: inline-block;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            margin-right: 4px;
            vertical-align: middle;
            position: relative;
            top: -1px;
        }}

        .card:nth-child(1) .status-dot {{ background: var(--accent-blue); }}
        .card:nth-child(2) .status-dot {{ background: var(--accent-green); }}
        .card:nth-child(3) .status-dot {{ background: var(--accent-sky); }}
        .card:nth-child(4) .status-dot {{ background: var(--accent-purple); }}
        .card:nth-child(5) .status-dot {{ background: var(--accent-teal); }}
        .card:nth-child(6) .status-dot {{ background: var(--accent-amber); }}

        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 14px;
        }}

        .chart-section {{
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 10px;
        }}

        .chart-section h2 {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .chart-container {{
            position: relative;
            width: 100%;
            height: 220px;
        }}

        .no-data {{
            text-align: center;
            color: var(--text-muted);
            padding: 2rem;
            font-size: 11px;
        }}

        footer {{
            text-align: center;
            padding: 10px 0;
            border-top: 1px solid var(--border-subtle);
            color: var(--text-muted);
            font-size: 11px;
        }}

        @media (max-width: 900px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        @media (max-width: 600px) {{
            .cards {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>MacAdmins Slack -- Workspace Statistics</h1>
            <span class="updated">updated {last_updated}</span>
        </header>

        <div class="cards">
            <div class="card">
                <span class="label"><span class="status-dot"></span>Active Members</span>
                <span class="value">{membership.get('active', 0):,}</span>
            </div>
            <div class="card">
                <span class="label"><span class="status-dot"></span>Active Channels</span>
                <span class="value">{channels.get('active_channels', 0):,}</span>
            </div>
            <div class="card">
                <span class="label"><span class="status-dot"></span>Messages (daily)</span>
                <span class="value">{activity.get('channel_messages_posted', activity.get('messages_posted', 0)):,}</span>
            </div>
            <div class="card">
                <span class="label"><span class="status-dot"></span>Daily Viewers</span>
                <span class="value">{activity.get('channel_unique_viewers', 0):,}</span>
            </div>
            <div class="card">
                <span class="label"><span class="status-dot"></span>Daily Posters</span>
                <span class="value">{activity.get('channel_unique_posters', 0):,}</span>
            </div>
            <div class="card">
                <span class="label"><span class="status-dot"></span>Reactions (daily)</span>
                <span class="value">{activity.get('channel_reactions', activity.get('reactions_added', 0)):,}</span>
            </div>
        </div>

        <div class="charts-grid">
            <div class="chart-section">
                <h2>Membership Over Time</h2>
                <div class="chart-container">
                    <canvas id="membershipChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <h2>Channels Over Time</h2>
                <div class="chart-container">
                    <canvas id="channelsChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <h2>Daily Activity Over Time</h2>
                <div class="chart-container">
                    <canvas id="activityChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <h2>Daily Engagement Over Time</h2>
                <div class="chart-container">
                    <canvas id="engagementChart"></canvas>
                </div>
            </div>
        </div>

        <footer>
            Data collected weekly via GitHub Actions -- sourced from the Slack API
        </footer>
    </div>

    <script>
    const DATA = {json.dumps(snapshots)};

    Chart.defaults.font.family = "'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace";
    Chart.defaults.font.size = 10;

    const CHART_DEFAULTS = {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{
            mode: 'index',
            intersect: false,
        }},
        plugins: {{
            legend: {{
                labels: {{
                    color: '#8b949e',
                    usePointStyle: true,
                    pointStyle: 'circle',
                    padding: 12,
                    font: {{ size: 10 }},
                }},
            }},
            tooltip: {{
                backgroundColor: '#0d1117',
                borderColor: '#2d333b',
                borderWidth: 1,
                titleColor: '#c9d1d9',
                bodyColor: '#c9d1d9',
                titleFont: {{ size: 10 }},
                bodyFont: {{ size: 10 }},
                padding: 8,
                callbacks: {{
                    label: function(context) {{
                        let value = context.parsed.y;
                        if (value === null || value === undefined) return '';
                        return context.dataset.label + ': ' + value.toLocaleString();
                    }},
                }},
            }},
        }},
        scales: {{
            x: {{
                ticks: {{ color: '#6e7681', font: {{ size: 10 }} }},
                grid: {{ color: '#1a2028' }},
                border: {{ color: '#1a2028' }},
            }},
            y: {{
                ticks: {{
                    color: '#6e7681',
                    font: {{ size: 10 }},
                    callback: function(value) {{
                        return value.toLocaleString();
                    }},
                }},
                grid: {{ color: '#1a2028' }},
                border: {{ color: '#1a2028' }},
                beginAtZero: false,
            }},
        }},
    }};

    function getField(snapshot, path) {{
        let parts = path.split('.');
        let val = snapshot;
        for (let p of parts) {{
            if (!val) return null;
            val = val[p];
        }}
        return val !== undefined ? val : null;
    }}

    function buildChart(canvasId, labels, datasets) {{
        if (labels.length < 1) {{
            let container = document.getElementById(canvasId).parentElement;
            container.innerHTML = '<div class="no-data">Insufficient data for trends -- check back after more weekly snapshots have been collected.</div>';
            return;
        }}

        let ctx = document.getElementById(canvasId).getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{ labels: labels, datasets: datasets }},
            options: CHART_DEFAULTS,
        }});
    }}

    let dates = DATA.map(s => s.date);

    buildChart('membershipChart', dates, [
        {{
            label: 'Active Members',
            data: DATA.map(s => getField(s, 'membership.active')),
            borderColor: '#58a6ff',
            backgroundColor: 'rgba(88, 166, 255, 0.08)',
            fill: true,
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 3,
            pointBackgroundColor: '#58a6ff',
        }},
        {{
            label: 'Total Registered',
            data: DATA.map(s => getField(s, 'membership.total_registered')),
            borderColor: '#6e7681',
            borderDash: [4, 3],
            tension: 0.3,
            borderWidth: 1,
            pointRadius: 2,
            pointBackgroundColor: '#6e7681',
        }},
        {{
            label: 'Deactivated',
            data: DATA.map(s => getField(s, 'membership.deactivated')),
            borderColor: '#da3633',
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 2,
            pointBackgroundColor: '#da3633',
        }},
    ]);

    buildChart('channelsChart', dates, [
        {{
            label: 'Active Channels',
            data: DATA.map(s => getField(s, 'channels.active_channels')),
            borderColor: '#3fb950',
            backgroundColor: 'rgba(63, 185, 80, 0.08)',
            fill: true,
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 3,
            pointBackgroundColor: '#3fb950',
        }},
        {{
            label: 'Archived Channels',
            data: DATA.map(s => getField(s, 'channels.archived_channels')),
            borderColor: '#d29922',
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 2,
            pointBackgroundColor: '#d29922',
        }},
    ]);

    buildChart('activityChart', dates, [
        {{
            label: 'Messages Posted',
            data: DATA.map(s => getField(s, 'activity.channel_messages_posted') || getField(s, 'activity.messages_posted')),
            borderColor: '#0ea5e9',
            backgroundColor: 'rgba(14, 165, 233, 0.08)',
            fill: true,
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 3,
            pointBackgroundColor: '#0ea5e9',
        }},
        {{
            label: 'Reactions Added',
            data: DATA.map(s => getField(s, 'activity.channel_reactions') || getField(s, 'activity.reactions_added')),
            borderColor: '#d29922',
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 2,
            pointBackgroundColor: '#d29922',
        }},
    ]);

    buildChart('engagementChart', dates, [
        {{
            label: 'Unique Viewers',
            data: DATA.map(s => getField(s, 'activity.channel_unique_viewers')),
            borderColor: '#a855f7',
            backgroundColor: 'rgba(168, 85, 247, 0.08)',
            fill: true,
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 3,
            pointBackgroundColor: '#a855f7',
        }},
        {{
            label: 'Unique Posters',
            data: DATA.map(s => getField(s, 'activity.channel_unique_posters')),
            borderColor: '#10b981',
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 2,
            pointBackgroundColor: '#10b981',
        }},
    ]);
    </script>
</body>
</html>"""

    with open(DASHBOARD_FILE, "w") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description="Generate MacAdmins Slack statistics dashboard")
    parser.add_argument("--snapshot-file", required=True, help="Path to the snapshot JSON file")
    args = parser.parse_args()

    # Load snapshot
    snapshot_path = Path(args.snapshot_file)
    if not snapshot_path.exists():
        print(f"Error: Snapshot file not found: {snapshot_path}", file=sys.stderr)
        sys.exit(1)

    with open(snapshot_path) as f:
        snapshot = json.load(f)

    print(f"Loaded snapshot for {snapshot.get('date', 'unknown date')}", file=sys.stderr)

    # Load history, upsert, save
    history = load_history()
    history = upsert_snapshot(history, snapshot)
    save_history(history)
    print(f"History updated: {len(history['snapshots'])} snapshot(s)", file=sys.stderr)

    # Generate dashboard
    generate_dashboard(history)
    print(f"Dashboard written to {DASHBOARD_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
