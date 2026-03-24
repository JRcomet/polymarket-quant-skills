# Polymarket Subgraph Queries

Useful Graph Protocol queries for extracting on-chain data from Polymarket.

## Subgraph Endpoints

| Network | URL |
|---------|-----|
| Polygon (main) | `https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic` |

## Common Queries

### Get Top Positions in a Market

```graphql
{
  positions(
    where: { market: "CONDITION_ID_HERE" }
    orderBy: value
    orderDirection: desc
    first: 50
  ) {
    user { id }
    value
    outcome
    market { id, question }
  }
}
```

### Get All Trades for a Wallet

```graphql
{
  trades(
    where: { user: "WALLET_ADDRESS" }
    orderBy: timestamp
    orderDirection: desc
    first: 100
  ) {
    id
    market { id, question }
    outcome
    amount
    price
    timestamp
    type  # BUY or SELL
  }
}
```

### Find Recent Large Trades

```graphql
{
  trades(
    where: { amount_gt: "1000000000" }  # > $1000 (6 decimals)
    orderBy: timestamp
    orderDirection: desc
    first: 50
  ) {
    user { id }
    market { id, question }
    outcome
    amount
    price
    timestamp
  }
}
```

### Get Market Positions Summary

```graphql
{
  market(id: "CONDITION_ID") {
    id
    question
    outcomes
    totalVolume
    totalLiquidity
    positions(first: 100, orderBy: value, orderDirection: desc) {
      user { id }
      value
      outcome
    }
  }
}
```

### Active Wallets in Last 24 Hours

```graphql
{
  trades(
    where: { timestamp_gt: UNIX_TIMESTAMP_24H_AGO }
    orderBy: amount
    orderDirection: desc
    first: 200
  ) {
    user { id }
    amount
    market { id }
    timestamp
  }
}
```

## Python Helper

```python
import requests

SUBGRAPH_URL = "https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic"

def query_subgraph(query, variables=None):
    """Execute a subgraph query."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = requests.post(SUBGRAPH_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise Exception(f"Subgraph error: {data['errors']}")

    return data.get("data", {})
```

## Rate Limits

- The Graph hosted service: ~5 requests/second
- Complex queries with many results may timeout — use pagination
- For high-frequency monitoring, cache results and use incremental queries
