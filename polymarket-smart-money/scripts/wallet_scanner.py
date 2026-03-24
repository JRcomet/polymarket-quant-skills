#!/usr/bin/env python3
"""
Polymarket Wallet Scanner
Discovers and scores profitable wallets from leaderboard data.
Usage: python3 wallet_scanner.py [--min-win-rate 0.55] [--min-trades 10] [--json]
"""

import argparse
import requests
import json
import time
import sys
from datetime import datetime, timezone


def fetch_leaderboard(limit=100):
    """Fetch top wallets from Polymarket leaderboard."""
    try:
        resp = requests.get(
            "https://data-api.polymarket.com/leaderboard",
            params={"limit": limit, "window": "all"},
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching leaderboard: {e}", file=sys.stderr)
        return []


def score_wallet(entry):
    """Score a wallet on multiple dimensions (0-1 each)."""
    win_rate = float(entry.get('win_rate', 0))
    volume = float(entry.get('volume', 0))
    profit = float(entry.get('profit', 0))
    num_trades = int(entry.get('num_trades', 0))

    # Reputation (win rate + track record)
    wr_score = min(max((win_rate - 0.5) / 0.3, 0), 1.0)
    volume_score = min(num_trades / 100, 1.0)
    reputation = wr_score * 0.6 + volume_score * 0.4

    # Size (meaningful capital)
    if volume >= 100000:
        size = 1.0
    elif volume >= 10000:
        size = 0.7
    elif volume >= 1000:
        size = 0.4
    else:
        size = 0.1

    # Efficiency (profit per trade)
    ppt = profit / num_trades if num_trades > 0 else 0
    if ppt >= 50:
        efficiency = 1.0
    elif ppt >= 10:
        efficiency = 0.7
    elif ppt >= 1:
        efficiency = 0.4
    elif ppt >= 0:
        efficiency = 0.2
    else:
        efficiency = 0.0

    # Composite
    composite = reputation * 0.40 + size * 0.25 + efficiency * 0.35

    # Tier
    if composite >= 0.8:
        tier = "S"
    elif composite >= 0.6:
        tier = "A"
    elif composite >= 0.4:
        tier = "B"
    elif composite >= 0.2:
        tier = "C"
    else:
        tier = "D"

    return {
        'composite': round(composite, 3),
        'reputation': round(reputation, 3),
        'size': round(size, 3),
        'efficiency': round(efficiency, 3),
        'tier': tier,
    }


def main():
    parser = argparse.ArgumentParser(description="Polymarket Wallet Scanner")
    parser.add_argument("--min-win-rate", type=float, default=0.55)
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print(f"Scanning Polymarket leaderboard (top {args.limit})...")
    leaderboard = fetch_leaderboard(args.limit)
    print(f"Fetched {len(leaderboard)} entries\n")

    results = []
    for entry in leaderboard:
        win_rate = float(entry.get('win_rate', 0))
        num_trades = int(entry.get('num_trades', 0))

        if win_rate < args.min_win_rate or num_trades < args.min_trades:
            continue

        score = score_wallet(entry)
        result = {
            'address': entry.get('address', ''),
            'win_rate': win_rate,
            'num_trades': num_trades,
            'volume': float(entry.get('volume', 0)),
            'profit': float(entry.get('profit', 0)),
            **score,
        }
        results.append(result)

    # Sort by composite score
    results.sort(key=lambda x: x['composite'], reverse=True)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"{'Tier':<5} {'Score':<7} {'WR':<7} {'Trades':<8} {'Profit':<12} {'Address'}")
        print("-" * 80)
        for r in results[:30]:
            print(f"  {r['tier']:<3} {r['composite']:.3f}  "
                  f"{r['win_rate']:.1%}  {r['num_trades']:<6}  "
                  f"${r['profit']:>9,.0f}  {r['address'][:16]}...")

    # Summary
    tier_counts = {}
    for r in results:
        tier_counts[r['tier']] = tier_counts.get(r['tier'], 0) + 1

    print(f"\n--- Summary ---")
    print(f"Qualified wallets: {len(results)}")
    print(f"Tier distribution: {dict(sorted(tier_counts.items()))}")
    print(f"Top profit: ${results[0]['profit']:,.0f}" if results else "No results")


if __name__ == "__main__":
    main()
```
