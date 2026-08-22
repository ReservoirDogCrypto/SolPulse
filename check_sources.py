#!/usr/bin/env python3
"""Standalone connectivity and shape check for SolPulse's data sources.

Run this before trusting a live report. It contacts every source SolPulse uses
and verifies not just that each responds, but that the specific fields the
parsers read are actually present — a source can be up and still have renamed a
key, which is the failure that would quietly hollow out the report.

Self-contained: copy this one file anywhere and run it.

    python3 check_sources.py
"""

import json
import sys
import time
import urllib.error
import urllib.request

TIMEOUT = 20
HEADERS = {"User-Agent": "SolPulse-check/1.0", "Accept": "application/json"}

RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana",
]

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ""

results = []


def get(url, payload=None):
    body = json.dumps(payload).encode() if payload else None
    headers = dict(HEADERS)
    if payload:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read())
    return data, int((time.monotonic() - started) * 1000)


def check(name, url, payload=None, expect=None, dig=None):
    """Fetch one source and confirm the fields the parser depends on exist."""
    expect = expect or []
    sys.stdout.write(f"  {name:38}")
    sys.stdout.flush()
    try:
        data, ms = get(url, payload)
    except urllib.error.HTTPError as exc:
        print(f"{RED}FAIL{RESET}  HTTP {exc.code}")
        results.append((name, False, f"HTTP {exc.code}"))
        return None
    except Exception as exc:
        print(f"{RED}FAIL{RESET}  {type(exc).__name__}: {exc}")
        results.append((name, False, str(exc)))
        return None

    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        print(f"{RED}FAIL{RESET}  RPC error {err.get('code')}: {err.get('message','')}")
        results.append((name, False, "rpc error"))
        return None

    probe = dig(data) if dig else data
    missing = []
    if expect and isinstance(probe, dict):
        missing = [k for k in expect if k not in probe]

    if missing:
        print(f"{YELLOW}SHAPE{RESET} {ms:>5}ms  missing: {', '.join(missing)}")
        results.append((name, False, f"missing {missing}"))
    else:
        print(f"{GREEN}OK{RESET}    {ms:>5}ms")
        results.append((name, True, ""))
    return probe


def rpc(method, params=None):
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}


print("\nSolPulse source check\n" + "=" * 58)

print("\nSolana JSON-RPC — finding a working endpoint")
endpoint = None
for candidate in RPC_ENDPOINTS:
    sys.stdout.write(f"  {candidate:38}")
    sys.stdout.flush()
    try:
        data, ms = get(candidate, rpc("getHealth"))
        if "error" not in data:
            print(f"{GREEN}OK{RESET}    {ms:>5}ms   health={data.get('result')}")
            endpoint = candidate
            break
        print(f"{YELLOW}RPC error{RESET}")
    except Exception as exc:
        print(f"{RED}unreachable{RESET}  {type(exc).__name__}")

if not endpoint:
    print(f"\n{RED}No Solana RPC endpoint reachable. Check your connection.{RESET}\n")
    sys.exit(1)

print(f"\nSolana JSON-RPC — methods  {DIM}(via {endpoint}){RESET}")
epoch = check("getEpochInfo", endpoint, rpc("getEpochInfo"),
              expect=["epoch", "absoluteSlot", "slotIndex", "slotsInEpoch",
                      "blockHeight"],
              dig=lambda d: d.get("result"))

perf = check("getRecentPerformanceSamples", endpoint,
             rpc("getRecentPerformanceSamples", [5]),
             expect=["numTransactions", "numSlots", "samplePeriodSecs"],
             dig=lambda d: (d.get("result") or [{}])[0])

votes = check("getVoteAccounts", endpoint, rpc("getVoteAccounts"),
              expect=["current", "delinquent"],
              dig=lambda d: d.get("result"))

