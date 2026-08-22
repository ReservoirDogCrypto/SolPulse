"""Machine-readable JSON output.

Structured for consumption rather than display: metrics are grouped by domain
and every run carries a schema version so downstream consumers can detect
format changes instead of silently misreading fields.
"""

import json

SCHEMA_VERSION = "1.0"

GROUPS = {
    "network": ["health", "tps", "tps_non_vote", "tps_avg_1h", "tps_peak_1h",
                "slot_time_ms", "slot", "block_height", "block_time_unix",
                "epoch", "slot_index", "slots_in_epoch", "epoch_progress_pct",
                "epoch_eta_hours"],
    "validators": ["validators_active", "validators_delinquent", "validators_total",
                   "delinquency_pct", "delinquent_stake_pct", "total_stake_sol",
                   "nakamoto_coefficient", "top10_stake_pct", "median_commission",
                   "zero_commission_validators", "top_validators"],
    "economics": ["sol_price_usd", "sol_change_24h_pct", "sol_market_cap_usd",
                  "sol_volume_24h_usd", "price_source", "price_confidence",
                  "tvl_usd", "tvl_rank", "tvl_share_pct", "stablecoin_supply_usd",
                  "dex_volume_24h_usd", "dex_volume_7d_usd",
                  "dex_volume_change_24h_pct", "top_dexes"],
    "supply": ["supply_total_sol", "supply_circulating_sol", "supply_circulating_pct"],
}


def build(report: dict) -> dict:
    metrics = report["metrics"]
    grouped = {}
    for group, keys in GROUPS.items():
        grouped[group] = {k: metrics[k] for k in keys if metrics.get(k) is not None}

    return {
        "schema_version": SCHEMA_VERSION,
        "generator": f"SolPulse v{report['version']}",
        "generated_at": report["generated_at"],
        "metrics": grouped,
        "timeseries": {"tps_samples": metrics.get("tps_series") or []},
        "anomalies": report["anomalies"],
        "sources": report["sources"],
    }


def render(report: dict) -> str:
    return json.dumps(build(report), indent=2, ensure_ascii=False)
