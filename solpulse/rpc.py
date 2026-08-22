"""Solana JSON-RPC client and the metrics derived from it.

Only public mainnet endpoints are used, so no API key is ever required. Public
RPC nodes rate-limit aggressively, so the client falls back across a list of
endpoints rather than hammering one.
"""

from typing import Optional

from .http import DEFAULT_TIMEOUT, Result, SourceLog, fetch_json

# Public endpoints, tried in order. The first is Solana Labs' own; the others
# are widely used public mirrors that also require no key.
ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana",
]

LAMPORTS_PER_SOL = 1_000_000_000


class SolanaRPC:
    """Thin JSON-RPC wrapper that fails over between public endpoints."""

    def __init__(self, log: SourceLog, endpoints: Optional[list] = None):
        self.log = log
        self.endpoints = endpoints or list(ENDPOINTS)
        self._working: Optional[str] = None

    # getSupply walks every account and measured ~6.7s against the public
    # endpoint, so it gets its own allowance rather than racing the default.
    SLOW_METHODS = {"getSupply": 30}

    def call(self, method: str, params: Optional[list] = None) -> Result:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }

        # Stay on an endpoint that already answered; only search again if it dies.
        ordered = self.endpoints
        if self._working:
            ordered = [self._working] + [e for e in self.endpoints if e != self._working]

        last: Result = Result.failure(f"rpc:{method}", "no endpoint reachable")
        for endpoint in ordered:
            result = fetch_json(endpoint, f"rpc:{method}", payload=payload, retries=1,
                                timeout=self.SLOW_METHODS.get(method, DEFAULT_TIMEOUT))
            if not result.ok:
                last = result
                continue

            body = result.data or {}
            if "error" in body:
                err = body["error"]
                last = Result.failure(
                    f"rpc:{method}",
                    f"RPC error {err.get('code')}: {err.get('message', '')}",
                )
                continue

            self._working = endpoint
            result.data = body.get("result")
            return self.log.record(result)

        return self.log.record(last)


def collect_network(rpc: SolanaRPC) -> dict:
    """Network liveness and throughput."""
    out: dict = {}

    health = rpc.call("getHealth")
    out["health"] = health.data if health.ok else None

    epoch = rpc.call("getEpochInfo")
    if epoch.ok and isinstance(epoch.data, dict):
        info = epoch.data
        slots_in_epoch = info.get("slotsInEpoch") or 0
        slot_index = info.get("slotIndex") or 0
        out["epoch"] = info.get("epoch")
        out["slot"] = info.get("absoluteSlot")
        out["block_height"] = info.get("blockHeight")
        out["slot_index"] = slot_index
        out["slots_in_epoch"] = slots_in_epoch
        out["epoch_progress_pct"] = (
            round(slot_index / slots_in_epoch * 100, 2) if slots_in_epoch else None
        )
        # Mainnet targets 400ms slots; remaining wall-clock time follows from that.
        remaining = max(slots_in_epoch - slot_index, 0)
        out["epoch_eta_hours"] = round(remaining * 0.4 / 3600, 1) if slots_in_epoch else None

    perf = rpc.call("getRecentPerformanceSamples", [60])
    if perf.ok and isinstance(perf.data, list) and perf.data:
        samples = perf.data
        latest = samples[0]
        period = latest.get("samplePeriodSecs") or 60
        num_slots = latest.get("numSlots") or 0

        out["tps"] = round((latest.get("numTransactions") or 0) / period, 1)
        # Vote transactions dominate raw counts; non-vote TPS is the number that
        # reflects actual user activity, so both are reported.
        non_vote = latest.get("numNonVoteTransactions")
        out["tps_non_vote"] = round(non_vote / period, 1) if non_vote is not None else None
        out["slot_time_ms"] = round(period / num_slots * 1000) if num_slots else None

        series = []
        for sample in samples:
            p = sample.get("samplePeriodSecs") or 60
            series.append({
                "tps": round((sample.get("numTransactions") or 0) / p, 1),
                "tps_non_vote": (
                    round(sample["numNonVoteTransactions"] / p, 1)
                    if sample.get("numNonVoteTransactions") is not None else None
                ),
                "slot": sample.get("slot"),
            })
        # Samples arrive newest-first; charts read left-to-right in time order.
        out["tps_series"] = list(reversed(series))

        tps_values = [s["tps"] for s in series if s["tps"] is not None]
        if tps_values:
            out["tps_avg_1h"] = round(sum(tps_values) / len(tps_values), 1)
            out["tps_peak_1h"] = max(tps_values)

    block_time = rpc.call("getBlockTime", [out["slot"]]) if out.get("slot") else None
    if block_time and block_time.ok:
        out["block_time_unix"] = block_time.data

    return out


