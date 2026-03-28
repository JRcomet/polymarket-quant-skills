---
name: polymarket-smart-money
description: "Track profitable wallets and detect insider trading on Polymarket prediction markets. Multi-dimensional wallet scoring, whale alerts, pre-settlement pattern detection, and cross-bot signal export. Use when the user mentions smart money tracking, wallet profiling, copy trading, insider detection, or on-chain analytics for prediction markets."
---

# Polymarket Smart Money Tracker

A complete system for discovering, scoring, and monitoring profitable wallets on Polymarket's prediction market platform. Based on a production system that analyzed 211,000+ on-chain signals and generated 3,433 insider trading alerts.

## When to Use This Skill

Use this skill when the user wants to:
- Track profitable Polymarket wallets and follow their trades
- Detect insider trading or suspicious pre-settlement activity
- Build a wallet scoring and ranking system
- Analyze Polymarket leaderboard data
- Create alerts for whale movements on prediction markets
- Export smart money signals to other trading bots
- Understand on-chain prediction market dynamics

## System Architecture

```
Discovery Layer → Scoring Layer → Monitoring Layer → Alert Layer
  (find wallets)   (rank quality)  (real-time watch)  (act on signals)
```

### Discovery Layer
Find wallets worth tracking from multiple sources:
- Polymarket leaderboard API (top performers)
- On-chain transaction scanning (high-volume addresses)
- Winning streak detection (consistent profitability)

### Scoring Layer
Rank wallets by quality using a multi-dimensional score:
- **Reputation** (35%): Win rate, profit consistency, track record length
- **Timing** (30%): How early they enter before events resolve
- **Size** (20%): Average position size relative to market depth
- **Efficiency** (15%): Profit per trade, risk-adjusted returns

### Monitoring Layer
Real-time tracking of scored wallets:
- Poll Polymarket subgraph for new transactions
- Detect position changes (new entries, exits, size changes)
- Cross-reference with market close times

### Alert Layer
Generate actionable signals:
- **Insider Alert**: Large buy within 24h of settlement on correct side
- **Whale Alert**: Position exceeding threshold in any market
- **Consensus Alert**: Multiple tracked wallets taking same position
- **Exit Alert**: Smart money exiting a position (potential reversal)

## Core Components

### 1. Wallet Discovery

```python
import requests

def discover_top_wallets(min_volume=10000, min_win_rate=0.55):
    """Find profitable wallets from Polymarket leaderboard."""
    # Polymarket exposes leaderboard data
    resp = requests.get(
        "https://data-api.polymarket.com/leaderboard",
        params={"limit": 100, "window": "all"},
        timeout=15
    )
    leaderboard = resp.json()

    qualified = []
    for entry in leaderboard:
        volume = float(entry.get('volume', 0))
        win_rate = float(entry.get('win_rate', 0))
        address = entry.get('address', '')

        if volume >= min_volume and win_rate >= min_win_rate:
            qualified.append({
                'address': address,
                'volume': volume,
                'win_rate': win_rate,
                'profit': float(entry.get('profit', 0)),
                'num_trades': int(entry.get('num_trades', 0)),
            })

    return sorted(qualified, key=lambda x: x['profit'], reverse=True)


def discover_from_market(condition_id, side="winner"):
    """Find wallets that were on the winning side of a resolved market."""
    # Query Polymarket subgraph for positions
    query = """
    {
      positions(
        where: {
          market: "%s",
          outcome: "%s"
        },
        orderBy: value,
        orderDirection: desc,
        first: 50
      ) {
        user { id }
        value
        outcome
      }
    }
    """ % (condition_id, side)

    resp = requests.post(
        "https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic",
        json={"query": query},
        timeout=15
    )
    data = resp.json()

    wallets = []
    for pos in data.get('data', {}).get('positions', []):
        wallets.append({
            'address': pos['user']['id'],
            'position_value': float(pos['value']),
        })
    return wallets
```

### 2. Wallet Scoring System

