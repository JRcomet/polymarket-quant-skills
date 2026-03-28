# Polymarket Quantitative Trading Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Skill](https://img.shields.io/badge/Claude-Skill-purple)](https://skillsmp.com)
[![Polymarket](https://img.shields.io/badge/Polymarket-CLOB-green)](https://polymarket.com)

Battle-tested AI agent skills for building automated trading systems on Polymarket prediction markets.

Built from a real production system: **7,674 lines of Python**, **211K+ on-chain signals analyzed**, **3,433 insider alerts generated**, running 24/7 on a Tokyo VPS.

## Skills

### `polymarket-quant-trading`

Build production-ready Polymarket trading bots with quantitative strategies including Kelly criterion position sizing, Bayesian probability updating, real-time Binance WebSocket feeds, and liquidity filtering.

**What's inside:**

- Complete bot template with all quantitative components
- Kelly criterion + Bayesian rolling update implementation
- Liquidity filter — the #1 lesson from live testing
- Signal fusion for multi-source strategies
- Polymarket API reference (CLOB, Gamma, Data APIs)
- VPS deployment guide with systemd
- Backtesting framework
- Market liquidity scanner

### `polymarket-smart-money`

Track profitable wallets, detect insider trading, and generate smart money signals on Polymarket.

**What's inside:**

- Wallet discovery from leaderboard + on-chain data
- Multi-dimensional scoring system (reputation 35%, timing 30%, size 20%, efficiency 15%)
- Insider trading detection (whale pre-settlement, trade clustering, new wallet alerts)
- Cross-bot signal export (JSON feed for other trading bots)
- Graph Protocol subgraph query reference
- Terminal alert dashboard
- Wallet scanner tool

## Architecture

```
┌─────────────────── quant-trading ───────────────────┐
│                                                      │
│  Signal Layer    →  Decision Layer  →  Execution     │
│  (Binance WS,      (Bayesian,         (CLOB API,    │
│   Weather API,       Kelly,             Limit/Market  │
│   On-chain)          Liquidity)         Orders)       │
│                                                      │
└──────────────────────────────────────────────────────┘

┌─────────────────── smart-money ─────────────────────┐
│                                                      │
│  Discovery     →  Scoring    →  Monitoring → Alert   │
│  (Leaderboard,    (4-dim        (Subgraph     (Whale,│
│   On-chain)        composite)    polling)      Insider│
│                                               Cluster│
└──────────────────────────────────────────────────────┘
```

## Installation

### Claude Code / Cowork

Copy the skill folder to your Claude skills directory:

```bash
cp -r polymarket-quant-trading ~/.claude/skills/
cp -r polymarket-smart-money ~/.claude/skills/
```

### From `.skill` file

```bash
claude skill install polymarket-quant-trading.skill
claude skill install polymarket-smart-money.skill
```

### From GitHub

```bash
git clone https://github.com/JRcomet/polymarket-quant-skills.git
cp -r polymarket-quant-skills/polymarket-quant-trading ~/.claude/skills/
cp -r polymarket-quant-skills/polymarket-smart-money ~/.claude/skills/
```

## Key Insights from Production

These are hard-won lessons from running bots on real Polymarket markets:

1. **Liquidity filtering is essential** — 70% of simulated profits occur in markets too thin to actually trade. A $50 depth filter cuts trades by 60% but makes every remaining trade executable.

2. **Fractional Kelly (25%)** — Full Kelly maximizes growth but with extreme variance. Quarter-Kelly sacrifices ~6% growth for ~75% less drawdown.

3. **Bayesian > snapshots** — Rolling probability updates over 30-second windows are far more robust than single-point price checks.

4. **Know your game** — Directional, structural, and cognitive strategies require completely different approaches. Don't mix them.

5. **DRY RUN first, always** — Every strategy runs in simulation mode before touching real capital. No exceptions.

## Strategy Tracks

| Track | Edge Source | Competition | Best For |
|-------|-----------|-------------|----------|
| Crypto Price | Binance real-time vs Polymarket lag | High (latency war) | Structural bots |
| Weather | Multi-API ensemble vs market mispricing | Low | Cognitive/automated |
| Smart Money | Whale tracking + insider detection | Medium | Signal-driven |

## Project Structure

```
polymarket-quant-skills/
├── README.md
├── LICENSE
├── polymarket-quant-trading/
│   ├── SKILL.md                    # Main skill instructions
│   ├── references/
│   │   ├── api-reference.md        # Polymarket API docs
│   │   └── bot-template.md         # Complete bot code template
│   └── scripts/
│       ├── liquidity_checker.py    # Market liquidity scanner
│       └── backtest.py             # Backtesting framework
├── polymarket-smart-money/
│   ├── SKILL.md                    # Main skill instructions
│   ├── references/
│   │   └── subgraph-queries.md     # Graph Protocol queries
│   └── scripts/
│       ├── wallet_scanner.py       # Wallet discovery tool
│       └── alert_dashboard.py      # Terminal alert dashboard
├── polymarket-quant-trading.skill  # Packaged skill file
└── polymarket-smart-money.skill    # Packaged skill file
```

## Requirements

- Python 3.8+
- `py-clob-client` — Polymarket CLOB API client
- `python-dotenv` — Environment variable management
- `requests` — HTTP requests
- `websocket-client` — Real-time price feeds

## Disclaimer

These skills are educational tools for building prediction market trading systems. Trading on Polymarket involves real financial risk. Always start with DRY RUN mode, use fractional Kelly sizing, and never risk more than you can afford to lose. The author is not responsible for any trading losses.

## Author

Built by a solo developer + Claude AI. No team, no funding, just one VPS.

## License

[MIT](LICENSE)
