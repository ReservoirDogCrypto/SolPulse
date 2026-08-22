#!/usr/bin/env python3
"""SolPulse — auto-updating Solana ecosystem report.

Generates an interactive HTML dashboard, a Markdown report and structured JSON
from live on-chain and off-chain data. Standard library only; no API keys.

    python3 solpulse.py                 # collect live data, write all formats
    python3 solpulse.py --demo          # offline run using fixture data
    python3 solpulse.py --watch 300     # refresh every 5 minutes
    python3 solpulse.py --format json   # one format only

Exit status is 0 on success, 1 when every data source failed, and 2 when a
critical anomaly is present — so a scheduler or CI job can alert on it.
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from solpulse import __version__, anomaly, demo, history, render_html, render_json, render_md
from solpulse.http import SourceLog
from solpulse.rpc import SolanaRPC, collect_network, collect_supply, collect_validators
from solpulse.sources import collect_dex, collect_price, collect_stablecoins, collect_tvl


def collect(use_demo: bool) -> tuple:
    if use_demo:
        return demo.build_metrics(), demo.build_log()

    log = SourceLog()
    rpc = SolanaRPC(log)
    metrics: dict = {}
    # Each collector is independent, so one failing source costs its own
    # metrics and nothing else.
    metrics.update(collect_network(rpc))
    metrics.update(collect_validators(rpc))
    metrics.update(collect_supply(rpc))
    metrics.update(collect_price(log))
    metrics.update(collect_tvl(log))
    metrics.update(collect_stablecoins(log))
    metrics.update(collect_dex(log))
    return metrics, log


def build_report(metrics: dict, log: SourceLog, hist: history.History,
                 demo_mode: bool) -> dict:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Capture the previous reading before appending this one, so each tile can
    # show movement since the last run rather than a bare snapshot.
    deltas = {}
    for key in history.TRACKED:
        current = metrics.get(key)
        prior = hist.previous(key)
        if isinstance(current, (int, float)) and isinstance(prior, (int, float)) and prior:
            deltas[key] = round((current - prior) / abs(prior) * 100, 1)

    hist.append(now.isoformat(), metrics)
    found = anomaly.detect(metrics, hist)
    hist.save()

    return {
        "version": __version__ + (" (demo)" if demo_mode else ""),
        "generated_at": stamp,
        "metrics": metrics,
        "deltas": deltas,
        "anomalies": found,
        "sources": {
            "healthy": log.healthy,
            "total": log.total,
            "entries": log.entries,
        },
    }


def write_outputs(report: dict, out_dir: Path, formats: list) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if "html" in formats:
        page = render_html.render(report)
        # index.html is what GitHub Pages serves at the directory root; without
        # it the published dashboard is a 404. dashboard.html is kept alongside
        # so the documented path keeps working.
        for name in ("index.html", "dashboard.html"):
            path = out_dir / name
            path.write_text(page, encoding="utf-8")
            written.append(path)
    if "markdown" in formats:
        path = out_dir / "report.md"
        path.write_text(render_md.render(report), encoding="utf-8")
        written.append(path)
    if "json" in formats:
        path = out_dir / "report.json"
        path.write_text(render_json.render(report), encoding="utf-8")
        written.append(path)
    return written


def run_once(args) -> int:
    metrics, log = collect(args.demo)

    if log.total and log.healthy == 0:
        print("error: every data source failed; no report written",
              file=sys.stderr)
        for entry in log.entries:
            print(f"  {entry['source']}: {entry['error']}", file=sys.stderr)
        return 1

    hist = history.History(Path(args.history))
    report = build_report(metrics, log, hist, args.demo)

    formats = ["html", "markdown", "json"] if args.format == "all" else [args.format]
    written = write_outputs(report, Path(args.out), formats)

    found = report["anomalies"]
    print(f"SolPulse {report['version']} · {report['generated_at']}")
    print(f"  sources  : {log.healthy}/{log.total} responded")
    print(f"  anomalies: {found['count']} "
          f"({found['critical']} critical, {found['warning']} warning)")
    print(f"  baseline : {found['baseline_snapshots']} snapshots"
          f"{'' if found['baseline_ready'] else ' (statistics not yet active)'}")
    for path in written:
        print(f"  wrote    : {path}")

    return 2 if found["critical"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="solpulse",
        description="Auto-updating Solana ecosystem report and dashboard.")
    parser.add_argument("--out", default="output",
                        help="output directory (default: output)")
    parser.add_argument("--format", default="all",
                        choices=["all", "html", "markdown", "json"],
                        help="which format to write (default: all)")
    parser.add_argument("--history", default="output/history.json",
                        help="snapshot history file, the anomaly baseline")
    parser.add_argument("--watch", type=int, metavar="SECONDS",
                        help="refresh on an interval instead of exiting")
    parser.add_argument("--demo", action="store_true",
                        help="use offline fixture data, no network needed")
    parser.add_argument("--version", action="version",
                        version=f"SolPulse {__version__}")
    args = parser.parse_args()

    if not args.watch:
        return run_once(args)

    interval = max(args.watch, 30)
    print(f"Watching: refreshing every {interval}s. Ctrl-C to stop.\n")
    while True:
        try:
            run_once(args)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0
        except Exception as exc:  # noqa: BLE001 - a watch loop must survive a bad run
            print(f"run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0


if __name__ == "__main__":
    sys.exit(main())