```python
import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class WalletProfile:
    address: str
    win_rate: float = 0.0
    total_trades: int = 0
    total_profit: float = 0.0
    avg_position_size: float = 0.0
    avg_entry_timing: float = 0.0  # hours before settlement
    first_seen: float = 0.0
    last_active: float = 0.0
    categories: Dict[str, int] = field(default_factory=dict)  # crypto, weather, politics, etc.


class WalletScorer:
    """Multi-dimensional wallet quality scoring."""

    WEIGHTS = {
        'reputation': 0.35,
        'timing': 0.30,
        'size': 0.20,
        'efficiency': 0.15,
    }

    def score(self, profile: WalletProfile) -> dict:
        """Calculate composite score for a wallet."""
        scores = {}

        # Reputation: win rate + consistency + track record
        scores['reputation'] = self._score_reputation(profile)

        # Timing: how early they enter (earlier = more informational)
        scores['timing'] = self._score_timing(profile)

        # Size: meaningful positions (not dust)
        scores['size'] = self._score_size(profile)

        # Efficiency: profit per trade
        scores['efficiency'] = self._score_efficiency(profile)

        # Composite
        composite = sum(
            scores[dim] * self.WEIGHTS[dim]
            for dim in self.WEIGHTS
        )

        return {
            'address': profile.address,
            'composite_score': round(composite, 3),
            'dimension_scores': {k: round(v, 3) for k, v in scores.items()},
            'tier': self._tier(composite),
        }

    def _score_reputation(self, p: WalletProfile) -> float:
        """0-1 score based on win rate and consistency."""
        if p.total_trades < 10:
            return 0.1  # not enough data

        # Win rate component (0.55 = baseline, 0.75+ = excellent)
        wr_score = min((p.win_rate - 0.5) / 0.3, 1.0)
        wr_score = max(wr_score, 0)

        # Track record length (more trades = more reliable)
        volume_score = min(p.total_trades / 100, 1.0)

        # Recency decay
        days_inactive = (time.time() - p.last_active) / 86400
        recency = max(1 - days_inactive / 30, 0.1)

        return wr_score * 0.5 + volume_score * 0.3 + recency * 0.2

    def _score_timing(self, p: WalletProfile) -> float:
        """Earlier entries before settlement = better information."""
        if p.avg_entry_timing <= 0:
            return 0.5

        # 24+ hours early = excellent timing
        # 1 hour early = still decent
        # < 10 minutes = possibly reacting to public info
        if p.avg_entry_timing >= 24:
            return 1.0
        elif p.avg_entry_timing >= 6:
            return 0.8
        elif p.avg_entry_timing >= 1:
            return 0.5
        else:
            return 0.2

    def _score_size(self, p: WalletProfile) -> float:
        """Meaningful position sizes indicate conviction."""
        if p.avg_position_size <= 0:
            return 0.1

        # $100+ avg = serious trader
        # $10-100 = moderate
        # <$10 = possibly noise
        if p.avg_position_size >= 1000:
            return 1.0
        elif p.avg_position_size >= 100:
            return 0.7
        elif p.avg_position_size >= 10:
            return 0.4
        else:
            return 0.1

    def _score_efficiency(self, p: WalletProfile) -> float:
        """Profit per trade efficiency."""
        if p.total_trades == 0:
            return 0

        profit_per_trade = p.total_profit / p.total_trades
        if profit_per_trade >= 50:
            return 1.0
        elif profit_per_trade >= 10:
            return 0.7
        elif profit_per_trade >= 1:
            return 0.4
        elif profit_per_trade >= 0:
            return 0.2
        else:
            return 0.0

    def _tier(self, score: float) -> str:
        if score >= 0.8:
            return "S"
        elif score >= 0.6:
            return "A"
        elif score >= 0.4:
            return "B"
        elif score >= 0.2:
            return "C"
        else:
            return "D"
```

### 3. Insider Trading Detection

The most valuable feature — detecting suspicious pre-settlement activity:

