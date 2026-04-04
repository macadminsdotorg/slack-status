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
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MacAdmins Slack -- Workspace Statistics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script>
    /* Apply saved theme before first paint to prevent flash */
    (function() {{
        var t = localStorage.getItem('slack-stats-theme') || 'dark';
        document.documentElement.setAttribute('data-theme', t);
    }})();
    </script>
    <style>
        /* ---- Dark theme (default) ---- */
        :root, [data-theme="dark"] {{
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
            --tooltip-bg: #0d1117;
            --toggle-circle: #ffffff;
        }}

        /* ---- Light theme ---- */
        [data-theme="light"] {{
            --bg-primary: #f0f2f5;
            --bg-secondary: #ffffff;
            --bg-panel: #ffffff;
            --bg-card: #f6f8fa;
            --text-primary: #1a1a1a;
            --text-secondary: #555555;
            --text-muted: #6e7681;
            --accent-blue: #0969da;
            --accent-sky: #0284c7;
            --accent-green: #1a7f37;
            --accent-amber: #9a6700;
            --accent-red: #cf222e;
            --accent-purple: #8250df;
            --accent-teal: #0f766e;
            --border-subtle: #d8dee4;
            --border: #d0d7de;
            --border-emphasis: #afb8c1;
            --grid-line: #e4e6e9;
            --tooltip-bg: #ffffff;
            --toggle-circle: #ffffff;
        }}

        /* ---- System theme: inherit from OS preference ---- */
        [data-theme="system"] {{
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
            --tooltip-bg: #0d1117;
            --toggle-circle: #ffffff;
        }}

        @media (prefers-color-scheme: light) {{
            [data-theme="system"] {{
                --bg-primary: #f0f2f5;
                --bg-secondary: #ffffff;
                --bg-panel: #ffffff;
                --bg-card: #f6f8fa;
                --text-primary: #1a1a1a;
                --text-secondary: #555555;
                --text-muted: #6e7681;
                --accent-blue: #0969da;
                --accent-sky: #0284c7;
                --accent-green: #1a7f37;
                --accent-amber: #9a6700;
                --accent-red: #cf222e;
                --accent-purple: #8250df;
                --accent-teal: #0f766e;
                --border-subtle: #d8dee4;
                --border: #d0d7de;
                --border-emphasis: #afb8c1;
                --grid-line: #e4e6e9;
                --tooltip-bg: #ffffff;
                --toggle-circle: #ffffff;
            }}
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
            transition: background-color 0.15s ease, color 0.15s ease;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 14px 14px;
        }}

        header {{
            display: flex;
            align-items: center;
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

        .header-right {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        header .updated {{
            color: var(--text-muted);
            font-size: 11px;
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace;
        }}

        /* ---- Theme toggle (iOS-style, 3-state) ---- */
        .theme-toggle {{
            position: relative;
            width: 48px;
            height: 24px;
            border-radius: 12px;
            border: none;
            cursor: pointer;
            padding: 0;
            transition: background-color 0.3s ease;
            flex-shrink: 0;
        }}

        .toggle-circle {{
            position: absolute;
            left: 2px;
            top: 2px;
            width: 20px;
            height: 20px;
            background: var(--toggle-circle);
            border-radius: 50%;
            transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            pointer-events: none;
        }}

        .theme-label {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            flex-shrink: 0;
        }}

        /* Toggle states */
        [data-theme="dark"] .theme-toggle {{
            background: #58a6ff;
        }}
        [data-theme="dark"] .toggle-circle {{
            transform: translateX(24px);
        }}

        [data-theme="light"] .theme-toggle {{
            background: #d29922;
        }}
        [data-theme="light"] .toggle-circle {{
            transform: translateX(0);
        }}

        [data-theme="system"] .theme-toggle {{
            background: #6e7681;
        }}
        [data-theme="system"] .toggle-circle {{
            transform: translateX(12px);
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
            transition: background-color 0.15s ease, border-color 0.15s ease;
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
            transition: background-color 0.15s ease, border-color 0.15s ease;
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
            <div class="header-right">
                <span class="updated">updated {last_updated}</span>
                <span class="theme-label" id="themeLabel">dark</span>
                <button class="theme-toggle" id="themeToggle" title="Toggle theme (Dark / Light / System)" aria-label="Switch to light mode">
                    <span class="toggle-circle"></span>
                </button>
            </div>
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

    /* ---- Theme toggle ---- */
    const THEMES = ['dark', 'light', 'system'];
    const LABELS = {{ dark: 'Switch to light mode', light: 'Switch to system mode', system: 'Switch to dark mode' }};

    function getEffectiveTheme(theme) {{
        if (theme !== 'system') return theme;
        return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }}

    function getThemeColours() {{
        let s = getComputedStyle(document.documentElement);
        return {{
            text: s.getPropertyValue('--text-secondary').trim(),
            muted: s.getPropertyValue('--text-muted').trim(),
            grid: s.getPropertyValue('--grid-line').trim(),
            border: s.getPropertyValue('--border').trim(),
            tooltipBg: s.getPropertyValue('--tooltip-bg').trim(),
            tooltipBorder: s.getPropertyValue('--border-emphasis').trim(),
            tooltipText: s.getPropertyValue('--text-primary').trim(),
        }};
    }}

    function applyTheme(theme) {{
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('slack-stats-theme', theme);
        document.getElementById('themeLabel').textContent = theme;

        let btn = document.getElementById('themeToggle');
        btn.setAttribute('aria-label', LABELS[theme]);

        // Rebuild charts with new colours
        rebuildAllCharts();
    }}

    document.getElementById('themeToggle').addEventListener('click', function() {{
        let current = localStorage.getItem('slack-stats-theme') || 'dark';
        let next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
        applyTheme(next);
    }});

    // Respond to OS theme changes when in system mode
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function() {{
        if ((localStorage.getItem('slack-stats-theme') || 'dark') === 'system') {{
            rebuildAllCharts();
        }}
    }});

    // Set initial label
    (function() {{
        let t = localStorage.getItem('slack-stats-theme') || 'dark';
        document.getElementById('themeLabel').textContent = t;
        document.getElementById('themeToggle').setAttribute('aria-label', LABELS[t]);
    }})();

    /* ---- Chart setup ---- */
    Chart.defaults.font.family = "'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace";
    Chart.defaults.font.size = 10;

    let chartInstances = {{}};

    function getChartDefaults() {{
        let c = getThemeColours();
        return {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{
                legend: {{
                    labels: {{
                        color: c.text,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 12,
                        font: {{ size: 10 }},
                    }},
                }},
                tooltip: {{
                    backgroundColor: c.tooltipBg,
                    borderColor: c.tooltipBorder,
                    borderWidth: 1,
                    titleColor: c.tooltipText,
                    bodyColor: c.tooltipText,
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
                    ticks: {{ color: c.muted, font: {{ size: 10 }} }},
                    grid: {{ color: c.grid }},
                    border: {{ color: c.grid }},
                }},
                y: {{
                    ticks: {{
                        color: c.muted,
                        font: {{ size: 10 }},
                        callback: function(value) {{ return value.toLocaleString(); }},
                    }},
                    grid: {{ color: c.grid }},
                    border: {{ color: c.grid }},
                    beginAtZero: false,
                }},
            }},
        }};
    }}

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
            container.innerHTML = '<div class="no-data">Insufficient data for trends -- check back after more daily snapshots have been collected.</div>';
            return;
        }}

        if (chartInstances[canvasId]) {{
            chartInstances[canvasId].destroy();
        }}

        let ctx = document.getElementById(canvasId).getContext('2d');
        chartInstances[canvasId] = new Chart(ctx, {{
            type: 'line',
            data: {{ labels: labels, datasets: datasets }},
            options: getChartDefaults(),
        }});
    }}

    function rebuildAllCharts() {{
        /* Small delay so CSS variables resolve after data-theme change */
        requestAnimationFrame(function() {{
            let dates = DATA.map(s => s.date);

            let eff = getEffectiveTheme(localStorage.getItem('slack-stats-theme') || 'dark');
            let accentBlue = eff === 'light' ? '#0969da' : '#58a6ff';
            let accentGreen = eff === 'light' ? '#1a7f37' : '#3fb950';
            let accentAmber = eff === 'light' ? '#9a6700' : '#d29922';
            let accentRed = eff === 'light' ? '#cf222e' : '#da3633';
            let accentSky = eff === 'light' ? '#0284c7' : '#0ea5e9';
            let accentPurple = eff === 'light' ? '#8250df' : '#a855f7';
            let accentTeal = eff === 'light' ? '#0f766e' : '#10b981';
            let muted = eff === 'light' ? '#6e7681' : '#6e7681';

            buildChart('membershipChart', dates, [
                {{
                    label: 'Active Members',
                    data: DATA.map(s => getField(s, 'membership.active')),
                    borderColor: accentBlue,
                    backgroundColor: accentBlue + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentBlue,
                }},
                {{
                    label: 'Total Registered',
                    data: DATA.map(s => getField(s, 'membership.total_registered')),
                    borderColor: muted, borderDash: [4, 3],
                    tension: 0.3, borderWidth: 1,
                    pointRadius: 2, pointBackgroundColor: muted,
                }},
                {{
                    label: 'Deactivated',
                    data: DATA.map(s => getField(s, 'membership.deactivated')),
                    borderColor: accentRed,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentRed,
                }},
            ]);

            buildChart('channelsChart', dates, [
                {{
                    label: 'Active Channels',
                    data: DATA.map(s => getField(s, 'channels.active_channels')),
                    borderColor: accentGreen,
                    backgroundColor: accentGreen + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentGreen,
                }},
                {{
                    label: 'Archived Channels',
                    data: DATA.map(s => getField(s, 'channels.archived_channels')),
                    borderColor: accentAmber,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentAmber,
                }},
            ]);

            buildChart('activityChart', dates, [
                {{
                    label: 'Messages Posted',
                    data: DATA.map(s => getField(s, 'activity.channel_messages_posted') || getField(s, 'activity.messages_posted')),
                    borderColor: accentSky,
                    backgroundColor: accentSky + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentSky,
                }},
                {{
                    label: 'Reactions Added',
                    data: DATA.map(s => getField(s, 'activity.channel_reactions') || getField(s, 'activity.reactions_added')),
                    borderColor: accentAmber,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentAmber,
                }},
            ]);

            buildChart('engagementChart', dates, [
                {{
                    label: 'Unique Viewers',
                    data: DATA.map(s => getField(s, 'activity.channel_unique_viewers')),
                    borderColor: accentPurple,
                    backgroundColor: accentPurple + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentPurple,
                }},
                {{
                    label: 'Unique Posters',
                    data: DATA.map(s => getField(s, 'activity.channel_unique_posters')),
                    borderColor: accentTeal,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentTeal,
                }},
            ]);
        }});
    }}

    /* Initial render */
    rebuildAllCharts();
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
