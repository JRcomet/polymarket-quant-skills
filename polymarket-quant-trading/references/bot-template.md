# Polymarket Bot — Complete Template

This is a production-ready bot template with all quantitative components integrated. Copy, customize, and deploy.

## Table of Contents
1. [Configuration](#configuration)
2. [Core Classes](#core-classes)
3. [Main Loop](#main-loop)
4. [WebSocket Feed](#websocket-feed)
5. [CSV Logging](#csv-logging)
6. [Customization Guide](#customization-guide)

## Configuration

```python
import os
import time
import json
import csv
import math
import threading
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ─── Trading Parameters ───
DRY_RUN = True                    # ALWAYS start True
SCAN_SLEEP = 0.5                  # seconds between scans
MIN_EDGE = 0.08                   # minimum edge to trade (8%)
ENTRY_BEFORE_CLOSE = 30           # seconds before close to enter

# ─── Kelly Criterion ───
KELLY_FRACTION = 0.25             # fraction of full Kelly
KELLY_MIN_BET = 0.50              # minimum bet in USD
KELLY_MAX_BET = 20.0              # maximum bet in USD
BANKROLL = 100.0                  # starting bankroll

# ─── Bayesian Tracker ───
BAYESIAN_WINDOW = 30              # seconds of observation
BAYESIAN_UPDATE_INTERVAL = 0.5    # seconds between updates
SIGMOID_WEIGHT = 0.4              # weight for sigmoid signal
BAYESIAN_WEIGHT = 0.6             # weight for Bayesian signal

# ─── Liquidity Filter ───
MIN_LIQUIDITY_USD = 50.0
MAX_SPREAD = 0.15
MIN_MARKET_PRICE = 0.05
MAX_MARKET_PRICE = 0.95

# ─── API Keys (from environment) ───
POLYMARKET_KEY = os.environ.get("POLYMARKET_API_KEY", "")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")

# ─── Logging ───
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)
```

## Core Classes

### BayesianTracker

```python
class BayesianTracker:
    """Accumulates price evidence over rolling windows."""

    def __init__(self):
        self.prior = 0.5
        self.observations = []
        self.window = BAYESIAN_WINDOW

    def update(self, price_move_pct, timestamp):
        if price_move_pct > 0:
            likelihood = 0.5 + min(price_move_pct / 2, 0.4)
        else:
            likelihood = 0.5 + max(price_move_pct / 2, -0.4)

        posterior = (likelihood * self.prior) / (
            likelihood * self.prior + (1 - likelihood) * (1 - self.prior)
        )
        self.prior = posterior
        self.observations.append({
            'ts': timestamp, 'move': price_move_pct, 'post': posterior
        })
        self._trim(timestamp)
        return posterior

    def _trim(self, now):
        cutoff = now - self.window
        self.observations = [o for o in self.observations if o['ts'] >= cutoff]

    def reset(self):
        self.prior = 0.5
        self.observations.clear()

    @property
    def confidence(self):
        return abs(self.prior - 0.5) * 2
```

### KellyCalculator

```python
class KellyCalculator:
    """Optimal position sizing via fractional Kelly criterion."""

    def __init__(self, bankroll=BANKROLL):
        self.bankroll = bankroll

    def calculate(self, edge, market_price):
        """
        edge: our estimated probability - market price
        market_price: current best ask or bid
        Returns: bet size in USD
        """
        if edge <= 0:
            return 0

        # Convert to Kelly formula inputs
        if market_price <= 0 or market_price >= 1:
            return 0

        b = (1 / market_price) - 1  # net odds
        p = market_price + edge       # our true probability
        q = 1 - p

        f_star = (b * p - q) / b
        if f_star <= 0:
            return 0

        raw = f_star * self.bankroll * KELLY_FRACTION
        return max(KELLY_MIN_BET, min(raw, KELLY_MAX_BET))

    def update_bankroll(self, pnl):
        self.bankroll += pnl
        log.info(f"Bankroll updated: ${self.bankroll:.2f}")
```

### LiquidityFilter

```python
class LiquidityFilter:
    """Reject markets that can't realistically fill orders."""

    @staticmethod
    def check(orderbook):
        """Returns (passes: bool, reason: str)"""
        if not orderbook or not orderbook.get('bids') or not orderbook.get('asks'):
            return False, "Empty orderbook"

        best_bid = float(orderbook['bids'][0]['price']) if orderbook['bids'] else 0
        best_ask = float(orderbook['asks'][0]['price']) if orderbook['asks'] else 1

        spread = best_ask - best_bid
        if spread > MAX_SPREAD:
            return False, f"Spread {spread:.3f} > {MAX_SPREAD}"

        if best_bid < MIN_MARKET_PRICE:
            return False, f"Bid {best_bid:.3f} too low"
        if best_ask > MAX_MARKET_PRICE:
            return False, f"Ask {best_ask:.3f} too high"

        # Sum depth at best prices
        bid_depth = sum(float(b['size']) * float(b['price'])
                       for b in orderbook['bids'][:3])
        ask_depth = sum(float(a['size']) * float(a['price'])
                       for a in orderbook['asks'][:3])
        total_depth = bid_depth + ask_depth

        if total_depth < MIN_LIQUIDITY_USD:
            return False, f"Depth ${total_depth:.0f} < ${MIN_LIQUIDITY_USD:.0f}"

        return True, f"OK (spread={spread:.3f}, depth=${total_depth:.0f})"
```

## Main Loop

```python
class TradingBot:
    """Main bot orchestrator."""

    def __init__(self):
        self.bayesian = BayesianTracker()
        self.kelly = KellyCalculator()
        self.liquidity = LiquidityFilter()
        self.trades_today = 0
        self.daily_limit = 50

        # Initialize Polymarket client
        if not DRY_RUN:
            from py_clob_client.client import ClobClient
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=POLYMARKET_KEY,
                chain_id=137,
                signature_type=2,
                funder=os.environ.get("POLYMARKET_FUNDER_ADDRESS", "")
            )
            self.client.set_api_creds(
                self.client.create_or_derive_api_creds()
            )

    def scan_markets(self):
        """Find active markets approaching close."""
        try:
            resp = requests.get(
                "https://gamma-api.polymarket.com/events",
                params={"active": True, "closed": False},
                timeout=10
            )
            events = resp.json()
            candidates = []
            now = time.time()

            for event in events:
                for market in event.get('markets', []):
                    end_str = market.get('end_date_iso', '')
                    if not end_str:
                        continue
                    # Parse end time and check if within entry window
                    # (customize based on your strategy's time horizon)
                    candidates.append(market)

            return candidates
        except Exception as e:
            log.error(f"Market scan failed: {e}")
            return []

    def evaluate_market(self, market, external_signal):
        """Run full evaluation pipeline on a market."""
        token_id = market.get('clobTokenIds', [''])[0]
        if not token_id:
            return None

        # 1. Get orderbook
        try:
            orderbook = requests.get(
                f"https://clob.polymarket.com/book",
                params={"token_id": token_id},
                timeout=5
            ).json()
        except:
            return None

        # 2. Liquidity check
        passes, reason = self.liquidity.check(orderbook)
        if not passes:
            log.debug(f"Filtered: {reason}")
            return None

        # 3. Compute signal
        market_price = float(orderbook['asks'][0]['price']) if orderbook.get('asks') else 0.5

        # Bayesian update with external signal
        bayesian_prob = self.bayesian.update(external_signal, time.time())

        # Sigmoid mapping (customize for your signal type)
        sigmoid_prob = 1 / (1 + math.exp(-external_signal * 5))

        # Signal fusion
        fused_prob, alignment = self._fuse(sigmoid_prob, bayesian_prob)

        if alignment == "CONFLICT":
            log.debug("Signal conflict — skipping")
            return None

        # 4. Calculate edge and position size
        edge = fused_prob - market_price
        if abs(edge) < MIN_EDGE:
            return None

        side = "YES" if edge > 0 else "NO"
        bet_size = self.kelly.calculate(abs(edge), market_price)

        if bet_size <= 0:
            return None

        return {
            'market': market,
            'token_id': token_id,
            'side': side,
            'edge': edge,
            'fused_prob': fused_prob,
            'market_price': market_price,
            'bet_size': bet_size,
            'alignment': alignment
        }

    def _fuse(self, sigmoid_prob, bayesian_prob):
        sig_dir = "UP" if sigmoid_prob > 0.5 else "DOWN"
        bay_dir = "UP" if bayesian_prob > 0.5 else "DOWN"

        if sig_dir != bay_dir:
            return 0.5, "CONFLICT"

        fused = sigmoid_prob * SIGMOID_WEIGHT + bayesian_prob * BAYESIAN_WEIGHT
        return fused, "ALIGNED"

    def execute_trade(self, signal):
        """Place order or log DRY RUN trade."""
        if self.trades_today >= self.daily_limit:
            log.warning("Daily trade limit reached")
            return

        if DRY_RUN:
            log.info(f"[DRY RUN] {signal['side']} ${signal['bet_size']:.2f} "
                     f"@ {signal['market_price']:.3f} "
                     f"(edge={signal['edge']:.3f})")
            self._log_trade(signal, dry_run=True)
        else:
            try:
                # Place limit order
                from py_clob_client.order_builder.constants import BUY, SELL
                order = self.client.create_and_post_order({
                    "tokenID": signal['token_id'],
                    "price": signal['market_price'],
                    "size": signal['bet_size'],
                    "side": BUY if signal['side'] == "YES" else SELL,
                })
                log.info(f"Order placed: {order}")
                self._log_trade(signal, dry_run=False, order_id=order.get('orderID'))
            except Exception as e:
                log.error(f"Order failed: {e}")

        self.trades_today += 1

    def _log_trade(self, signal, dry_run=True, order_id=None):
        """Append trade to CSV log."""
        filepath = os.path.join(LOG_DIR, 'trades_log.csv')
        file_exists = os.path.exists(filepath)

        with open(filepath, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    'timestamp', 'market_id', 'side', 'edge',
                    'bet_size', 'market_price', 'fused_prob',
                    'dry_run', 'order_id'
                ])
            writer.writerow([
                datetime.now(timezone.utc).isoformat(),
                signal['market'].get('conditionId', ''),
                signal['side'],
                f"{signal['edge']:.4f}",
                f"{signal['bet_size']:.2f}",
                f"{signal['market_price']:.3f}",
                f"{signal['fused_prob']:.4f}",
                dry_run,
                order_id or ''
            ])

    def run(self):
        """Main loop."""
        log.info(f"Bot starting ({'DRY RUN' if DRY_RUN else 'LIVE'})")
        log.info(f"Kelly: {KELLY_FRACTION*100}% fraction, "
                 f"${KELLY_MIN_BET}-${KELLY_MAX_BET} range")

        while True:
            try:
                markets = self.scan_markets()
                for market in markets:
                    # Get your external signal here
                    # (Binance price, weather data, etc.)
                    external_signal = self._get_external_signal(market)

                    result = self.evaluate_market(market, external_signal)
                    if result:
                        self.execute_trade(result)

                time.sleep(SCAN_SLEEP)

            except KeyboardInterrupt:
                log.info("Shutting down...")
                break
            except Exception as e:
                log.error(f"Loop error: {e}")
                time.sleep(5)

    def _get_external_signal(self, market):
        """Override this method for your specific signal source."""
        # Example: return price change percentage from Binance
        return 0.0


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
```

## WebSocket Feed

For real-time price data from Binance:

```python
import websocket
import json
import threading

class BinanceFeed:
    """Real-time crypto price feed via WebSocket."""

    WS_URL = "wss://stream.binance.com:9443/ws"

    def __init__(self, symbols=None):
        self.symbols = symbols or ['btcusdt', 'ethusdt']
        self.prices = {}
        self.running = False
        self._thread = None

    def start(self):
        streams = '/'.join(f"{s}@ticker" for s in self.symbols)
        url = f"{self.WS_URL}/{streams}"

        def on_message(ws, message):
            data = json.loads(message)
            symbol = data.get('s', '').lower()
            price = float(data.get('c', 0))
            change_pct = float(data.get('P', 0))
            self.prices[symbol] = {
                'price': price,
                'change_pct': change_pct,
                'timestamp': time.time()
            }

        def on_error(ws, error):
            log.error(f"WebSocket error: {error}")

        def on_close(ws, code, msg):
            log.warning(f"WebSocket closed: {code}")
            if self.running:
                time.sleep(5)
                self.start()  # auto-reconnect

        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        self.running = True
        self._thread = threading.Thread(target=ws.run_forever, daemon=True)
        self._thread.start()
        log.info(f"Binance WebSocket connected: {self.symbols}")

    def get_price(self, symbol):
        return self.prices.get(symbol, {})

    def stop(self):
        self.running = False
```

## CSV Logging

The bot generates three CSV files for analysis:

| File | Purpose | Key Columns |
|------|---------|-------------|
| `trades_log.csv` | All executed/simulated trades | timestamp, side, edge, bet_size, pnl |
| `signals.csv` | All signals generated (including skipped) | timestamp, signal_type, value, action_taken |
| `calibration.csv` | Predicted vs actual outcomes | predicted_prob, actual_outcome, was_correct |

## Customization Guide

### Adding a New Signal Source

1. Create a new class that provides `get_signal(market) -> float`
2. Wire it into `_get_external_signal()` in the main bot
3. Optionally add a BayesianTracker for the new source
4. Update signal fusion weights

### Adjusting Risk Parameters

| Parameter | Conservative | Moderate | Aggressive |
|-----------|-------------|----------|------------|
| KELLY_FRACTION | 0.10 | 0.25 | 0.50 |
| MIN_EDGE | 0.12 | 0.08 | 0.05 |
| MAX_BET | $5 | $20 | $50 |
| MIN_LIQUIDITY | $100 | $50 | $20 |

### Multi-Bot Setup

Run multiple bots as separate systemd services, each targeting a different market category:
```bash
# crypto-bot.service → crypto price markets
# weather-bot.service → weather prediction markets
# event-bot.service → news/event markets
```

Share signals between bots via a JSON feed file that each bot writes and others can read.