```python
from datetime import datetime, timezone, timedelta


class InsiderDetector:
    """Detect suspicious trading patterns before market settlement."""

    # Thresholds
    WHALE_THRESHOLD_USD = 1000      # large single trade
    TIMING_WINDOW_HOURS = 24        # how close to settlement counts
    CLUSTER_THRESHOLD = 3           # multiple trades in short window
    CLUSTER_WINDOW_MINUTES = 30     # time window for clustering

    def __init__(self):
        self.alerts = []
        self.alert_history = {}  # address -> list of alerts

    def check_trade(self, trade, market_end_time):
        """
        Evaluate a single trade for insider signals.

        trade: {address, side, size_usd, timestamp, market_id}
        market_end_time: datetime when market resolves
        """
        alerts = []
        now = datetime.fromtimestamp(trade['timestamp'], tz=timezone.utc)
        hours_to_settlement = (market_end_time - now).total_seconds() / 3600

        # 1. Large pre-settlement trade
        if (trade['size_usd'] >= self.WHALE_THRESHOLD_USD and
            hours_to_settlement <= self.TIMING_WINDOW_HOURS):
            alerts.append({
                'type': 'WHALE_PRE_SETTLEMENT',
                'severity': 'HIGH',
                'address': trade['address'],
                'details': (
                    f"${trade['size_usd']:,.0f} trade, "
                    f"{hours_to_settlement:.1f}h before settlement"
                ),
                'timestamp': trade['timestamp'],
                'market_id': trade['market_id'],
            })

        # 2. Cluster detection (same address, multiple trades, short window)
        recent = self._get_recent_trades(
            trade['address'],
            trade['market_id'],
            trade['timestamp'],
            window_minutes=self.CLUSTER_WINDOW_MINUTES
        )
        if len(recent) >= self.CLUSTER_THRESHOLD:
            total_size = sum(t['size_usd'] for t in recent)
            alerts.append({
                'type': 'TRADE_CLUSTER',
                'severity': 'MEDIUM',
                'address': trade['address'],
                'details': (
                    f"{len(recent)} trades in {self.CLUSTER_WINDOW_MINUTES}min, "
                    f"total ${total_size:,.0f}"
                ),
                'timestamp': trade['timestamp'],
                'market_id': trade['market_id'],
            })

        # 3. New wallet, large trade (freshly funded → suspicious)
        if (trade.get('is_new_wallet', False) and
            trade['size_usd'] >= self.WHALE_THRESHOLD_USD * 0.5):
            alerts.append({
                'type': 'NEW_WALLET_LARGE_TRADE',
                'severity': 'HIGH',
                'address': trade['address'],
                'details': (
                    f"New wallet with ${trade['size_usd']:,.0f} trade"
                ),
                'timestamp': trade['timestamp'],
                'market_id': trade['market_id'],
            })

        for alert in alerts:
            self.alerts.append(alert)
            self.alert_history.setdefault(trade['address'], []).append(alert)

        return alerts

    def _get_recent_trades(self, address, market_id, current_ts, window_minutes):
        """Get trades from same address in recent window."""
        cutoff = current_ts - (window_minutes * 60)
        return [
            a for a in self.alert_history.get(address, [])
            if a['timestamp'] >= cutoff and a['market_id'] == market_id
        ]

    def get_summary(self):
        """Get alert statistics."""
        by_type = {}
        by_severity = {}
        for alert in self.alerts:
            by_type[alert['type']] = by_type.get(alert['type'], 0) + 1
            by_severity[alert['severity']] = by_severity.get(alert['severity'], 0) + 1

        return {
            'total_alerts': len(self.alerts),
            'by_type': by_type,
            'by_severity': by_severity,
            'unique_addresses': len(self.alert_history),
        }
```

### 4. Signal Export for Cross-Bot Integration

Export tracked wallet signals for other bots to consume:

```python
import json
import os

class SignalExporter:
    """Export wallet signals as JSON feed for other bots."""

    def __init__(self, output_path='wallet_signal_feed.json'):
        self.output_path = output_path
        self.signals = []

    def add_signal(self, wallet_score, trade_info, alert=None):
        """Add a signal from a tracked wallet's activity."""
        signal = {
            'timestamp': time.time(),
            'source': 'smart_money_tracker',
            'wallet': {
                'address': wallet_score['address'],
                'tier': wallet_score['tier'],
                'composite_score': wallet_score['composite_score'],
            },
            'trade': {
                'market_id': trade_info.get('market_id', ''),
                'side': trade_info.get('side', ''),
                'size_usd': trade_info.get('size_usd', 0),
            },
            'alert_type': alert['type'] if alert else None,
            'alert_severity': alert['severity'] if alert else None,
            'signal_strength': self._compute_strength(wallet_score, alert),
        }
        self.signals.append(signal)

    def _compute_strength(self, wallet_score, alert):
        """0-1 signal strength based on wallet quality and alert type."""
        base = wallet_score['composite_score']

        if alert:
            severity_boost = {
                'HIGH': 0.3,
                'MEDIUM': 0.15,
                'LOW': 0.05,
            }
            base += severity_boost.get(alert['severity'], 0)

        return min(base, 1.0)

    def export(self):
        """Write current signals to JSON file."""
        # Keep only last 1000 signals
        recent = self.signals[-1000:]

        output = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_signals': len(recent),
            'signals': recent,
        }

        with open(self.output_path, 'w') as f:
            json.dump(output, f, indent=2)

        return len(recent)
```

## Deployment

### Running the Tracker

```python
class SmartMoneyTracker:
    """Main tracker orchestrator."""

    def __init__(self):
        self.scorer = WalletScorer()
        self.detector = InsiderDetector()
        self.exporter = SignalExporter()
        self.tracked_wallets = {}  # address -> WalletProfile
        self.scan_interval = 300   # 5 minutes

    def run(self):
        """Main monitoring loop."""
        # Initial wallet discovery
        self.discover_wallets()

        while True:
            try:
                for address, profile in self.tracked_wallets.items():
                    new_trades = self.fetch_new_trades(address)
                    for trade in new_trades:
                        # Score the wallet
                        score = self.scorer.score(profile)

                        # Check for insider signals
                        alerts = self.detector.check_trade(
                            trade,
                            trade.get('market_end_time', datetime.max)
                        )

                        # Export signals
                        for alert in alerts:
                            self.exporter.add_signal(score, trade, alert)

                self.exporter.export()
                self.cleanup_inactive_wallets()
                time.sleep(self.scan_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"Tracker error: {e}")
                time.sleep(30)
```

### systemd Service

```ini
[Unit]
Description=Polymarket Smart Money Tracker
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/polymarket-bot
ExecStart=/usr/bin/python3 /root/polymarket-bot/wallet_tracker.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

## Data Output

The tracker generates these files:

| File | Contents | Update Frequency |
|------|----------|-----------------|
| `wallet_signals.csv` | All detected wallet activities | Every scan cycle |
| `insider_alerts.csv` | Flagged suspicious trades | Real-time |
| `smart_money_scores.csv` | Current wallet rankings | Hourly |
| `wallet_signal_feed.json` | Machine-readable signal feed | Every scan cycle |

## Three Types of Prediction Market Traders

Understanding who you're tracking helps prioritize signals:

**Directional Traders** — Buy conviction positions and hold to settlement. Sports/politics heavy. Top performer: single address with $10M+ profit on correct directional calls. Signal: large early positions in binary outcomes.

**Structural Traders** — Act as market makers, profit from spread. 3 of the top 5 crypto market wallets are automated market makers. Signal: symmetric positions, high trade frequency, tight spreads.

**Cognitive Traders** — Few trades per month, each backed by deep research. Low frequency but high conviction. Signal: sudden large position from previously quiet wallet.

## Reference Files

- `references/subgraph-queries.md` — Useful Graph Protocol queries for Polymarket data
- `scripts/wallet_scanner.py` — Standalone wallet discovery and scoring tool
- `scripts/alert_dashboard.py` — Simple terminal dashboard for insider alerts