supply = check("getSupply", endpoint,
               rpc("getSupply", [{"excludeNonCirculatingAccountsList": True}]),
               expect=["total", "circulating"],
               dig=lambda d: (d.get("result") or {}).get("value"))

print("\nOff-chain sources")
price = check("DeFiLlama price", "https://coins.llama.fi/prices/current/coingecko:solana",
              expect=["price"],
              dig=lambda d: (d.get("coins") or {}).get("coingecko:solana"))

chains = check("DeFiLlama chains (TVL)", "https://api.llama.fi/v2/chains")
stables = check("DeFiLlama stablecoins", "https://stablecoins.llama.fi/stablecoinchains")
dex = check("DeFiLlama DEX volume",
            "https://api.llama.fi/overview/dexs/solana?excludeTotalDataChart=true",
            expect=["total24h"])
cg = check("CoinGecko price (fallback)",
           "https://api.coingecko.com/api/v3/simple/price?ids=solana"
           "&vs_currencies=usd&include_24hr_change=true&include_market_cap=true",
           expect=["usd"], dig=lambda d: d.get("solana"))

print("\n" + "=" * 58)
print("Sample of values read\n")


def show(label, value):
    print(f"  {label:34} {value}")


if perf:
    period = perf.get("samplePeriodSecs") or 60
    show("TPS (total)", round((perf.get("numTransactions") or 0) / period, 1))
    nv = perf.get("numNonVoteTransactions")
    show("TPS (non-vote)",
         round(nv / period, 1) if nv is not None
         else f"{YELLOW}numNonVoteTransactions absent{RESET}")
if epoch:
    show("Epoch", epoch.get("epoch"))
    show("Slot", f"{epoch.get('absoluteSlot'):,}" if epoch.get("absoluteSlot") else "—")
if votes:
    current, delinquent = votes.get("current") or [], votes.get("delinquent") or []
    show("Validators active / delinquent", f"{len(current)} / {len(delinquent)}")
    if current:
        show("First validator keys present",
             all(k in current[0] for k in ("activatedStake", "nodePubkey",
                                           "votePubkey", "commission")))
if supply:
    total = supply.get("total")
    show("Total supply (SOL)", f"{total / 1e9:,.0f}" if total else "—")
if price:
    show("SOL price (DeFiLlama)", price.get("price"))
if cg:
    show("SOL price (CoinGecko)", cg.get("usd"))
if isinstance(chains, list):
    solana = next((c for c in chains
                   if isinstance(c, dict) and (c.get("name") or "").lower() == "solana"),
                  None)
    show("Solana TVL", f"${solana['tvl']:,.0f}" if solana and solana.get("tvl")
         else f"{YELLOW}Solana not found in chain list{RESET}")
if isinstance(stables, list):
    solana = next((c for c in stables
                   if isinstance(c, dict)
                   and (c.get("gecko_id") or c.get("name") or "").lower() == "solana"),
                  None)
    if solana and isinstance(solana.get("totalCirculatingUSD"), dict):
        show("Stablecoin supply",
             f"${sum(solana['totalCirculatingUSD'].values()):,.0f}")
    else:
        show("Stablecoin supply", f"{YELLOW}shape differs — send this output{RESET}")
if isinstance(dex, dict):
    show("DEX volume 24h", f"${dex.get('total24h', 0):,.0f}")
    protocols = dex.get("protocols")
    show("DEX protocol list present",
         f"{len(protocols)} entries" if isinstance(protocols, list) else
         f"{YELLOW}absent — top-DEX chart will be empty{RESET}")

ok = sum(1 for _, good, _ in results if good)
print("\n" + "=" * 58)
print(f"\n  {ok}/{len(results)} checks passed\n")
for name, good, why in results:
    if not good:
        print(f"  {RED}✗{RESET} {name}: {why}")
if ok == len(results):
    print(f"  {GREEN}All sources healthy. Run: python3 solpulse.py{RESET}\n")
else:
    print(f"\n  Send this whole output back and the parsers will be adjusted.\n")
