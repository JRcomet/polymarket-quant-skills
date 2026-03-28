---
name: polymarket-quant-trading
description: "Build automated Polymarket trading bots with Kelly criterion, Bayesian probability, liquidity filtering, and real-time data feeds. Covers CLOB API integration, signal generation, position sizing, risk management, DRY RUN validation, and VPS deployment. Use when the user mentions Polymarket, prediction markets, event contracts, or quantitative trading strategies."
---

# Polymarket Quantitative Trading Bot Builder

A battle-tested skill for building automated trading bots on Polymarket's prediction market platform. Based on a real system that processed 211,000+ on-chain signals, executed 2,500+ simulated trades, and runs 24/7 on a Tokyo VPS.

## When to Use This Skill

Use this skill when the user wants to:
- Build a Polymarket trading bot from scratch
- Add quantitative strategies (Kelly, Bayesian, etc.) to an existing bot
- Connect external data sources (Binance, weather APIs) to Polymarket
- Implement proper risk management for prediction market trading
- Deploy a trading bot to production (VPS + systemd)
- Analyze Polymarket market data or orderbook dynamics
- Understand prediction market mechanics and edge detection

## Architecture Overview

A complete Polymarket quant system has three layers:

```
Signal Layer → Decision Layer → Execution Layer
(data sources)   (quant models)   (CLOB API)
```

**Signal Layer**: External data feeds that provide information edge
- Crypto prices (Binance WebSocket for real-time BTC/ETH)
- Weather data (Open-Meteo + WeatherAPI ensemble)
- On-chain wallet activity (Polymarket contract events)

**Decision Layer**: Quantitative models that convert signals to trades
- Bayesian probability updating (rolling posterior estimation)
- Kelly criterion (optimal position sizing)
- Liquidity filtering (reject thin markets)
- Signal fusion (weighted multi-source combination)

**Execution Layer**: Trade placement and management
- Polymarket CLOB API (py_clob_client)
- Order type selection (limit vs market)
- Position tracking and P&L logging

## Core Quantitative Components

### 1. Kelly Criterion — Dynamic Position Sizing

The Kelly criterion determines optimal bet size based on edge magnitude:

```
f* = (b * p - q) / b

where:
  f* = fraction of bankroll to bet
  b  = decimal odds - 1 (net payout)
  p  = estimated true probability
  q  = 1 - p
```

**Implementation guidance:**
- Use fractional Kelly (25% of full Kelly) for conservative growth
- Set hard limits: MIN_BET = $0.50, MAX_BET = $10-20
- Scale with bankroll: recalculate after each trade
- Never bet on negative edge (f* <= 0 → skip)

```python
def kelly_bet_size(edge, odds, bankroll, kelly_fraction=0.25):
    """Calculate Kelly-optimal bet size with fractional scaling."""
    b = odds - 1  # net payout ratio
    p = 0.5 + edge  # our estimated probability
    q = 1 - p

    f_star = (b * p - q) / b
    if f_star <= 0:
        return 0  # no edge, no bet

    raw_size = f_star * bankroll * kelly_fraction
    return max(0.50, min(raw_size, 20.0))  # clamp to limits
```

**Why fractional Kelly**: Full Kelly maximizes long-term growth rate but has extreme variance. At 25% Kelly, you sacrifice ~6% of optimal growth but reduce drawdown risk by ~75%. This is the sweet spot for a system running on limited capital.

### 2. Bayesian Rolling Update — Probability Estimation

Instead of relying on a single price snapshot, accumulate evidence over a rolling window:

