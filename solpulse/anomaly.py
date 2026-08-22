"""Anomaly detection over collected metrics.

Two independent layers, because they catch different failures:

1. Rules — conditions that are bad in absolute terms no matter the history
   (the chain reporting unhealthy, delinquency above a safe share of stake).
   These fire on the very first run, when no baseline exists yet.

2. Statistics — deviation from this deployment's own recent history, using a
   median/MAD modified z-score. Mean and standard deviation are avoided on
   purpose: crypto metrics are spiky, and a single 10x spike inflates the
   standard deviation so much that later real anomalies stop registering.
   Median and MAD are resistant to exactly that.

When several unrelated metrics go anomalous in the same run, that correlation is
itself reported — a TPS drop alongside rising delinquency tells a different
story than either alone.
"""

from statistics import median

# Modified z-score above which a value is called anomalous. 3.5 is the
# conventional cutoff for the median/MAD form (Iglewicz & Hoaglin).
Z_THRESHOLD = 3.5

# Statistics need a baseline; below this many past readings, rules only.
MIN_HISTORY = 5

# On a perfectly constant series the z-score is undefined, so a departure is
# judged by relative change instead: moves under this fraction are treated as
# noise, anything larger is reported at a fixed high score.
FLAT_SERIES_TOLERANCE = 0.05
FLAT_SERIES_SCORE = 99.0

# Absolute floor for the Nakamoto coefficient. Solana's sits around 19, so a
# threshold at 20 would fire on every single run — and an anomaly panel that
# always shows the same warning trains the reader to ignore all of them. A
# standing structural fact belongs in a metric tile, not an alert feed; this
# floor is set where the number would be genuinely alarming, and *degradation*
# from the current level is left to the statistical layer, which catches a drop
# relative to this deployment's own baseline.
NAKAMOTO_FLOOR = 15

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _modified_z(value: float, series: list):
    """Median/MAD modified z-score, or None when the series cannot support one."""
    if len(series) < MIN_HISTORY:
        return None
    med = median(series)
    deviations = [abs(x - med) for x in series]
    mad = median(deviations)
    if mad == 0:
        # Half or more of the series sits on the median. Fall back to mean
        # absolute deviation so a genuine departure is still detectable.
        mean_abs = sum(deviations) / len(deviations) if deviations else 0
        if mean_abs > 0:
            return 0.7979 * (value - med) / mean_abs

        # Perfectly constant series: any change is infinitely many deviations,
        # so scale by relative change instead. Integer metrics such as the
        # validator count sit flat for long stretches, and returning None here
        # would silently swallow the very jump worth reporting.
        if value == med:
            return 0.0
        relative = abs(value - med) / abs(med) if med else 1.0
        if relative < FLAT_SERIES_TOLERANCE:
            return 0.0
        return FLAT_SERIES_SCORE if value > med else -FLAT_SERIES_SCORE
    return 0.6745 * (value - med) / mad


def _rules(metrics: dict) -> list:
    found = []

    if metrics.get("health") not in ("ok", None):
        found.append({
            "severity": "critical",
            "metric": "health",
            "message": f"RPC reports node health as '{metrics.get('health')}'",
        })

    delinquency = metrics.get("delinquent_stake_pct")
    if isinstance(delinquency, (int, float)):
        if delinquency > 10:
            found.append({
                "severity": "critical",
                "metric": "delinquent_stake_pct",
                "message": (
                    f"{delinquency}% of stake is delinquent — approaching the "
                    "33% that would halt finality"
                ),
            })
        elif delinquency > 5:
            found.append({
                "severity": "warning",
                "metric": "delinquent_stake_pct",
                "message": f"{delinquency}% of stake is delinquent (normal is under 5%)",
            })

    nakamoto = metrics.get("nakamoto_coefficient")
    if isinstance(nakamoto, int) and nakamoto < NAKAMOTO_FLOOR:
        found.append({
            "severity": "warning",
            "metric": "nakamoto_coefficient",
            "message": (
                f"Nakamoto coefficient has fallen to {nakamoto}: only {nakamoto} "
                "validators would need to collude to halt finality"
            ),
        })

    slot_time = metrics.get("slot_time_ms")
    if isinstance(slot_time, (int, float)) and slot_time > 600:
        found.append({
            "severity": "warning",
            "metric": "slot_time_ms",
            "message": f"Slot time {slot_time}ms is well above the 400ms target",
        })

    tps = metrics.get("tps")
    if isinstance(tps, (int, float)) and tps < 500:
        found.append({
            "severity": "critical",
            "metric": "tps",
            "message": f"Throughput has fallen to {tps} TPS",
        })

    return found


def _statistical(metrics: dict, history) -> list:
    found = []
    watched = {
        "tps": ("Throughput", "warning"),
        "tps_non_vote": ("Non-vote throughput", "warning"),
        "slot_time_ms": ("Slot time", "warning"),
        "delinquency_pct": ("Validator delinquency", "warning"),
        "nakamoto_coefficient": ("Nakamoto coefficient", "warning"),
        "sol_price_usd": ("SOL price", "info"),
        "tvl_usd": ("TVL", "info"),
        "stablecoin_supply_usd": ("Stablecoin supply", "info"),
        "dex_volume_24h_usd": ("DEX volume", "info"),
    }

    for key, (label, severity) in watched.items():
        value = metrics.get(key)
        if not isinstance(value, (int, float)):
            continue
        series = history.series(key)
        score = _modified_z(value, series)
        if score is None or abs(score) < Z_THRESHOLD:
            continue

        baseline = median(series)
        direction = "above" if score > 0 else "below"
        change = ((value - baseline) / baseline * 100) if baseline else 0
        found.append({
            "severity": severity,
            "metric": key,
            "z_score": round(score, 2),
            "baseline": baseline,
            "message": (
                f"{label} is {abs(change):.1f}% {direction} its recent baseline "
                f"({_fmt(value)} vs {_fmt(baseline)}, z={score:+.1f})"
            ),
        })

    return found


def _fmt(value) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def detect(metrics: dict, history) -> dict:
    """Run both layers and summarise what was found."""
    anomalies = _rules(metrics) + _statistical(metrics, history)
    anomalies.sort(key=lambda a: SEVERITY_ORDER.get(a["severity"], 9))

    baseline_size = len(history.snapshots) - 1 if history.snapshots else 0
    correlated = None
    network_hit = {a["metric"] for a in anomalies} & {
        "tps", "tps_non_vote", "slot_time_ms", "health"}
    validator_hit = {a["metric"] for a in anomalies} & {
        "delinquency_pct", "delinquent_stake_pct", "nakamoto_coefficient"}
    if network_hit and validator_hit:
        correlated = (
            "Network throughput and validator health are both anomalous in the "
            "same run — these usually move together during an incident rather "
            "than independently."
        )

    return {
        "count": len(anomalies),
        "critical": sum(1 for a in anomalies if a["severity"] == "critical"),
        "warning": sum(1 for a in anomalies if a["severity"] == "warning"),
        "info": sum(1 for a in anomalies if a["severity"] == "info"),
        "anomalies": anomalies,
        "correlation": correlated,
        "baseline_snapshots": baseline_size,
        "baseline_ready": baseline_size >= MIN_HISTORY,
    }
