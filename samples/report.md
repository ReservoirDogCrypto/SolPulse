# Solana Ecosystem Report

*Generated 2026-08-22 15:25:33 UTC · SolPulse v1.0.0 (demo)*

**Network health:** `ok` · **Sources responding:** 9/10 · **Anomalies:** 0

## Anomalies

None. Statistical detection needs 5 more run(s) to establish a baseline; absolute rules are already active.

## Network performance

| Metric | Value | Notes |
|---|---|---|
| Transactions per second | 3,349.4 | includes vote transactions |
| Non-vote TPS | 1,205.8 | real user activity |
| Peak TPS (1h) | 3,520.3 |  |
| Average TPS (1h) | 3,248.1 |  |
| Slot time | 412 ms | 400ms target |
| Current slot | 298,459,000 |  |
| Block height | 276,902,411 |  |
| Epoch | 842 | 43.38% complete |
| Epoch ETA | ~27.2 h | at target slot time |

## Validators

| Metric | Value | Notes |
|---|---|---|
| Active | 1,312 |  |
| Delinquent | 41 | 3.03% by count |
| Delinquent stake | 1.42% | 33% would halt finality |
| Nakamoto coefficient | 21 | validators needed to halt finality |
| Top-10 stake share | 17.84% |  |
| Total active stake | 396.14M SOL |  |
| Median commission | 7% |  |
| Zero-commission validators | 214 |  |

### Largest validators

| Identity | Stake (SOL) | Share | Commission |
|---|---:|---:|---:|
| `8XvKi7Wu…` | 12.01M | 3.03% | 0% |
| `RpDc1QoC…` | 10.45M | 2.64% | 5% |
| `i7WuJh6V…` | 9.09M | 2.29% | 8% |
| `1QoCbzPn…` | 7.91M | 2.0% | 10% |
| `Jh6VtHg5…` | 6.88M | 1.74% | 0% |
| `bzPnBayN…` | 5.98M | 1.51% | 7% |
| `tHg5UsGf…` | 5.21M | 1.31% | 10% |
| `BayNmAZx…` | 4.53M | 1.14% | 5% |
| `UsGf4TrF…` | 3.94M | 1.0% | 0% |
| `mAZxMk9Y…` | 3.43M | 0.87% | 10% |

## Economics

| Metric | Value | Notes |
|---|---|---|
| SOL price | $184.32 | DeFiLlama (demo) |
| 24h change | -2.14% |  |
| Market cap | $99.40B |  |
| TVL | $9.24B | rank #3 of all chains |
| TVL share of all chains | 7.91% |  |
| Stablecoin supply | $12.68B |  |
| DEX volume 24h | $3.41B | +6.4% vs prior day |
| DEX volume 7d | $24.90B |  |
| Circulating supply | 549.10M SOL | 90.7% of total |

### Largest DEXes by 24h volume

| DEX | Volume |
|---|---:|
| Raydium | $1.18B |
| Orca | $742.0M |
| Meteora | $631.0M |
| Lifinity | $288.0M |
| Phoenix | $174.0M |
| Invariant | $121.0M |
| Saber | $84.0M |
| Aldrin | $51.0M |

## Source status

| Source | Status | Latency |
|---|---|---:|
| `rpc:getHealth` | ok | 120 ms |
| `rpc:getEpochInfo` | ok | 120 ms |
| `rpc:getRecentPerformanceSamples` | ok | 120 ms |
| `rpc:getVoteAccounts` | ok | 120 ms |
| `rpc:getSupply` | ok | 120 ms |
| `defillama:price` | ok | 120 ms |
| `defillama:tvl` | ok | 120 ms |
| `defillama:stablecoins` | ok | 120 ms |
| `defillama:dex` | ok | 120 ms |
| `coingecko:price` | failed — HTTP 429 | — |

---

Collected from the Solana JSON-RPC, DeFiLlama and CoinGecko. No API keys required. Anomaly detection combines absolute rules with a median/MAD modified z-score against this deployment's own snapshot history.