```python
class BayesianTracker:
    """Track probability estimates using Bayesian updating."""

    def __init__(self, window_seconds=30, update_interval=0.5):
        self.prior = 0.5  # start neutral
        self.observations = []
        self.window = window_seconds
        self.interval = update_interval

    def update(self, price_move_pct, timestamp):
        """Update posterior with new price evidence."""
        # Likelihood ratio based on price movement
        if price_move_pct > 0:
            likelihood_up = 0.5 + min(price_move_pct / 2, 0.4)
        else:
            likelihood_up = 0.5 + max(price_move_pct / 2, -0.4)

        # Bayesian update
        posterior = (likelihood_up * self.prior) / (
            likelihood_up * self.prior +
            (1 - likelihood_up) * (1 - self.prior)
        )

        self.prior = posterior
        self.observations.append({
            'timestamp': timestamp,
            'move': price_move_pct,
            'posterior': posterior
        })

        # Trim old observations
        self._trim_window(timestamp)
        return posterior

    def get_confidence(self):
        """How far from 0.5 (neutral) is our estimate."""
        return abs(self.prior - 0.5) * 2  # 0 = no info, 1 = certain
```

**Key insight**: 5 consecutive bullish signals in a 30-second window push the posterior from 0.50 to ~0.83. A sudden reversal drops it back quickly. This is much more robust than acting on a single price snapshot.

### 3. Liquidity Filter — The Most Important Feature

**This is the #1 lesson from DRY RUN testing.** In simulation, 70% of profitable trades occurred in markets with < $5 of liquidity. These trades look great on paper but are impossible to execute at the quoted price in production.

```python
# Liquidity thresholds (tune based on your capital)
MIN_LIQUIDITY_USD = 50     # minimum market depth
MAX_SPREAD = 0.15          # max bid-ask spread
MIN_MARKET_PRICE = 0.05    # skip penny markets
MAX_MARKET_PRICE = 0.95    # skip near-certain markets

def passes_liquidity_filter(market_data):
    """Reject markets that can't realistically fill orders."""
    best_bid = market_data.get('best_bid', 0)
    best_ask = market_data.get('best_ask', 1)
    spread = best_ask - best_bid

    if spread > MAX_SPREAD:
        return False, f"Spread too wide: {spread:.3f}"

    if best_bid < MIN_MARKET_PRICE or best_ask > MAX_MARKET_PRICE:
        return False, f"Price outside range: {best_bid:.3f}-{best_ask:.3f}"

    # Check depth at best price
    depth = market_data.get('depth_at_best', 0)
    if depth < MIN_LIQUIDITY_USD:
        return False, f"Thin market: ${depth:.0f} depth"

    return True, "OK"
```

**Impact**: Adding this filter cuts trade count by ~60% but dramatically improves real-world performance. Every bot should have this.

### 4. Signal Fusion — Multi-Source Combination

When you have multiple signal sources, combine them with conflict detection:

```python
def fuse_signals(sigmoid_prob, bayesian_prob,
                 sigmoid_weight=0.4, bayesian_weight=0.6):
    """Weighted combination with conflict detection."""
    # Check for signal conflict
    sigmoid_direction = "UP" if sigmoid_prob > 0.5 else "DOWN"
    bayesian_direction = "UP" if bayesian_prob > 0.5 else "DOWN"

    if sigmoid_direction != bayesian_direction:
        # Signals disagree — reduce confidence
        return 0.5, "CONFLICT"

    # Weighted fusion
    fused = sigmoid_prob * sigmoid_weight + bayesian_prob * bayesian_weight
    return fused, "ALIGNED"
```

## Polymarket API Integration

### Required Setup

```bash
pip install py-clob-client python-dotenv requests websocket-client
```

### API Endpoints

| API | Purpose | Base URL |
|-----|---------|----------|
| CLOB API | Order placement & management | `https://clob.polymarket.com` |
| Gamma API | Market discovery & metadata | `https://gamma-api.polymarket.com` |
| Data API | Historical prices & orderbooks | `https://data-api.polymarket.com` |

### Authentication

Polymarket uses API key + secret + passphrase authentication:

```python
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    key=os.environ["POLYMARKET_API_KEY"],
    chain_id=137,  # Polygon
    signature_type=2,
    funder=os.environ["POLYMARKET_FUNDER_ADDRESS"]
)
# Derive API credentials from private key
client.set_api_creds(client.create_or_derive_api_creds())
```

**Security**: NEVER hardcode private keys. Always use environment variables or `.env` files excluded from version control.

### Market Discovery