def collect_validators(rpc: SolanaRPC) -> dict:
    """Validator set health and stake concentration."""
    out: dict = {}
    votes = rpc.call("getVoteAccounts")
    if not (votes.ok and isinstance(votes.data, dict)):
        return out

    current = votes.data.get("current") or []
    delinquent = votes.data.get("delinquent") or []

    out["validators_active"] = len(current)
    out["validators_delinquent"] = len(delinquent)
    total_count = len(current) + len(delinquent)
    out["validators_total"] = total_count
    out["delinquency_pct"] = (
        round(len(delinquent) / total_count * 100, 2) if total_count else 0.0
    )

    stakes = sorted((v.get("activatedStake") or 0) for v in current)
    stakes.reverse()
    total_stake = sum(stakes)
    out["total_stake_sol"] = round(total_stake / LAMPORTS_PER_SOL)

    delinquent_stake = sum((v.get("activatedStake") or 0) for v in delinquent)
    out["delinquent_stake_pct"] = (
        round(delinquent_stake / (total_stake + delinquent_stake) * 100, 2)
        if (total_stake + delinquent_stake) else 0.0
    )

    if total_stake and stakes:
        # Nakamoto coefficient: how few validators must collude to halt the
        # chain. Solana needs >1/3 of stake to stop finality, so this counts the
        # smallest set reaching 33.3%. Lower is worse.
        threshold = total_stake / 3
        running = 0
        nakamoto = 0
        for stake in stakes:
            running += stake
            nakamoto += 1
            if running > threshold:
                break
        out["nakamoto_coefficient"] = nakamoto

        out["top_validators"] = [
            {
                "identity": v.get("nodePubkey", "")[:8] + "…",
                "vote_account": v.get("votePubkey", "")[:8] + "…",
                "stake_sol": round((v.get("activatedStake") or 0) / LAMPORTS_PER_SOL),
                "stake_pct": round((v.get("activatedStake") or 0) / total_stake * 100, 2),
                "commission": v.get("commission"),
            }
            for v in sorted(current, key=lambda x: x.get("activatedStake") or 0,
                            reverse=True)[:10]
        ]

        commissions = [v.get("commission") for v in current
                       if isinstance(v.get("commission"), int)]
        if commissions:
            commissions.sort()
            mid = len(commissions) // 2
            out["median_commission"] = (
                commissions[mid] if len(commissions) % 2
                else (commissions[mid - 1] + commissions[mid]) / 2
            )
            out["zero_commission_validators"] = sum(1 for c in commissions if c == 0)

        top_stake = sum(stakes[:10])
        out["top10_stake_pct"] = round(top_stake / total_stake * 100, 2)

    return out


def collect_supply(rpc: SolanaRPC) -> dict:
    """SOL supply figures."""
    out: dict = {}
    supply = rpc.call("getSupply", [{"excludeNonCirculatingAccountsList": True}])
    if supply.ok and isinstance(supply.data, dict):
        value = supply.data.get("value") or {}
        total = value.get("total")
        circulating = value.get("circulating")
        if total:
            out["supply_total_sol"] = round(total / LAMPORTS_PER_SOL)
        if circulating:
            out["supply_circulating_sol"] = round(circulating / LAMPORTS_PER_SOL)
        if total and circulating:
            out["supply_circulating_pct"] = round(circulating / total * 100, 2)
    return out
