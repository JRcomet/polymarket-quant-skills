#!/usr/bin/env python3
"""
Simple Backtesting Framework for Polymarket Strategies
Reads trades_log.csv and calibration.csv to evaluate strategy performance.
Usage: python3 backtest.py --trades trades_log.csv --calibration calibration.csv
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime


def load_csv(filepath):
    """Load CSV file into list of dicts."""
    rows = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def analyze_trades(trades):
    """Compute trade-level statistics."""
    total = len(trades)
    if total == 0:
        return {"error": "No trades found"}

    # Parse numeric fields
    edges = []
    bet_sizes = []
    sides = defaultdict(int)

    for t in trades:
        try:
            edges.append(float(t.get('edge', 0)))
            bet_sizes.append(float(t.get('bet_size', 0)))
            sides[t.get('side', 'UNKNOWN')] += 1
        except (ValueError, TypeError):
            continue

    avg_edge = sum(edges) / len(edges) if edges else 0
    avg_bet = sum(bet_sizes) / len(bet_sizes) if bet_sizes else 0
    total_wagered = sum(bet_sizes)

    return {
        "total_trades": total,
        "avg_edge": round(avg_edge, 4),
        "avg_bet_size": round(avg_bet, 2),
        "total_wagered": round(total_wagered, 2),
        "max_edge": round(max(edges), 4) if edges else 0,
        "min_edge": round(min(edges), 4) if edges else 0,
        "side_distribution": dict(sides),
    }


def analyze_calibration(calibration):
    """Compute calibration metrics — predicted vs actual."""
    if not calibration:
        return {"error": "No calibration data"}

    buckets = defaultdict(lambda: {"correct": 0, "total": 0})

    for row in calibration:
        try:
            predicted = float(row.get('predicted_prob', row.get('our_prob', 0.5)))
            actual = int(row.get('actual_outcome', row.get('was_correct', 0)))

            # Bucket by 10% intervals
            bucket = round(predicted, 1)
            buckets[bucket]["total"] += 1
            if actual:
                buckets[bucket]["correct"] += 1
        except (ValueError, TypeError):
            continue

    calibration_table = {}
    for bucket in sorted(buckets.keys()):
        data = buckets[bucket]
        actual_rate = data["correct"] / data["total"] if data["total"] > 0 else 0
        calibration_table[f"{bucket:.1f}"] = {
            "predicted": bucket,
            "actual": round(actual_rate, 3),
            "n": data["total"],
            "calibration_error": round(abs(bucket - actual_rate), 3)
        }

    total_entries = sum(b["total"] for b in buckets.values())
    total_correct = sum(b["correct"] for b in buckets.values())
    overall_accuracy = total_correct / total_entries if total_entries > 0 else 0

    avg_cal_error = (
        sum(abs(k - v["correct"]/v["total"])
            for k, v in buckets.items() if v["total"] > 0)
        / len([v for v in buckets.values() if v["total"] > 0])
    ) if buckets else 0

    return {
        "total_predictions": total_entries,
        "overall_accuracy": round(overall_accuracy, 4),
        "avg_calibration_error": round(avg_cal_error, 4),
        "calibration_by_bucket": calibration_table
    }


def compute_pnl(trades):
    """Estimate P&L from trade outcomes (if available)."""
    total_pnl = 0
    wins = 0
    losses = 0

    for t in trades:
        pnl = t.get('pnl')
        if pnl is not None:
            try:
                pnl_val = float(pnl)
                total_pnl += pnl_val
                if pnl_val > 0:
                    wins += 1
                else:
                    losses += 1
            except (ValueError, TypeError):
                continue

    if wins + losses == 0:
        return {"note": "No P&L data available (DRY RUN mode?)"}

    return {
        "total_pnl": round(total_pnl, 2),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / (wins + losses), 4) if (wins + losses) > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Polymarket Strategy Backtester")
    parser.add_argument("--trades", required=True, help="Path to trades_log.csv")
    parser.add_argument("--calibration", default=None, help="Path to calibration.csv")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    trades = load_csv(args.trades)
    trade_stats = analyze_trades(trades)
    pnl_stats = compute_pnl(trades)

    cal_stats = {}
    if args.calibration:
        calibration = load_csv(args.calibration)
        cal_stats = analyze_calibration(calibration)

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "trade_statistics": trade_stats,
        "pnl": pnl_stats,
    }
    if cal_stats:
        report["calibration"] = cal_stats

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print("  POLYMARKET STRATEGY BACKTEST REPORT")
        print("=" * 60)
        print(f"\nTrades: {trade_stats.get('total_trades', 0)}")
        print(f"Avg Edge: {trade_stats.get('avg_edge', 0):.2%}")
        print(f"Avg Bet: ${trade_stats.get('avg_bet_size', 0):.2f}")
        print(f"Total Wagered: ${trade_stats.get('total_wagered', 0):.2f}")
        print(f"Side Split: {trade_stats.get('side_distribution', {})}")

        if "note" not in pnl_stats:
            print(f"\nP&L: ${pnl_stats.get('total_pnl', 0):.2f}")
            print(f"Win Rate: {pnl_stats.get('win_rate', 0):.1%}")
        else:
            print(f"\n{pnl_stats['note']}")

        if cal_stats and "calibration_by_bucket" in cal_stats:
            print(f"\nCalibration ({cal_stats.get('total_predictions', 0)} predictions):")
            print(f"  Overall Accuracy: {cal_stats.get('overall_accuracy', 0):.1%}")
            print(f"  Avg Cal Error: {cal_stats.get('avg_calibration_error', 0):.3f}")
            for bucket, data in cal_stats["calibration_by_bucket"].items():
                print(f"  {bucket}: predicted={data['predicted']:.0%}, "
                      f"actual={data['actual']:.0%}, n={data['n']}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
```
