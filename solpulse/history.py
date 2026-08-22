"""Snapshot history, which is what makes anomaly detection possible.

A single reading cannot be anomalous — it needs a baseline. Each run appends a
compact snapshot to a local JSON file so later runs can compare against what
normal looked like.
"""

import json
from pathlib import Path

# Metrics worth trending. Deliberately narrow: history stays small and readable.
TRACKED = [
    "tps", "tps_non_vote", "slot_time_ms", "validators_active",
    "validators_delinquent", "delinquency_pct", "nakamoto_coefficient",
    "sol_price_usd", "tvl_usd", "stablecoin_supply_usd", "dex_volume_24h_usd",
]

MAX_SNAPSHOTS = 500


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.snapshots = self._load()

    def _load(self) -> list:
        if not self.path.exists():
            return []
        try:
            with self.path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            # A corrupt history must not stop a report from being produced.
            return []

    def append(self, timestamp: str, metrics: dict) -> None:
        snapshot = {"ts": timestamp}
        for key in TRACKED:
            if metrics.get(key) is not None:
                snapshot[key] = metrics[key]
        self.snapshots.append(snapshot)
        self.snapshots = self.snapshots[-MAX_SNAPSHOTS:]

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as fh:
                json.dump(self.snapshots, fh, indent=1)
        except OSError:
            pass

    def series(self, metric: str, exclude_last: bool = True) -> list:
        """Past values for a metric, oldest first.

        The current run's own snapshot is excluded by default so a reading is
        never compared against itself.
        """
        source = self.snapshots[:-1] if exclude_last and self.snapshots else self.snapshots
        return [s[metric] for s in source
                if isinstance(s.get(metric), (int, float))]

    def previous(self, metric: str):
        """Most recent stored value for a metric.

        Call this before appending the current run, when the last stored
        snapshot is genuinely the previous reading.
        """
        for snapshot in reversed(self.snapshots):
            if isinstance(snapshot.get(metric), (int, float)):
                return snapshot[metric]
        return None
