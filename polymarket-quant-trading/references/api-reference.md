# Polymarket API Reference

Quick reference for the APIs used in trading bot development.

## CLOB API (Order Management)

**Base URL**: `https://clob.polymarket.com`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/book` | Get orderbook for a token |
| GET | `/price` | Get current mid-price |
| GET | `/midpoint` | Get midpoint price |
| POST | `/order` | Place a new order |
| DELETE | `/order/{id}` | Cancel an order |
| GET | `/orders` | List your open orders |
| GET | `/trades` | List your trade history |

### Get Orderbook
```
GET /book?token_id={token_id}

Response:
{
  "market": "0x...",
  "asset_id": "token_id",
  "bids": [{"price": "0.45", "size": "100"}],
  "asks": [{"price": "0.55", "size": "50"}]
}
```

### Place Order (via py_clob_client)
```python
from py_clob_client.client import ClobClient
from py_clob_client.order_builder.constants import BUY

order = client.create_and_post_order({
    "tokenID": "token_id_here",
    "price": 0.45,
    "size": 10.0,
    "side": BUY,
})
```

## Gamma API (Market Discovery)

**Base URL**: `https://gamma-api.polymarket.com`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/events` | List events with markets |
| GET | `/markets` | List individual markets |
| GET | `/markets/{id}` | Get market details |

### List Active Events
```
GET /events?active=true&closed=false

Response: [
  {
    "id": "event_id",
    "title": "Will BTC reach $100K?",
    "markets": [
      {
        "id": "market_id",
        "question": "Will BTC reach $100K by Dec 31?",
        "clobTokenIds": ["yes_token", "no_token"],
        "outcomePrices": "[0.65, 0.35]",
        "volume": "125000",
        "end_date_iso": "2025-12-31T00:00:00Z"
      }
    ]
  }
]
```

### Useful Filters

| Parameter | Type | Description |
|-----------|------|-------------|
| `active` | bool | Only active events |
| `closed` | bool | Exclude closed events |
| `tag_slug` | string | Filter by category (crypto, politics, sports, weather) |
| `limit` | int | Max results (default 100) |
| `offset` | int | Pagination offset |

## Data API (Historical Data)

**Base URL**: `https://data-api.polymarket.com`

### Price History
```
GET /prices-history?market={condition_id}&interval=max&fidelity=1

Response: {
  "history": [
    {"t": 1700000000, "p": 0.45},
    {"t": 1700003600, "p": 0.48}
  ]
}
```

## Rate Limits

- CLOB API: ~10 requests/second per IP
- Gamma API: ~5 requests/second per IP
- Order placement: 50 orders/day (may vary)
- WebSocket connections: use Binance streams, not Polymarket

## Error Handling

```python
import time

def safe_api_call(func, *args, max_retries=3, **kwargs):
    """Retry with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # rate limited
                wait = 2 ** attempt
                log.warning(f"Rate limited, waiting {wait}s")
                time.sleep(wait)
            else:
                raise
        except requests.exceptions.ConnectionError:
            time.sleep(2 ** attempt)
    raise Exception(f"Failed after {max_retries} retries")
```
