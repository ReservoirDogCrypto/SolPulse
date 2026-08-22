"""Human-readable Markdown report."""

from .render_html import fmt, fmt_exact


def _row(label: str, value: str, note: str = "") -> str:
    return f"| {label} | {value} | {note} |"


def render(report: dict) -> str:
    m = report["metrics"]
    anomalies = report["anomalies"]
    sources = report["sources"]

    lines = [
        "# Solana Ecosystem Report",
        "",
        f"*Generated {report['generated_at']} · SolPulse v{report['version']}*",
        "",
        f"**Network health:** `{m.get('health') or 'unknown'}` · "
        f"**Sources responding:** {sources['healthy']}/{sources['total']} · "
        f"**Anomalies:** {anomalies['count']}"
        + (f" ({anomalies['critical']} critical)" if anomalies["critical"] else ""),
        "",
    ]

    if anomalies["anomalies"]:
        lines += ["## Anomalies", ""]
        for a in anomalies["anomalies"]:
            lines.append(f"- **{a['severity'].upper()}** — {a['message']}")
        if anomalies.get("correlation"):
            lines.append(f"- **CORRELATED** — {anomalies['correlation']}")
        lines.append("")
    elif not anomalies["baseline_ready"]:
        need = 5 - anomalies["baseline_snapshots"]
        lines += ["## Anomalies", "",
                  f"None. Statistical detection needs {need} more run(s) to "
                  "establish a baseline; absolute rules are already active.", ""]
    else:
        lines += ["## Anomalies", "",
                  "None. All tracked metrics sit within their recent baselines.", ""]

    lines += ["## Network performance", "",
              "| Metric | Value | Notes |", "|---|---|---|",
              _row("Transactions per second", fmt(m.get("tps"), decimals=1),
                   "includes vote transactions"),
              _row("Non-vote TPS", fmt(m.get("tps_non_vote"), decimals=1),
                   "real user activity"),
              _row("Peak TPS (1h)", fmt(m.get("tps_peak_1h"), decimals=1), ""),
              _row("Average TPS (1h)", fmt(m.get("tps_avg_1h"), decimals=1), ""),
              _row("Slot time", f"{fmt(m.get('slot_time_ms'))} ms", "400ms target"),
              _row("Current slot", fmt_exact(m.get("slot")), ""),
              _row("Block height", fmt_exact(m.get("block_height")), ""),
              _row("Epoch", fmt_exact(m.get("epoch")),
                   f"{m.get('epoch_progress_pct', '—')}% complete"),
              _row("Epoch ETA", f"~{m.get('epoch_eta_hours', '—')} h",
                   "at target slot time"),
              ""]

    lines += ["## Validators", "",
              "| Metric | Value | Notes |", "|---|---|---|",
              _row("Active", fmt(m.get("validators_active")), ""),
              _row("Delinquent", fmt(m.get("validators_delinquent")),
                   f"{m.get('delinquency_pct', '—')}% by count"),
              _row("Delinquent stake", f"{m.get('delinquent_stake_pct', '—')}%",
                   "33% would halt finality"),
              _row("Nakamoto coefficient", fmt(m.get("nakamoto_coefficient")),
                   "validators needed to halt finality"),
              _row("Top-10 stake share", f"{m.get('top10_stake_pct', '—')}%", ""),
              _row("Total active stake", f"{fmt(m.get('total_stake_sol'))} SOL", ""),
              _row("Median commission", f"{m.get('median_commission', '—')}%", ""),
              _row("Zero-commission validators",
                   fmt(m.get("zero_commission_validators")), ""),
              ""]

    if m.get("top_validators"):
        lines += ["### Largest validators", "",
                  "| Identity | Stake (SOL) | Share | Commission |",
                  "|---|---:|---:|---:|"]
        for v in m["top_validators"]:
            lines.append(f"| `{v['identity']}` | {fmt(v['stake_sol'])} | "
                         f"{v['stake_pct']}% | {v['commission']}% |")
        lines.append("")

    lines += ["## Economics", "",
              "| Metric | Value | Notes |", "|---|---|---|",
              _row("SOL price", fmt(m.get("sol_price_usd"), "$"),
                   m.get("price_source", "")),
              _row("24h change",
                   f"{m['sol_change_24h_pct']:+.2f}%"
                   if m.get("sol_change_24h_pct") is not None else "—", ""),
              _row("Market cap", fmt(m.get("sol_market_cap_usd"), "$"), ""),
              _row("TVL", fmt(m.get("tvl_usd"), "$"),
                   f"rank #{m['tvl_rank']} of all chains" if m.get("tvl_rank") else ""),
              _row("TVL share of all chains", f"{m.get('tvl_share_pct', '—')}%", ""),
              _row("Stablecoin supply", fmt(m.get("stablecoin_supply_usd"), "$"), ""),
              _row("DEX volume 24h", fmt(m.get("dex_volume_24h_usd"), "$"),
                   f"{m['dex_volume_change_24h_pct']:+.1f}% vs prior day"
                   if m.get("dex_volume_change_24h_pct") is not None else ""),
              _row("DEX volume 7d", fmt(m.get("dex_volume_7d_usd"), "$"), ""),
              _row("Circulating supply", f"{fmt(m.get('supply_circulating_sol'))} SOL",
                   f"{m.get('supply_circulating_pct', '—')}% of total"),
              ""]

    if m.get("top_dexes"):
        lines += ["### Largest DEXes by 24h volume", "",
                  "| DEX | Volume |", "|---|---:|"]
        for d in m["top_dexes"]:
            lines.append(f"| {d['name']} | {fmt(d['volume_24h_usd'], '$')} |")
        lines.append("")

    lines += ["## Source status", "",
              "| Source | Status | Latency |", "|---|---|---:|"]
    for entry in sources["entries"]:
        status = "ok" if entry["ok"] else f"failed — {entry['error']}"
        latency = f"{entry['elapsed_ms']} ms" if entry["ok"] else "—"
        lines.append(f"| `{entry['source']}` | {status} | {latency} |")

    lines += ["",
              "---",
              "",
              "Collected from the Solana JSON-RPC, DeFiLlama and CoinGecko. "
              "No API keys required. Anomaly detection combines absolute rules "
              "with a median/MAD modified z-score against this deployment's own "
              "snapshot history.",
              ""]
    return "\n".join(lines)
