"""Off-chain data sources: DeFiLlama and CoinGecko.

Both offer keyless public endpoints. DeFiLlama is treated as primary because
CoinGecko's free tier increasingly demands a demo key; CoinGecko is kept as a
fallback so price survives one of the two going down.

Every parser here is defensive: upstream shapes change without notice, and a
missing field must degrade one metric, not the whole report.
"""

from .http import SourceLog, fetch_json

LLAMA_PRICE = "https://coins.llama.fi/prices/current/coingecko:solana"
LLAMA_CHAINS = "https://api.llama.fi/v2/chains"
LLAMA_STABLES = "https://stablecoins.llama.fi/stablecoinchains"
LLAMA_DEX = "https://api.llama.fi/overview/dexs/solana?excludeTotalDataChart=true"
COINGECKO_PRICE = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=solana&vs_currencies=usd&include_24hr_change=true"
    "&include_market_cap=true&include_24hr_vol=true"
)


def _num(value):
    """Coerce to float when possible; upstream mixes strings and numbers."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_price(log: SourceLog) -> dict:
    """SOL price, preferring DeFiLlama and falling back to CoinGecko."""
    out: dict = {}

    res = log.record(fetch_json(LLAMA_PRICE, "defillama:price"))
    if res.ok and isinstance(res.data, dict):
        coin = (res.data.get("coins") or {}).get("coingecko:solana") or {}
        price = _num(coin.get("price"))
        if price:
            out["sol_price_usd"] = round(price, 2)
            out["price_source"] = "DeFiLlama"
            confidence = _num(coin.get("confidence"))
            if confidence is not None:
                out["price_confidence"] = round(confidence, 3)

    res = log.record(fetch_json(COINGECKO_PRICE, "coingecko:price"))
    if res.ok and isinstance(res.data, dict):
        sol = res.data.get("solana") or {}
        price = _num(sol.get("usd"))
        if price and "sol_price_usd" not in out:
            out["sol_price_usd"] = round(price, 2)
            out["price_source"] = "CoinGecko"
        change = _num(sol.get("usd_24h_change"))
        if change is not None:
            out["sol_change_24h_pct"] = round(change, 2)
        mcap = _num(sol.get("usd_market_cap"))
        if mcap:
            out["sol_market_cap_usd"] = round(mcap)
        vol = _num(sol.get("usd_24h_vol"))
        if vol:
            out["sol_volume_24h_usd"] = round(vol)

    return out


def collect_tvl(log: SourceLog) -> dict:
    """Total value locked on Solana, plus its rank among all chains."""
    out: dict = {}
    res = log.record(fetch_json(LLAMA_CHAINS, "defillama:tvl"))
    if not (res.ok and isinstance(res.data, list)):
        return out

    chains = [c for c in res.data if isinstance(c, dict)]
    ranked = sorted(chains, key=lambda c: _num(c.get("tvl")) or 0, reverse=True)
    for position, chain in enumerate(ranked, start=1):
        if (chain.get("name") or "").lower() == "solana":
            tvl = _num(chain.get("tvl"))
            if tvl:
                out["tvl_usd"] = round(tvl)
                out["tvl_rank"] = position
                total = sum(_num(c.get("tvl")) or 0 for c in ranked)
                if total:
                    out["tvl_share_pct"] = round(tvl / total * 100, 2)
            break
    return out


def collect_stablecoins(log: SourceLog) -> dict:
    """Stablecoin float sitting on Solana."""
    out: dict = {}
    res = log.record(fetch_json(LLAMA_STABLES, "defillama:stablecoins"))
    if not (res.ok and isinstance(res.data, list)):
        return out

    for chain in res.data:
        if not isinstance(chain, dict):
            continue
        if (chain.get("gecko_id") or chain.get("name") or "").lower() == "solana":
            circulating = chain.get("totalCirculatingUSD")
            if isinstance(circulating, dict):
                total = sum(_num(v) or 0 for v in circulating.values())
                if total:
                    out["stablecoin_supply_usd"] = round(total)
            break
    return out


def collect_dex(log: SourceLog) -> dict:
    """DEX volume, a proxy for real economic activity."""
    out: dict = {}
    res = log.record(fetch_json(LLAMA_DEX, "defillama:dex"))
    if not (res.ok and isinstance(res.data, dict)):
        return out

    day = _num(res.data.get("total24h"))
    if day:
        out["dex_volume_24h_usd"] = round(day)
    week = _num(res.data.get("total7d"))
    if week:
        out["dex_volume_7d_usd"] = round(week)
    change = _num(res.data.get("change_1d"))
    if change is not None:
        out["dex_volume_change_24h_pct"] = round(change, 2)

    protocols = res.data.get("protocols")
    if isinstance(protocols, list) and protocols:
        top = sorted(protocols, key=lambda p: _num(p.get("total24h")) or 0, reverse=True)
        out["top_dexes"] = [
            {
                "name": p.get("name", "unknown"),
                "volume_24h_usd": round(_num(p.get("total24h")) or 0),
            }
            for p in top[:8] if isinstance(p, dict)
        ]
    return out
