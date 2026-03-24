#!/usr/bin/env python3
"""
Polymarket Liquidity Checker
Scans active markets and reports liquidity metrics.
Usage: python3 liquidity_checker.py [--min-volume 1000] [--category crypto]
"""

import argparse
import requests
import json
import sys
from datetime import datetime, timezone


def get_active_markets(category=None, min_volume=1000):
    """Fetch active markets from Gamma API."""
    params = {"active": "true", "closed": "false", "limit": 100}
    if category:
        params["tag_slug"] = category

    resp = requests.get(
        "https://gamma-api.polymarket.com/events",
        params=params,
        timeout=15
    )
    resp.raise_for_status()
    events = resp.json()

    markets = []
    for event in events:
        for m in event.get("markets", []):
            vol = float(m.get("volume", 0))
            if vol >= min_volume:
                markets.append({
                    "question": m.get("question", ""),
                    "condition_id": m.get("conditionId", ""),
                    "token_ids": m.get("clobTokenIds", []),
                    "volume": vol,
                    "outcome_prices": m.get("outcomePrices", "[]"),
                    "end_date": m.get("end_date_iso", ""),
                })
    return markets


def check_orderbook(token_id):
    """Get orderbook depth for a token."""
    try:
        resp = requests.get(
            "https://clob.polymarket.com/book",
            params={"token_id": token_id},
            timeout=10
        )
        resp.raise_for_status()
        book = resp.json()

        bids = book.get("bids", [])
        asks = book.get("asks", [])

        best_bid = float(bids[0]["price"]) if bids else 0
        best_ask = float(asks[0]["price"]) if asks else 1
        spread = best_ask - best_bid

        bid_depth = sum(float(b["size"]) * float(b["price"]) for b in bids[:5])
        ask_depth = sum(float(a["size"]) * float(a["price"]) for a in asks[:5])

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "bid_depth_usd": bid_depth,
            "ask_depth_usd": ask_depth,
            "total_depth_usd": bid_depth + ask_depth,
            "num_bids": len(bids),
            "num_asks": len(asks),
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Polymarket Liquidity Scanner")
    parser.add_argument("--category", default=None, help="Market category filter")
    parser.add_argument("--min-volume", type=float, default=1000, help="Minimum volume USD")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print(f"Scanning Polymarket markets (category={args.category}, min_vol=${args.min_volume:,.0f})...")
    markets = get_active_markets(args.category, args.min_volume)
    print(f"Found {len(markets)} markets\n")

    results = []
    for i, market in enumerate(markets[:20]):  # limit to 20 to avoid rate limits
        token_ids = market["token_ids"]
        if not token_ids:
            continue

        book = check_orderbook(token_ids[0])
        if "error" in book:
            continue

        result = {**market, **book}
        results.append(result)

        if not args.json:
            tradeable = "YES" if (
                book["spread"] <= 0.15 and
                book["total_depth_usd"] >= 50 and
                book["best_bid"] >= 0.05 and
                book["best_ask"] <= 0.95
            ) else "NO"

            print(f"[{i+1}] {market['question'][:60]}")
            print(f"    Spread: {book['spread']:.3f} | "
                  f"Depth: ${book['total_depth_usd']:.0f} | "
                  f"Tradeable: {tradeable}")
            print()

    if args.json:
        print(json.dumps(results, indent=2))

    # Summary
    tradeable_count = sum(1 for r in results
                         if r["spread"] <= 0.15 and r["total_depth_usd"] >= 50)
    print(f"\n--- Summary ---")
    print(f"Markets scanned: {len(results)}")
    print(f"Tradeable (spread<=0.15, depth>=$50): {tradeable_count}")
    print(f"Filtered out: {len(results) - tradeable_count}")


if __name__ == "__main__":
    main()
```
