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
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3"></script>
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

        /* ---- Events toggle ---- */
        .events-toggle {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 4px;
            user-select: none;
        }}

        .events-toggle input {{
            accent-color: var(--accent-blue);
            cursor: pointer;
        }}

        .events-toggle input:checked + span {{
            color: var(--accent-blue);
        }}

        /* ---- View selector ---- */
        .view-selector {{
            display: flex;
            align-items: center;
            gap: 2px;
            border: 1px solid var(--border-emphasis);
            border-radius: 3px;
            overflow: hidden;
        }}

        .view-selector button {{
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            padding: 3px 8px;
            cursor: pointer;
            transition: background-color 0.15s ease, color 0.15s ease;
        }}

        .view-selector button:hover {{
            color: var(--text-primary);
        }}

        .view-selector button.active {{
            background: var(--accent-blue);
            color: #ffffff;
        }}

        [data-theme="light"] .view-selector button.active {{
            background: var(--accent-blue);
            color: #ffffff;
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

        .chart-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .chart-section h2 {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
            margin: 0;
        }}

        .expand-btn {{
            background: none;
            border: 1px solid var(--border-emphasis);
            border-radius: 3px;
            color: var(--text-muted);
            font-size: 10px;
            padding: 2px 8px;
            cursor: pointer;
            transition: color 0.15s ease, border-color 0.15s ease;
        }}

        .expand-btn:hover {{
            color: var(--text-primary);
            border-color: var(--text-secondary);
        }}

        .chart-container {{
            position: relative;
            width: 100%;
            height: 220px;
        }}

        /* ---- Fullscreen modal ---- */
        .modal-overlay {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.85);
            z-index: 1000;
            padding: 20px;
            justify-content: center;
            align-items: center;
        }}

        .modal-overlay.active {{
            display: flex;
        }}

        .modal-content {{
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 3px;
            width: 100%;
            height: 100%;
            max-width: 100%;
            max-height: 100%;
            padding: 14px;
            display: flex;
            flex-direction: column;
        }}

        .modal-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border-subtle);
            flex-shrink: 0;
        }}

        .modal-header h2 {{
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
            margin: 0;
        }}

        .modal-header .modal-hint {{
            font-size: 10px;
            color: var(--text-muted);
        }}

        .modal-close {{
            background: none;
            border: 1px solid var(--border-emphasis);
            border-radius: 3px;
            color: var(--text-muted);
            font-size: 11px;
            padding: 4px 12px;
            cursor: pointer;
            transition: color 0.15s ease, border-color 0.15s ease;
        }}

        .modal-close:hover {{
            color: var(--text-primary);
            border-color: var(--text-secondary);
        }}

        .modal-chart-container {{
            flex: 1;
            position: relative;
            min-height: 0;
        }}

        .no-data {{
            text-align: center;
            color: var(--text-muted);
            padding: 2rem;
            font-size: 11px;
        }}

        /* ---- Comparison panel ---- */
        .compare-panel {{
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 10px;
            margin-bottom: 14px;
            transition: background-color 0.15s ease, border-color 0.15s ease;
        }}

        .compare-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border-subtle);
            flex-wrap: wrap;
        }}

        .compare-header h2 {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
            margin-right: auto;
        }}

        .compare-header input[type="date"] {{
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace;
            font-size: 11px;
            padding: 4px 8px;
            background: var(--bg-primary);
            color: var(--text-primary);
            border: 1px solid var(--border-emphasis);
            border-radius: 3px;
            cursor: pointer;
            transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
            color-scheme: dark;
        }}

        [data-theme="light"] .compare-header input[type="date"] {{
            color-scheme: light;
        }}

        @media (prefers-color-scheme: light) {{
            [data-theme="system"] .compare-header input[type="date"] {{
                color-scheme: light;
            }}
        }}

        .compare-header input[type="date"]:focus {{
            outline: 1px solid var(--accent-blue);
        }}

        .compare-hint {{
            font-size: 10px;
            color: var(--text-muted);
            margin-left: auto;
        }}

        .compare-header label {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .compare-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}

        .compare-table th {{
            text-align: left;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-muted);
            padding: 4px 8px;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .compare-table td {{
            padding: 4px 8px;
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .compare-table td:first-child {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: var(--text-secondary);
        }}

        .compare-table tr:last-child td {{
            border-bottom: none;
        }}

        .delta-positive {{
            color: var(--accent-green);
        }}

        .delta-negative {{
            color: var(--accent-red);
        }}

        .delta-neutral {{
            color: var(--text-muted);
        }}

        .compare-empty {{
            color: var(--text-muted);
            font-size: 11px;
            padding: 10px 0;
            text-align: center;
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
                <div class="view-selector" id="viewSelector">
                    <button data-view="daily" class="active">daily</button>
                    <button data-view="weekly">weekly</button>
                    <button data-view="monthly">monthly</button>
                    <button data-view="annual">annual</button>
                </div>
                <label class="events-toggle" title="Overlay Apple events on charts">
                    <input type="checkbox" id="eventsToggle"> <span>events</span>
                </label>
                <span class="theme-label" id="themeLabel">dark</span>
                <button class="theme-toggle" id="themeToggle" title="Toggle theme (Dark / Light / System)" aria-label="Switch to light mode">
                    <span class="toggle-circle"></span>
                </button>
            </div>
        </header>

        <div class="cards">
            <div class="card" title="Full members, multi-channel guests, and single-channel guests who have not been deactivated. Excludes bots and Workflow Builder automations.">
                <span class="label"><span class="status-dot"></span>Active Members</span>
                <span class="value">{membership.get('active', 0):,}</span>
            </div>
            <div class="card" title="Public channels that have not been archived. Does not include private channels or direct messages.">
                <span class="label"><span class="status-dot"></span>Active Channels</span>
                <span class="value">{channels.get('active_channels', 0):,}</span>
            </div>
            <div class="card" title="Total messages posted across all public channels on the analytics date ({activity.get('date', 'N/A')}). Private channels and DMs are not included.">
                <span class="label"><span class="status-dot"></span>Messages (daily)</span>
                <span class="value">{activity.get('channel_messages_posted', activity.get('messages_posted', 0)):,}</span>
            </div>
            <div class="card" title="Unique members who viewed at least one public channel on the analytics date. A single member viewing multiple channels is counted once.">
                <span class="label"><span class="status-dot"></span>Daily Viewers</span>
                <span class="value">{activity.get('channel_unique_viewers', 0):,}</span>
            </div>
            <div class="card" title="Unique members who posted at least one message in a public channel on the analytics date. A single member posting in multiple channels is counted once.">
                <span class="label"><span class="status-dot"></span>Daily Posters</span>
                <span class="value">{activity.get('channel_unique_posters', 0):,}</span>
            </div>
            <div class="card" title="Total emoji reactions added across all public channels on the analytics date ({activity.get('date', 'N/A')}).">
                <span class="label"><span class="status-dot"></span>Reactions (daily)</span>
                <span class="value">{activity.get('channel_reactions', activity.get('reactions_added', 0)):,}</span>
            </div>
        </div>

        <div class="compare-panel">
            <div class="compare-header">
                <h2>Compare Snapshots</h2>
                <label for="compareFrom">From</label>
                <input type="date" id="compareFrom">
                <label for="compareTo">To</label>
                <input type="date" id="compareTo">
                <span class="compare-hint" id="compareHint">Selects nearest available snapshot</span>
            </div>
            <div id="compareBody">
                <div class="compare-empty">Select two different dates to compare.</div>
            </div>
        </div>

        <div class="charts-grid">
            <div class="chart-section">
                <div class="chart-header">
                    <h2 title="Active members, total registered, and deactivated accounts over time. Excludes bots and Workflow Builder automations.">Membership Over Time</h2>
                    <button class="expand-btn" data-chart="membershipChart" data-title="Membership Over Time">expand</button>
                </div>
                <div class="chart-container">
                    <canvas id="membershipChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <div class="chart-header">
                    <h2 title="Public channels only. Active channels are not archived; archived channels remain searchable but read-only.">Channels Over Time</h2>
                    <button class="expand-btn" data-chart="channelsChart" data-title="Channels Over Time">expand</button>
                </div>
                <div class="chart-container">
                    <canvas id="channelsChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <div class="chart-header">
                    <h2 title="Messages and reactions across all public channels per analytics date. Private channels and DMs are not included.">Daily Activity Over Time</h2>
                    <button class="expand-btn" data-chart="activityChart" data-title="Daily Activity Over Time">expand</button>
                </div>
                <div class="chart-container">
                    <canvas id="activityChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <div class="chart-header">
                    <h2 title="Unique viewers and posters per analytics date. Each member counted once regardless of how many channels they accessed.">Daily Engagement Over Time</h2>
                    <button class="expand-btn" data-chart="engagementChart" data-title="Daily Engagement Over Time">expand</button>
                </div>
                <div class="chart-container">
                    <canvas id="engagementChart"></canvas>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="chartModal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 id="modalTitle"></h2>
                    <span class="modal-hint">Drag to select, scroll to zoom, double-click to reset</span>
                    <label class="events-toggle" title="Overlay Apple events">
                        <input type="checkbox" id="modalEventsToggle"> <span>events</span>
                    </label>
                    <button class="modal-close" id="modalReset" style="margin-right: 6px;">reset zoom</button>
                    <button class="modal-close" id="modalClose">close</button>
                </div>
                <div class="modal-chart-container">
                    <canvas id="modalChart"></canvas>
                </div>
            </div>
        </div>

        <footer>
            Data collected daily via GitHub Actions via the Slack API
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

    /* ---- Apple events overlay ---- */
    const APPLE_EVENTS = [
        /* 2025 */
        {{ date: '2025-03-12', label: 'iOS 18.3.2', type: 'release' }},
        {{ date: '2025-03-31', label: 'iOS 18.4 / macOS 15.4', type: 'release' }},
        {{ date: '2025-06-09', label: 'WWDC 2025', type: 'event' }},
        {{ date: '2025-09-09', label: 'iPhone 17 Event', type: 'event' }},
        {{ date: '2025-09-15', label: 'iOS 26 / macOS Tahoe', type: 'release' }},
        {{ date: '2025-09-19', label: 'iPhone 17 Launch', type: 'launch' }},
        {{ date: '2025-10-15', label: 'M5 MacBook Pro / iPad Pro', type: 'launch' }},
        {{ date: '2025-10-22', label: 'M5 Devices Available', type: 'launch' }},
        {{ date: '2025-11-03', label: 'iOS 26.1 / macOS 26.1', type: 'release' }},
        {{ date: '2025-12-12', label: 'iOS 26.2 / macOS 26.2', type: 'release' }},
        /* 2026 */
        {{ date: '2026-02-11', label: 'iOS 26.3 / macOS 26.3', type: 'release' }},
        {{ date: '2026-03-04', label: 'Apple Experience Event', type: 'event' }},
        {{ date: '2026-03-11', label: 'iPhone 17e / MacBook Air M5', type: 'launch' }},
        {{ date: '2026-03-24', label: 'iOS 26.4 / macOS 26.4', type: 'release' }},
    ];

    const EVENT_COLOURS = {{
        event: {{ line: '#da3633', label: '#da3633' }},
        launch: {{ line: '#d29922', label: '#d29922' }},
        release: {{ line: '#6e7681', label: '#6e7681' }},
    }};

    let showEvents = false;

    /* Build a lookup from date string to list of events */
    let eventsByDate = {{}};
    APPLE_EVENTS.forEach(function(ev) {{
        if (!eventsByDate[ev.date]) eventsByDate[ev.date] = [];
        eventsByDate[ev.date].push(ev);
    }});

    function getEventsForIndex(dates, idx) {{
        if (!showEvents || idx < 0 || idx >= dates.length) return [];
        let dateStr = dates[idx];
        /* Exact match */
        if (eventsByDate[dateStr]) return eventsByDate[dateStr];
        /* For aggregated views, check if any events fall within the period label */
        let matches = [];
        APPLE_EVENTS.forEach(function(ev) {{
            if (dateStr.length === 7 && ev.date.startsWith(dateStr)) matches.push(ev);
            else if (dateStr.length === 4 && ev.date.startsWith(dateStr)) matches.push(ev);
            else if (dateStr.indexOf('-W') !== -1) {{
                /* Weekly: check if event's week key matches */
                let evWeek = getWeekKey(ev.date);
                if (evWeek === dateStr) matches.push(ev);
            }}
        }});
        return matches;
    }}

    function getEventAnnotations(dates) {{
        if (!showEvents) return {{}};

        let annotations = {{}};
        APPLE_EVENTS.forEach(function(ev, i) {{
            let idx = dates.indexOf(ev.date);
            if (idx === -1) {{
                /* Find nearest date in the dataset */
                let nearest = null;
                let minDist = Infinity;
                let evTime = new Date(ev.date).getTime();
                dates.forEach(function(d, j) {{
                    let dist = Math.abs(new Date(d).getTime() - evTime);
                    if (dist < minDist) {{ minDist = dist; nearest = j; }}
                }});
                if (nearest !== null && minDist < 3 * 86400000) idx = nearest;
            }}
            if (idx === -1) return;

            let colours = EVENT_COLOURS[ev.type] || EVENT_COLOURS.release;
            annotations['event' + i] = {{
                type: 'line',
                xMin: idx,
                xMax: idx,
                borderColor: colours.line,
                borderWidth: 1,
                borderDash: ev.type === 'release' ? [3, 3] : [],
            }};
        }});
        return annotations;
    }}

    function refreshAfterSettingsChange() {{
        let reopenId = currentModalChartId;
        let reopenTitle = currentModalTitle;
        rebuildAllCharts();
        if (reopenId) {{
            /* Reopen after rebuildAllCharts' requestAnimationFrame completes */
            requestAnimationFrame(function() {{
                requestAnimationFrame(function() {{
                    openModal(reopenId, reopenTitle);
                }});
            }});
        }}
    }}

    document.getElementById('eventsToggle').addEventListener('change', function() {{
        showEvents = this.checked;
        document.getElementById('modalEventsToggle').checked = showEvents;
        refreshAfterSettingsChange();
    }});

    document.getElementById('modalEventsToggle').addEventListener('change', function() {{
        showEvents = this.checked;
        document.getElementById('eventsToggle').checked = showEvents;
        refreshAfterSettingsChange();
    }});

    /* ---- View aggregation ---- */
    let currentView = localStorage.getItem('slack-stats-view') || 'daily';

    function getWeekKey(dateStr) {{
        let d = new Date(dateStr);
        let thu = new Date(d);
        thu.setDate(d.getDate() - ((d.getDay() + 6) % 7) + 3);
        let jan4 = new Date(thu.getFullYear(), 0, 4);
        let week = Math.ceil(((thu - jan4) / 86400000 + jan4.getDay() + 1) / 7);
        return thu.getFullYear() + '-W' + String(week).padStart(2, '0');
    }}

    function getMonthKey(dateStr) {{ return dateStr.substring(0, 7); }}
    function getYearKey(dateStr) {{ return dateStr.substring(0, 4); }}

    function aggregateData(view) {{
        if (view === 'daily') return DATA;

        let keyFn = view === 'weekly' ? getWeekKey : view === 'monthly' ? getMonthKey : getYearKey;
        let groups = {{}};

        DATA.forEach(function(s) {{
            let key = keyFn(s.date);
            if (!groups[key]) groups[key] = [];
            groups[key].push(s);
        }});

        let result = [];
        Object.keys(groups).sort().forEach(function(key) {{
            let items = groups[key];
            let merged = {{ date: key }};

            /* For membership/channels: take the last snapshot (point-in-time) */
            let last = items[items.length - 1];
            if (last.membership) merged.membership = last.membership;
            if (last.channels) merged.channels = last.channels;

            /* For activity: average across the period */
            let activityKeys = ['channel_messages_posted', 'channel_files_shared',
                'channel_reactions', 'channel_unique_viewers', 'channel_unique_posters',
                'messages_posted', 'reactions_added'];

            let hasActivity = items.some(function(s) {{ return s.activity; }});
            if (hasActivity) {{
                merged.activity = {{ date: key, source: 'public_channel' }};
                activityKeys.forEach(function(ak) {{
                    let vals = items.filter(function(s) {{ return s.activity && s.activity[ak] != null; }})
                                    .map(function(s) {{ return s.activity[ak]; }});
                    if (vals.length > 0) {{
                        merged.activity[ak] = Math.round(vals.reduce(function(a, b) {{ return a + b; }}, 0) / vals.length);
                    }}
                }});
            }}

            result.push(merged);
        }});

        return result;
    }}

    function setView(view) {{
        currentView = view;
        localStorage.setItem('slack-stats-view', view);
        document.querySelectorAll('.view-selector button').forEach(function(btn) {{
            btn.classList.toggle('active', btn.dataset.view === view);
        }});
        refreshAfterSettingsChange();
    }}

    /* Initialise view selector state */
    document.querySelectorAll('.view-selector button').forEach(function(btn) {{
        btn.classList.toggle('active', btn.dataset.view === currentView);
        btn.addEventListener('click', function() {{ setView(btn.dataset.view); }});
    }});

    /* ---- Chart setup ---- */
    Chart.defaults.font.family = "'SF Mono', 'Monaco', 'Cascadia Code', 'Consolas', monospace";
    Chart.defaults.font.size = 10;

    let chartInstances = {{}};

    function getChartDefaults(enableZoom, dates) {{
        let c = getThemeColours();
        let opts = {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{
                annotation: {{
                    annotations: dates ? getEventAnnotations(dates) : {{}},
                }},
                legend: {{
                    labels: {{
                        color: c.text,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 12,
                        font: {{ size: enableZoom ? 12 : 10 }},
                    }},
                }},
                tooltip: {{
                    backgroundColor: c.tooltipBg,
                    borderColor: c.tooltipBorder,
                    borderWidth: 1,
                    titleColor: c.tooltipText,
                    bodyColor: c.tooltipText,
                    titleFont: {{ size: enableZoom ? 12 : 10 }},
                    bodyFont: {{ size: enableZoom ? 12 : 10 }},
                    padding: enableZoom ? 12 : 8,
                    footerColor: c.muted,
                    footerFont: {{ size: enableZoom ? 10 : 9, style: 'italic' }},
                    callbacks: {{
                        afterTitle: function(tooltipItems) {{
                            if (!showEvents || !tooltipItems.length || !dates) return '';
                            let evts = getEventsForIndex(dates, tooltipItems[0].dataIndex);
                            if (evts.length === 0) return '';
                            let typeLabels = {{ event: 'EVENT', launch: 'LAUNCH', release: 'RELEASE' }};
                            return evts.map(function(ev) {{
                                return (typeLabels[ev.type] || 'EVENT') + ': ' + ev.label;
                            }}).join('\\n');
                        }},
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
                    ticks: {{ color: c.muted, font: {{ size: enableZoom ? 11 : 10 }} }},
                    grid: {{ color: c.grid }},
                    border: {{ color: c.grid }},
                }},
                y: {{
                    ticks: {{
                        color: c.muted,
                        font: {{ size: enableZoom ? 11 : 10 }},
                        callback: function(value) {{ return value.toLocaleString(); }},
                    }},
                    grid: {{ color: c.grid }},
                    border: {{ color: c.grid }},
                    beginAtZero: false,
                }},
            }},
        }};

        if (enableZoom) {{
            opts.plugins.zoom = {{
                pan: {{
                    enabled: true,
                    mode: 'x',
                }},
                zoom: {{
                    wheel: {{ enabled: true }},
                    pinch: {{ enabled: true }},
                    drag: {{
                        enabled: true,
                        backgroundColor: 'rgba(88, 166, 255, 0.15)',
                        borderColor: 'rgba(88, 166, 255, 0.4)',
                        borderWidth: 1,
                    }},
                    mode: 'x',
                }},
            }};
        }}

        return opts;
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

    let chartDatasets = {{}};

    function buildChart(canvasId, labels, datasets) {{
        if (labels.length < 1) {{
            let container = document.getElementById(canvasId).parentElement;
            container.innerHTML = '<div class="no-data">Insufficient data for trends -- check back after more daily snapshots have been collected.</div>';
            return;
        }}

        if (chartInstances[canvasId]) {{
            chartInstances[canvasId].destroy();
        }}

        /* Store dataset config for modal re-use */
        chartDatasets[canvasId] = {{ labels: labels, datasets: datasets }};

        let ctx = document.getElementById(canvasId).getContext('2d');
        chartInstances[canvasId] = new Chart(ctx, {{
            type: 'line',
            data: {{ labels: labels, datasets: datasets }},
            options: getChartDefaults(false, labels),
        }});
    }}

    function rebuildAllCharts() {{
        /* Small delay so CSS variables resolve after data-theme change */
        requestAnimationFrame(function() {{
            let viewData = aggregateData(currentView);
            let dates = viewData.map(s => s.date);

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
                    data: viewData.map(s => getField(s, 'membership.active')),
                    borderColor: accentBlue,
                    backgroundColor: accentBlue + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentBlue,
                }},
                {{
                    label: 'Total Registered',
                    data: viewData.map(s => getField(s, 'membership.total_registered')),
                    borderColor: muted, borderDash: [4, 3],
                    tension: 0.3, borderWidth: 1,
                    pointRadius: 2, pointBackgroundColor: muted,
                }},
                {{
                    label: 'Deactivated',
                    data: viewData.map(s => getField(s, 'membership.deactivated')),
                    borderColor: accentRed,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentRed,
                }},
            ]);

            buildChart('channelsChart', dates, [
                {{
                    label: 'Active Channels',
                    data: viewData.map(s => getField(s, 'channels.active_channels')),
                    borderColor: accentGreen,
                    backgroundColor: accentGreen + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentGreen,
                }},
                {{
                    label: 'Archived Channels',
                    data: viewData.map(s => getField(s, 'channels.archived_channels')),
                    borderColor: accentAmber,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentAmber,
                }},
            ]);

            buildChart('activityChart', dates, [
                {{
                    label: 'Messages Posted',
                    data: viewData.map(s => getField(s, 'activity.channel_messages_posted') || getField(s, 'activity.messages_posted')),
                    borderColor: accentSky,
                    backgroundColor: accentSky + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentSky,
                }},
                {{
                    label: 'Reactions Added',
                    data: viewData.map(s => getField(s, 'activity.channel_reactions') || getField(s, 'activity.reactions_added')),
                    borderColor: accentAmber,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentAmber,
                }},
            ]);

            buildChart('engagementChart', dates, [
                {{
                    label: 'Unique Viewers',
                    data: viewData.map(s => getField(s, 'activity.channel_unique_viewers')),
                    borderColor: accentPurple,
                    backgroundColor: accentPurple + '14',
                    fill: true, tension: 0.3, borderWidth: 1.5,
                    pointRadius: 3, pointBackgroundColor: accentPurple,
                }},
                {{
                    label: 'Unique Posters',
                    data: viewData.map(s => getField(s, 'activity.channel_unique_posters')),
                    borderColor: accentTeal,
                    tension: 0.3, borderWidth: 1.5,
                    pointRadius: 2, pointBackgroundColor: accentTeal,
                }},
            ]);
        }});
    }}

    /* Initial render */
    rebuildAllCharts();

    /* ---- Comparison panel ---- */
    const COMPARE_METRICS = [
        {{ label: 'Active Members', path: 'membership.active', tip: 'Non-deactivated human accounts. Excludes bots and Workflow Builder automations.' }},
        {{ label: 'Total Registered', path: 'membership.total_registered', tip: 'All human accounts ever created, including deactivated. Excludes bots.' }},
        {{ label: 'Deactivated', path: 'membership.deactivated', tip: 'Human accounts that have been deactivated by admins or by the user themselves.' }},
        {{ label: 'Full Members', path: 'membership.full_members', tip: 'Active members with full workspace access. Excludes single-channel and multi-channel guests.' }},
        {{ label: 'Admins', path: 'membership.admins', tip: 'Workspace administrators with elevated permissions for managing channels, members, and settings.' }},
        {{ label: 'Bots and Workflows', path: 'membership.bots', tip: 'Includes Workflow Builder automations (wf_bot / wb_bot accounts), app integrations (e.g. GitHub, Trello), and Slackbot.' }},
        {{ label: 'Active Channels', path: 'channels.active_channels', tip: 'Public channels that have not been archived. Does not include private channels or DMs.' }},
        {{ label: 'Archived Channels', path: 'channels.archived_channels', tip: 'Channels that have been archived. They remain searchable but no new messages can be posted.' }},
        {{ label: 'Messages Posted', path: 'activity.channel_messages_posted', tip: 'Total messages posted across all public channels on the analytics date. Private channels and DMs not included.' }},
        {{ label: 'Reactions', path: 'activity.channel_reactions', tip: 'Total emoji reactions added across all public channels on the analytics date.' }},
        {{ label: 'Unique Viewers', path: 'activity.channel_unique_viewers', tip: 'Unique members who viewed at least one public channel. Each member counted once regardless of how many channels viewed.' }},
        {{ label: 'Unique Posters', path: 'activity.channel_unique_posters', tip: 'Unique members who posted at least one message in a public channel. Each member counted once.' }},
    ];

    /* All snapshot dates sorted chronologically */
    const SNAPSHOT_DATES = DATA.map(function(s) {{ return s.date; }}).sort();

    function findNearestSnapshot(dateStr) {{
        /* Find the snapshot with the closest date to the given date string */
        if (!dateStr || SNAPSHOT_DATES.length === 0) return null;
        let target = new Date(dateStr).getTime();
        let best = null;
        let bestDist = Infinity;
        for (let i = 0; i < DATA.length; i++) {{
            let dist = Math.abs(new Date(DATA[i].date).getTime() - target);
            if (dist < bestDist) {{
                bestDist = dist;
                best = i;
            }}
        }}
        return best;
    }}

    function initCompareDates() {{
        let fromInput = document.getElementById('compareFrom');
        let toInput = document.getElementById('compareTo');

        if (SNAPSHOT_DATES.length === 0) return;

        let minDate = SNAPSHOT_DATES[0];
        let maxDate = SNAPSHOT_DATES[SNAPSHOT_DATES.length - 1];

        fromInput.min = minDate;
        fromInput.max = maxDate;
        toInput.min = minDate;
        toInput.max = maxDate;

        /* Default: oldest as "from", newest as "to" */
        fromInput.value = minDate;
        toInput.value = maxDate;
    }}

    function formatDelta(from, to) {{
        if (from === null || to === null || from === undefined || to === undefined) {{
            return '<span class="delta-neutral">--</span>';
        }}
        let diff = to - from;
        if (diff === 0) return '<span class="delta-neutral">0</span>';
        let sign = diff > 0 ? '+' : '';
        let cls = diff > 0 ? 'delta-positive' : 'delta-negative';
        return '<span class="' + cls + '">' + sign + diff.toLocaleString() + '</span>';
    }}

    function renderComparison() {{
        let fromDate = document.getElementById('compareFrom').value;
        let toDate = document.getElementById('compareTo').value;
        let body = document.getElementById('compareBody');
        let hint = document.getElementById('compareHint');

        if (!fromDate || !toDate) {{
            body.innerHTML = '<div class="compare-empty">Select two dates to compare.</div>';
            return;
        }}

        let fromIdx = findNearestSnapshot(fromDate);
        let toIdx = findNearestSnapshot(toDate);

        if (fromIdx === null || toIdx === null) {{
            body.innerHTML = '<div class="compare-empty">No snapshot data available.</div>';
            return;
        }}

        let snapA = DATA[fromIdx];
        let snapB = DATA[toIdx];

        if (snapA.date === snapB.date) {{
            body.innerHTML = '<div class="compare-empty">Both dates resolve to the same snapshot (' + snapA.date + '). Select a wider range.</div>';
            return;
        }}

        /* Show which actual snapshot dates were matched */
        let hintParts = [];
        if (snapA.date !== fromDate) hintParts.push('from matched to ' + snapA.date);
        if (snapB.date !== toDate) hintParts.push('to matched to ' + snapB.date);
        hint.textContent = hintParts.length > 0 ? 'Nearest: ' + hintParts.join(', ') : 'Selects nearest available snapshot';

        let html = '<table class="compare-table">';
        html += '<thead><tr><th>Metric</th><th>' + snapA.date + '</th><th>' + snapB.date + '</th><th>Change</th></tr></thead>';
        html += '<tbody>';

        COMPARE_METRICS.forEach(function(m) {{
            let valA = getField(snapA, m.path);
            let valB = getField(snapB, m.path);
            let fmtA = valA !== null && valA !== undefined ? valA.toLocaleString() : '--';
            let fmtB = valB !== null && valB !== undefined ? valB.toLocaleString() : '--';
            let tipAttr = m.tip ? ' title="' + m.tip.replace(/"/g, '&quot;') + '"' : '';
            html += '<tr' + tipAttr + '><td>' + m.label + '</td><td>' + fmtA + '</td><td>' + fmtB + '</td><td>' + formatDelta(valA, valB) + '</td></tr>';
        }});

        html += '</tbody></table>';
        body.innerHTML = html;
    }}

    initCompareDates();
    if (DATA.length > 1) {{
        renderComparison();
    }}
    document.getElementById('compareFrom').addEventListener('change', renderComparison);
    document.getElementById('compareTo').addEventListener('change', renderComparison);

    /* ---- Chart modal (expand) ---- */
    let modalChart = null;
    let currentModalChartId = null;
    let currentModalTitle = null;

    function openModal(chartId, title) {{
        currentModalChartId = chartId;
        currentModalTitle = title;
        document.getElementById('modalEventsToggle').checked = showEvents;
        let modal = document.getElementById('chartModal');
        let stored = chartDatasets[chartId];
        if (!stored) return;

        document.getElementById('modalTitle').textContent = title;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        /* Deep-clone datasets so modal doesn't share state with grid charts */
        let clonedDatasets = stored.datasets.map(function(ds) {{
            let clone = {{}};
            for (let k in ds) clone[k] = ds[k];
            /* Larger points in expanded view */
            clone.pointRadius = (ds.pointRadius || 3) + 1;
            clone.borderWidth = (ds.borderWidth || 1.5) + 0.5;
            return clone;
        }});

        requestAnimationFrame(function() {{
            if (modalChart) {{
                modalChart.destroy();
                modalChart = null;
            }}
            let ctx = document.getElementById('modalChart').getContext('2d');
            modalChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: stored.labels.slice(), datasets: clonedDatasets }},
                options: getChartDefaults(true, stored.labels),
            }});
        }});
    }}

    function closeModal() {{
        let modal = document.getElementById('chartModal');
        modal.classList.remove('active');
        document.body.style.overflow = '';
        currentModalChartId = null;
        currentModalTitle = null;
        if (modalChart) {{
            modalChart.destroy();
            modalChart = null;
        }}
    }}

    document.querySelectorAll('.expand-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            openModal(btn.dataset.chart, btn.dataset.title);
        }});
    }});

    document.getElementById('modalReset').addEventListener('click', function() {{
        if (modalChart) modalChart.resetZoom();
    }});
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('chartModal').addEventListener('click', function(e) {{
        if (e.target === this) closeModal();
    }});
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') closeModal();
    }});
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
