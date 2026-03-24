#!/usr/bin/env python3
"""
Insider Alert Dashboard
Reads insider_alerts.csv and displays a live terminal dashboard.
Usage: python3 alert_dashboard.py --alerts insider_alerts.csv [--watch]
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone
from collections import Counter


def load_alerts(filepath):
    """Load alerts from CSV."""
    if not os.path.exists(filepath):
        return []

    alerts = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            alerts.append(row)
    return alerts


def display_dashboard(alerts, clear=True):
    """Render terminal dashboard."""
    if clear:
        os.system('clear' if os.name != 'nt' else 'cls')

    print("=" * 70)
    print("  POLYMARKET INSIDER ALERT DASHBOARD")
    print(f"  Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if not alerts:
        print("\n  No alerts found.\n")
        return

    # Summary stats
    types = Counter(a.get('alert_type', 'UNKNOWN') for a in alerts)
    severities = Counter(a.get('severity', 'UNKNOWN') for a in alerts)
    addresses = set(a.get('address', '') for a in alerts)

    print(f"\n  Total Alerts: {len(alerts)}")
    print(f"  Unique Addresses: {len(addresses)}")
    print(f"\n  By Type:")
    for t, count in types.most_common():
        print(f"    {t}: {count}")
    print(f"\n  By Severity:")
    for s, count in severities.most_common():
        indicator = {"HIGH": "!!!", "MEDIUM": "!!", "LOW": "!"}.get(s, "?")
        print(f"    {indicator} {s}: {count}")

    # Recent alerts (last 20)
    print(f"\n  {'─' * 66}")
    print(f"  RECENT ALERTS (last 20)")
    print(f"  {'─' * 66}")

    recent = alerts[-20:]
    for a in reversed(recent):
        severity = a.get('severity', '?')
        alert_type = a.get('alert_type', '?')
        address = a.get('address', '?')[:12]
        details = a.get('details', '')[:40]
        ts = a.get('timestamp', '')[:19]

        color_code = {
            'HIGH': '\033[91m',      # red
            'MEDIUM': '\033[93m',    # yellow
            'LOW': '\033[92m',       # green
        }.get(severity, '\033[0m')

        print(f"  {color_code}[{severity:>6}]\033[0m {ts} "
              f"{alert_type:<25} {address}... {details}")

    # Top flagged addresses
    addr_counts = Counter(a.get('address', '') for a in alerts)
    top_addrs = addr_counts.most_common(5)
    if top_addrs:
        print(f"\n  {'─' * 66}")
        print(f"  TOP FLAGGED ADDRESSES")
        print(f"  {'─' * 66}")
        for addr, count in top_addrs:
            high_count = sum(1 for a in alerts
                           if a.get('address') == addr and a.get('severity') == 'HIGH')
            print(f"    {addr[:20]}...  {count} alerts ({high_count} HIGH)")

    print(f"\n{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description="Insider Alert Dashboard")
    parser.add_argument("--alerts", required=True, help="Path to insider_alerts.csv")
    parser.add_argument("--watch", action="store_true", help="Auto-refresh every 30s")
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                alerts = load_alerts(args.alerts)
                display_dashboard(alerts, clear=True)
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
    else:
        alerts = load_alerts(args.alerts)
        display_dashboard(alerts, clear=False)


if __name__ == "__main__":
    main()
```
