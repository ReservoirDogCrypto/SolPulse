"""Synthetic fixture data for offline runs.

`--demo` exists so the report can be generated, reviewed and screenshotted with
no network at all. It makes the project reviewable in restricted environments
and gives the test suite deterministic input. Values are plausible rather than
real, and every demo run is clearly labelled as such in the output.
"""

import math

from .http import Result, SourceLog


def build_metrics(seed: int = 0) -> dict:
    samples = []
    for i in range(60):
        wave = math.sin(i / 9) * 340 + math.cos(i / 4) * 120
        total = 3150 + wave + (i * 3)
        samples.append({
            "tps": round(total, 1),
            "tps_non_vote": round(total * 0.36, 1),
            "slot": 298_450_000 + i * 150,
        })

    # Base58-shaped identities so the demo screenshot looks like a real run.
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    validators = []
    stake = 13_800_000
    for i in range(10):
        stake = int(stake * 0.87)
        pubkey = "".join(alphabet[(i * 17 + n * 23 + 7) % len(alphabet)]
                         for n in range(8))
        validators.append({
            "identity": pubkey + "…",
            "vote_account": pubkey[::-1] + "…",
            "stake_sol": stake,
            "stake_pct": round(stake / 396_000_000 * 100, 2),
            "commission": [0, 5, 8, 10, 0, 7, 10, 5, 0, 10][i],
        })

    return {
        "health": "ok",
        "tps": samples[-1]["tps"],
        "tps_non_vote": samples[-1]["tps_non_vote"],
        "tps_avg_1h": round(sum(s["tps"] for s in samples) / len(samples), 1),
        "tps_peak_1h": max(s["tps"] for s in samples),
        "slot_time_ms": 412,
        "slot": 298_459_000,
        "block_height": 276_902_411,
        "block_time_unix": 1_755_500_000,
        "epoch": 842,
        "slot_index": 187_400,
        "slots_in_epoch": 432_000,
        "epoch_progress_pct": 43.38,
        "epoch_eta_hours": 27.2,
        "tps_series": samples,
        "validators_active": 1_312,
        "validators_delinquent": 41,
        "validators_total": 1_353,
        "delinquency_pct": 3.03,
        "delinquent_stake_pct": 1.42,
        "total_stake_sol": 396_140_000,
        "nakamoto_coefficient": 21,
        "top10_stake_pct": 17.84,
        "median_commission": 7,
        "zero_commission_validators": 214,
        "top_validators": validators,
        "sol_price_usd": 184.32,
        "sol_change_24h_pct": -2.14,
        "sol_market_cap_usd": 99_400_000_000,
        "sol_volume_24h_usd": 3_820_000_000,
        "price_source": "DeFiLlama (demo)",
        "tvl_usd": 9_240_000_000,
        "tvl_rank": 3,
        "tvl_share_pct": 7.91,
        "stablecoin_supply_usd": 12_680_000_000,
        "dex_volume_24h_usd": 3_410_000_000,
        "dex_volume_7d_usd": 24_900_000_000,
        "dex_volume_change_24h_pct": 6.4,
        "top_dexes": [
            {"name": "Raydium", "volume_24h_usd": 1_180_000_000},
            {"name": "Orca", "volume_24h_usd": 742_000_000},
            {"name": "Meteora", "volume_24h_usd": 631_000_000},
            {"name": "Lifinity", "volume_24h_usd": 288_000_000},
            {"name": "Phoenix", "volume_24h_usd": 174_000_000},
            {"name": "Invariant", "volume_24h_usd": 121_000_000},
            {"name": "Saber", "volume_24h_usd": 84_000_000},
            {"name": "Aldrin", "volume_24h_usd": 51_000_000},
        ],
        "supply_total_sol": 605_400_000,
        "supply_circulating_sol": 549_100_000,
        "supply_circulating_pct": 90.7,
    }


def build_log() -> SourceLog:
    log = SourceLog()
    for name in ["rpc:getHealth", "rpc:getEpochInfo",
                 "rpc:getRecentPerformanceSamples", "rpc:getVoteAccounts",
                 "rpc:getSupply", "defillama:price", "defillama:tvl",
                 "defillama:stablecoins", "defillama:dex"]:
        log.record(Result(ok=True, source=name, elapsed_ms=120))
    log.record(Result.failure("coingecko:price", "HTTP 429"))
    return log
