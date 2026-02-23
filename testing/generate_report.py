"""
VRIDDHI API TESTING FRAMEWORK - Report Generator

Purpose: Generate HTML reports from JSON test results with
charts, statistics, and detailed test case information.

Usage:
    python -m testing.generate_report                    # Latest report
    python -m testing.generate_report path/to/report.json  # Specific report

Author: Claude
Date: 2025-02-23
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

REPORTS_DIR = Path(__file__).parent / "reports"


def get_latest_report() -> Path:
    """Find the most recent JSON report."""
    reports = list(REPORTS_DIR.glob("test_report_*.json"))
    if not reports:
        raise FileNotFoundError("No test reports found in reports/")
    return max(reports, key=lambda p: p.stat().st_mtime)


def generate_html_report(report_data: Dict[str, Any]) -> str:
    """Generate HTML report from JSON data."""

    suites = report_data.get("suites", [])

    # Calculate totals
    total_tests = sum(s.get("total_tests", 0) for s in suites)
    total_passed = sum(s.get("passed", 0) for s in suites)
    total_failed = sum(s.get("failed", 0) for s in suites)
    total_errors = sum(s.get("errors", 0) for s in suites)
    total_time = sum(s.get("total_time_ms", 0) for s in suites) / 1000

    pass_rate = (total_passed / max(1, total_tests)) * 100

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VRIDDHI API Test Report</title>
    <style>
        :root {{
            --primary: #4f46e5;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --muted: #64748b;
            --border: #e2e8f0;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            margin-bottom: 2rem;
        }}

        h1 {{
            color: var(--primary);
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .timestamp {{
            color: var(--muted);
            font-size: 0.875rem;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .summary-card {{
            background: var(--card);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .summary-card h3 {{
            font-size: 2.5rem;
            margin-bottom: 0.25rem;
        }}

        .summary-card p {{
            color: var(--muted);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .summary-card.success h3 {{ color: var(--success); }}
        .summary-card.warning h3 {{ color: var(--warning); }}
        .summary-card.danger h3 {{ color: var(--danger); }}
        .summary-card.primary h3 {{ color: var(--primary); }}

        .progress-bar {{
            background: var(--border);
            border-radius: 999px;
            height: 8px;
            margin: 1rem 0;
            overflow: hidden;
        }}

        .progress-bar-fill {{
            height: 100%;
            border-radius: 999px;
            transition: width 0.3s;
        }}

        .suite {{
            background: var(--card);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .suite-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}

        .suite-title {{
            font-size: 1.25rem;
            font-weight: 600;
        }}

        .suite-endpoint {{
            font-family: monospace;
            background: var(--bg);
            padding: 0.25rem 0.75rem;
            border-radius: 6px;
            font-size: 0.875rem;
            color: var(--primary);
        }}

        .suite-stats {{
            display: flex;
            gap: 2rem;
            margin-bottom: 1rem;
        }}

        .stat {{
            text-align: center;
        }}

        .stat-value {{
            font-size: 1.5rem;
            font-weight: 600;
        }}

        .stat-label {{
            font-size: 0.75rem;
            color: var(--muted);
            text-transform: uppercase;
        }}

        .results-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}

        .results-table th {{
            text-align: left;
            padding: 0.75rem;
            background: var(--bg);
            font-weight: 500;
            color: var(--muted);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        .results-table td {{
            padding: 0.75rem;
            border-top: 1px solid var(--border);
        }}

        .results-table tr:hover {{
            background: var(--bg);
        }}

        .status-badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 500;
        }}

        .status-match {{ background: #dcfce7; color: #166534; }}
        .status-similar {{ background: #fef3c7; color: #92400e; }}
        .status-none {{ background: #f1f5f9; color: #475569; }}
        .status-error {{ background: #fee2e2; color: #dc2626; }}

        .query-text {{
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .type-badge {{
            display: inline-block;
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            background: var(--bg);
            color: var(--muted);
        }}

        .footer {{
            text-align: center;
            margin-top: 2rem;
            color: var(--muted);
            font-size: 0.875rem;
        }}

        .collapsible {{
            cursor: pointer;
        }}

        .collapsible:after {{
            content: ' ▼';
            font-size: 0.75rem;
        }}

        .results-wrapper {{
            max-height: 500px;
            overflow-y: auto;
        }}

        .chart-container {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin: 1rem 0;
        }}

        .donut-chart {{
            width: 120px;
            height: 120px;
            position: relative;
        }}

        .donut-chart svg {{
            transform: rotate(-90deg);
        }}

        .donut-center {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.25rem;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 VRIDDHI API Test Report</h1>
            <p class="timestamp">Generated: {report_data.get('generated_at', 'Unknown')}</p>
            <p class="timestamp">API: {report_data.get('api_url', 'Unknown')}</p>
        </header>

        <div class="summary-grid">
            <div class="summary-card primary">
                <h3>{total_tests}</h3>
                <p>Total Tests</p>
            </div>
            <div class="summary-card success">
                <h3>{total_passed}</h3>
                <p>Passed</p>
            </div>
            <div class="summary-card warning">
                <h3>{total_failed}</h3>
                <p>Failed</p>
            </div>
            <div class="summary-card danger">
                <h3>{total_errors}</h3>
                <p>Errors</p>
            </div>
            <div class="summary-card">
                <h3>{pass_rate:.1f}%</h3>
                <p>Pass Rate</p>
                <div class="progress-bar">
                    <div class="progress-bar-fill" style="width: {pass_rate}%; background: {'var(--success)' if pass_rate >= 70 else 'var(--warning)' if pass_rate >= 50 else 'var(--danger)'}"></div>
                </div>
            </div>
            <div class="summary-card">
                <h3>{total_time:.1f}s</h3>
                <p>Total Time</p>
            </div>
        </div>
"""

    # Add each suite
    for suite in suites:
        suite_name = suite.get("suite_name", "Unknown")
        endpoint = suite.get("endpoint", "")
        s_total = suite.get("total_tests", 0)
        s_passed = suite.get("passed", 0)
        s_failed = suite.get("failed", 0)
        s_errors = suite.get("errors", 0)
        avg_time = suite.get("avg_response_time_ms", 0)
        results = suite.get("results", [])

        html += f"""
        <div class="suite">
            <div class="suite-header">
                <span class="suite-title">{suite_name}</span>
                <span class="suite-endpoint">{endpoint}</span>
            </div>

            <div class="suite-stats">
                <div class="stat">
                    <div class="stat-value">{s_total}</div>
                    <div class="stat-label">Total</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: var(--success)">{s_passed}</div>
                    <div class="stat-label">Passed</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: var(--warning)">{s_failed}</div>
                    <div class="stat-label">Failed</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: var(--danger)">{s_errors}</div>
                    <div class="stat-label">Errors</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{avg_time:.0f}ms</div>
                    <div class="stat-label">Avg Time</div>
                </div>
            </div>

            <div class="results-wrapper">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Test ID</th>
                            <th>Type</th>
                            <th>Query</th>
                            <th>Status</th>
                            <th>Matches</th>
                            <th>Similar</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        for result in results[:100]:  # Limit to 100 per suite
            test_id = result.get("test_id", "")
            pair_type = result.get("pair_type", "")
            query = result.get("query", "")[:50]
            status = result.get("status", "")
            actual_match = result.get("actual_match", False)
            match_count = result.get("match_count", 0)
            similar_count = result.get("similar_count", 0)
            time_ms = result.get("response_time_ms", 0)

            if status == "error":
                status_class = "status-error"
                status_text = "Error"
            elif actual_match:
                status_class = "status-match"
                status_text = "Match"
            elif similar_count > 0:
                status_class = "status-similar"
                status_text = "Similar"
            else:
                status_class = "status-none"
                status_text = "No Match"

            html += f"""
                        <tr>
                            <td><code>{test_id}</code></td>
                            <td><span class="type-badge">{pair_type}</span></td>
                            <td class="query-text" title="{query}">{query}</td>
                            <td><span class="status-badge {status_class}">{status_text}</span></td>
                            <td>{match_count}</td>
                            <td>{similar_count}</td>
                            <td>{time_ms:.0f}ms</td>
                        </tr>
"""

        html += """
                    </tbody>
                </table>
            </div>
        </div>
"""

    html += """
        <footer>
            <p>Generated by VRIDDHI API Testing Framework</p>
        </footer>
    </div>
</body>
</html>
"""

    return html


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1])
    else:
        try:
            report_path = get_latest_report()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)

    print(f"Loading report: {report_path}")

    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    html = generate_html_report(report_data)

    # Save HTML
    html_path = report_path.with_suffix(".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML report saved: {html_path}")


if __name__ == "__main__":
    main()