```python
def find_active_markets(keyword=None, category=None):
    """Find markets that are actively trading."""
    params = {"active": True, "closed": False}
    if keyword:
        params["tag_slug"] = keyword

    resp = requests.get(
        "https://gamma-api.polymarket.com/events",
        params=params
    )
    events = resp.json()

    # Filter for markets with adequate liquidity
    tradeable = []
    for event in events:
        for market in event.get('markets', []):
            if float(market.get('volume', 0)) > 1000:
                tradeable.append(market)
    return tradeable
```

## Bot Architecture Template

Read `references/bot-template.md` for the complete bot template with:
- Main scanning loop with configurable intervals
- WebSocket integration for real-time price feeds
- CSV logging for trades, signals, and calibration data
- systemd service configuration for 24/7 operation
- DRY RUN mode for zero-cost strategy validation

## Strategy Tracks

### Track 1: Crypto Price Prediction (Structural)
- **Edge source**: Binance real-time prices vs Polymarket odds lag
- **Time horizon**: 5-minute windows before market close
- **Key challenge**: Latency — 70% of arbitrage profits go to <100ms bots
- **Realistic expectation**: Positive EV at second-level latency, not HFT profits

### Track 2: Weather Prediction (Cognitive)
- **Edge source**: Multi-source weather APIs vs market mispricing
- **Time horizon**: 0-7 days before event resolution
- **Key challenge**: Data quality and source agreement
- **Advantage**: Low competition, no latency arms race

### Track 3: Event/News Prediction (Directional)
- **Edge source**: Information research and analysis
- **Time horizon**: Days to weeks
- **Key challenge**: Requires deep domain knowledge
- **Approach**: Few high-conviction bets, not high-frequency

## Deployment Guide

### VPS Setup (Recommended: Tokyo/US for low latency to Polygon)

```bash
# 1. SSH into VPS
ssh root@your-vps-ip

# 2. Create project directory
mkdir -p /root/polymarket-bot
cd /root/polymarket-bot

# 3. Install dependencies
pip3 install py-clob-client python-dotenv requests websocket-client

# 4. Set up environment
cat > .env << 'EOF'
POLYMARKET_API_KEY=your_key
POLYMARKET_SECRET=your_secret
POLYMARKET_PASSPHRASE=your_passphrase
PRIVATE_KEY=your_private_key
EOF

# 5. Create systemd service
cat > /etc/systemd/system/polymarket-bot.service << 'EOF'
[Unit]
Description=Polymarket Trading Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/polymarket-bot
ExecStart=/usr/bin/python3 /root/polymarket-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable and start
systemctl daemon-reload
systemctl enable polymarket-bot
systemctl start polymarket-bot

# 7. Check logs
journalctl -u polymarket-bot -f
```

### DRY RUN First

**Always** start with `DRY_RUN = True`. This mode:
- Executes full signal pipeline
- Logs all would-be trades to CSV
- Tracks theoretical P&L
- Costs zero money

Run DRY RUN for at least 48 hours before considering live trading. Check:
1. Are signals generating at expected frequency?
2. What's the theoretical win rate?
3. How many trades pass the liquidity filter?
4. Is the Kelly sizing reasonable?

## Common Pitfalls

1. **Ignoring liquidity** — Simulated profits in thin markets are fake
2. **Over-betting** — Full Kelly = eventual ruin. Use fractional (25%)
3. **Single data source** — Always cross-reference when possible
4. **No DRY RUN** — Going live without validation is gambling, not trading
5. **Hardcoded private keys** — Use env vars, never commit keys to code
6. **Ignoring settlement** — Markets resolve on schedule; factor this into entry timing
7. **Technical indicator cargo cult** — MACD/RSI/VWAP are stock indicators; most don't apply to binary event markets

## Reference Files

- `references/bot-template.md` — Complete bot code template with all components
- `references/api-reference.md` — Polymarket API endpoint documentation
- `scripts/liquidity_checker.py` — Standalone market liquidity scanner
- `scripts/backtest.py` — Simple backtesting framework for strategy validation
