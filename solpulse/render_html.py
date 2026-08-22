"""Interactive HTML dashboard.

Self-contained by design: SVG is generated here and the only script is a few
lines of vanilla JS for the hover layer. No CDN, no chart library, no build
step — the file opens straight from disk, which is also what keeps the
"no external dependencies" promise honest at the presentation layer.

Colours come from a palette validated for colour-vision deficiency against both
surfaces; series identity is always carried by a legend and direct labels as
well as by hue, and status is always icon + label + colour, never colour alone.
"""

import html
import json
from datetime import datetime, timezone

CSS = """
*,*::before,*::after{box-sizing:border-box}
.viz-root{
  color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --raised:#222221;
  --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
}
:root[data-theme="light"] .viz-root{
  color-scheme:light;
  --page:#f9f9f7; --surface:#fcfcfb; --raised:#f2f2ef;
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834;
}
body{margin:0;background:var(--page);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 64px}
a{color:var(--s1)}
h1{font-size:1.5rem;font-weight:650;margin:0;letter-spacing:-.01em}
h2{font-size:1.02rem;font-weight:620;margin:0 0 14px;letter-spacing:-.005em}
.sub{color:var(--muted);font-size:.82rem;margin-top:4px}
header.top{display:flex;justify-content:space-between;align-items:flex-start;
  gap:16px;flex-wrap:wrap;margin-bottom:22px}
button.theme{background:var(--raised);color:var(--ink-2);border:1px solid var(--ring);
  border-radius:7px;padding:7px 13px;font:inherit;font-size:.8rem;cursor:pointer}
button.theme:hover{color:var(--ink)}
button.theme:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:11px;
  padding:18px 20px;margin-bottom:16px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:1px;
  background:var(--surface);border:1px solid var(--ring);border-radius:11px;
  overflow:hidden;margin-bottom:16px}
.tile{background:var(--surface);padding:15px 17px;box-shadow:0 0 0 1px var(--ring)}
.tile .k{font-size:.68rem;letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted);margin-bottom:7px}
.tile .v{font-size:1.6rem;font-weight:640;letter-spacing:-.02em;line-height:1.1}
.tile .u{font-size:.8rem;color:var(--ink-2);font-weight:400;margin-left:3px}
.tile .d{font-size:.75rem;color:var(--ink-2);margin-top:5px}
.tile .delta{font-size:.72rem;color:var(--muted);margin-top:5px;
  font-variant-numeric:tabular-nums}
.tile .delta b{font-weight:600;color:var(--ink-2)}
.meter{height:4px;background:var(--grid);border-radius:2px;margin-top:8px;
  overflow:hidden}
.meter i{display:block;height:100%;background:var(--s1);border-radius:2px}
.strip{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:16px}
.pill{display:inline-flex;align-items:center;gap:6px;background:var(--surface);
  border:1px solid var(--ring);border-radius:999px;padding:5px 12px;font-size:.79rem;
  color:var(--ink-2)}
.dot{width:8px;height:8px;border-radius:50%;flex:none}
.an{display:flex;gap:11px;padding:11px 0;border-bottom:1px solid var(--grid)}
.an:last-child{border-bottom:none;padding-bottom:0}
.an .ico{flex:none;width:19px;height:19px;border-radius:50%;display:grid;
  place-items:center;font-size:11px;font-weight:700;color:#fff;margin-top:1px}
.an .body{flex:1;min-width:0}
.an .lbl{font-size:.67rem;letter-spacing:.08em;text-transform:uppercase;
  font-weight:700;margin-bottom:2px}
.an .msg{font-size:.88rem;color:var(--ink-2)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:.8rem;
  color:var(--ink-2)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.swatch{width:11px;height:3px;border-radius:2px;flex:none}
.chart{position:relative;overflow-x:auto}
svg{display:block;max-width:100%;height:auto}
.tip{position:absolute;pointer-events:none;opacity:0;transition:opacity .1s;
  background:var(--raised);border:1px solid var(--ring);border-radius:8px;
  padding:8px 11px;font-size:.79rem;white-space:nowrap;z-index:5;
  box-shadow:0 6px 20px rgba(0,0,0,.35)}
.tip .tk{color:var(--muted);font-size:.72rem;margin-bottom:4px}
.tip .tr{display:flex;align-items:center;gap:7px;
  font-variant-numeric:tabular-nums}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--grid)}
th{font-size:.67rem;letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted);font-weight:650}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:last-child td{border-bottom:none}
details{margin-top:12px}
summary{cursor:pointer;font-size:.79rem;color:var(--muted)}
summary:focus-visible{outline:2px solid var(--s1);outline-offset:3px}
footer{color:var(--muted);font-size:.78rem;margin-top:28px;
  border-top:1px solid var(--grid);padding-top:16px}
.na{color:var(--muted);font-style:italic;font-size:.9rem}
"""

JS = """
document.querySelectorAll('[data-chart]').forEach(function(box){
  var svg=box.querySelector('svg'), tip=box.querySelector('.tip');
  if(!svg||!tip) return;
  var pts=JSON.parse(svg.dataset.points||'[]'), cross=svg.querySelector('.crosshair');
  if(!pts.length) return;
  function move(ev){
    var r=svg.getBoundingClientRect(), vb=svg.viewBox.baseVal;
    var x=(ev.clientX-r.left)/r.width*vb.width;
    var best=null,bd=1e9;
    pts.forEach(function(p){var d=Math.abs(p.x-x); if(d<bd){bd=d;best=p;}});
    if(!best) return;
    if(cross){cross.setAttribute('x1',best.x);cross.setAttribute('x2',best.x);
      cross.style.opacity=1;}
    tip.innerHTML=best.html;
    tip.style.opacity=1;
    var px=best.x/vb.width*r.width;
    tip.style.left=Math.min(Math.max(px-tip.offsetWidth/2,0),r.width-tip.offsetWidth)+'px';
    tip.style.top='4px';
  }
  svg.addEventListener('mousemove',move);
  svg.addEventListener('mouseleave',function(){
    tip.style.opacity=0; if(cross) cross.style.opacity=0;});
});
document.querySelectorAll('[data-bar]').forEach(function(box){
  var tip=box.querySelector('.tip');
  box.querySelectorAll('[data-tip]').forEach(function(el){
    el.addEventListener('mouseenter',function(ev){
      tip.innerHTML=el.dataset.tip; tip.style.opacity=1;
      var r=box.getBoundingClientRect();
      tip.style.left=Math.min(ev.clientX-r.left+12,r.width-tip.offsetWidth-4)+'px';
      tip.style.top=(ev.clientY-r.top-8)+'px';
    });
    el.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });
});
var btn=document.getElementById('themeBtn');
if(btn) btn.addEventListener('click',function(){
  var cur=document.documentElement.getAttribute('data-theme');
  document.documentElement.setAttribute('data-theme',cur==='light'?'dark':'light');
});
"""

SEV_COLOR = {"critical": "var(--critical)", "warning": "var(--warning)",
             "serious": "var(--serious)", "info": "var(--s1)"}
SEV_GLYPH = {"critical": "!", "warning": "!", "serious": "!", "info": "i"}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fmt_exact(value) -> str:
    """Full number with separators, never abbreviated.

    Slots, block heights and epochs are identifiers, not magnitudes: rendering
    slot 298459000 as "298.46M" discards the digits that make it useful.
    """
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}"
    return esc(value)


def fmt(value, unit: str = "", decimals: int = 0) -> str:
    """Human-readable number with magnitude suffix."""
    if value is None:
        return "—"
    if not isinstance(value, (int, float)):
        return esc(value)
    absolute = abs(value)
    if unit == "$":
        if absolute >= 1e9:
            return f"${value / 1e9:.2f}B"
        if absolute >= 1e6:
            return f"${value / 1e6:.1f}M"
        if absolute >= 1e3:
            return f"${value / 1e3:.1f}K"
        return f"${value:,.2f}"
    if absolute >= 1e9:
        return f"{value / 1e9:.2f}B"
    if absolute >= 1e6:
        return f"{value / 1e6:.2f}M"
    return f"{value:,.{decimals}f}"


def _tile(key: str, value: str, unit: str = "", detail: str = "",
          delta=None, extra: str = "") -> str:
    """One metric tile.

    `delta` is percent movement since the previous run. It is rendered in
    neutral ink with a direction glyph rather than green/red: for most of these
    metrics "up" is not inherently good, and colouring them would assert a
    judgement the data does not support.
    """
    unit_html = f'<span class="u">{esc(unit)}</span>' if unit else ""
    detail_html = f'<div class="d">{detail}</div>' if detail else ""
    delta_html = ""
    if isinstance(delta, (int, float)) and abs(delta) >= 0.1:
        glyph = "▲" if delta > 0 else "▼"
        delta_html = (f'<div class="delta">{glyph} <b>{abs(delta):.1f}%</b>'
                      f' vs last run</div>')
    return (f'<div class="tile"><div class="k">{esc(key)}</div>'
            f'<div class="v">{value}{unit_html}</div>{detail_html}'
            f'{extra}{delta_html}</div>')


def _line_chart(series: list, width: int = 1080, height: int = 260) -> str:
    """Multi-series line chart with a shared hover crosshair.

    `series` is a list of {label, color_var, values}. Values are aligned by
    index; None gaps break the path rather than interpolating across missing
    data, which would invent readings that were never taken.
    """
    live = [s for s in series if any(v is not None for v in s["values"])]
    if not live:
        return '<p class="na">No time-series data available.</p>'

    pad_l, pad_r, pad_t, pad_b = 52, 14, 14, 26
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    count = max(len(s["values"]) for s in live)
    if count < 2:
        return '<p class="na">Not enough samples yet to plot a trend.</p>'

    everything = [v for s in live for v in s["values"] if v is not None]
    lo, hi = min(everything), max(everything)
    if hi == lo:
        hi = lo + 1
    span = hi - lo
    lo -= span * 0.12
    hi += span * 0.12

    def sx(i):
        return pad_l + i / (count - 1) * plot_w

    def sy(v):
        return pad_t + (1 - (v - lo) / (hi - lo)) * plot_h

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Throughput over the last hour">']

    # Recessive gridlines and axis ticks.
    for step in range(5):
        value = lo + (hi - lo) * step / 4
        y = sy(value)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" '
                     f'y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 9}" y="{y + 4:.1f}" text-anchor="end" '
                     f'font-size="11" fill="var(--muted)" '
                     f'style="font-variant-numeric:tabular-nums">{fmt(value)}</text>')

    parts.append(f'<line class="crosshair" x1="0" y1="{pad_t}" x2="0" '
                 f'y2="{pad_t + plot_h}" stroke="var(--muted)" stroke-width="1" '
                 f'stroke-dasharray="3 3" style="opacity:0"/>')

    for s in live:
        segments, current = [], []
        for i, v in enumerate(s["values"]):
            if v is None:
                if len(current) > 1:
                    segments.append(current)
                current = []
            else:
                current.append(f"{sx(i):.1f},{sy(v):.1f}")
        if len(current) > 1:
            segments.append(current)
        for segment in segments:
            parts.append(f'<polyline points="{" ".join(segment)}" fill="none" '
                         f'stroke="{s["color"]}" stroke-width="2" '
                         f'stroke-linejoin="round" stroke-linecap="round"/>')
        # Direct label at the series end — identity never rests on hue alone.
        last = next((i for i in range(len(s["values"]) - 1, -1, -1)
                     if s["values"][i] is not None), None)
        if last is not None:
            parts.append(f'<circle cx="{sx(last):.1f}" cy="{sy(s["values"][last]):.1f}" '
                         f'r="4" fill="{s["color"]}" stroke="var(--surface)" '
                         f'stroke-width="2"/>')

    parts.append(f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{width - pad_r}" '
                 f'y2="{pad_t + plot_h}" stroke="var(--axis)" stroke-width="1"/>')
    parts.append(f'<text x="{pad_l}" y="{height - 6}" font-size="11" '
                 f'fill="var(--muted)">1 hour ago</text>')
    parts.append(f'<text x="{width - pad_r}" y="{height - 6}" text-anchor="end" '
                 f'font-size="11" fill="var(--muted)">now</text>')

    points = []
    for i in range(count):
        rows = []
        for s in live:
            v = s["values"][i] if i < len(s["values"]) else None
            if v is None:
                continue
            rows.append(
                f'<div class="tr"><span class="swatch" style="background:{s["color"]}">'
                f'</span>{esc(s["label"])}: <strong>{fmt(v, decimals=1)}</strong></div>')
        points.append({
            "x": round(sx(i), 1),
            "html": f'<div class="tk">sample {i + 1} of {count}</div>' + "".join(rows),
        })

    parts.append("</svg>")
    svg = parts[0].replace(
        "<svg ", f'<svg data-points="{esc(json.dumps(points))}" ', 1) + "".join(parts[1:])
    return svg


def _bar_chart(rows: list, value_key: str, label_key: str,
               unit: str = "", width: int = 520) -> str:
    """Horizontal bars, one series, sorted descending.

    Bars carry 4px rounded ends on the value side and sit on a shared baseline;
    a 2px surface gap separates neighbours so adjacent fills never merge.
    """
    if not rows:
        return '<p class="na">No data available.</p>'

    bar_h, gap, label_w = 26, 8, 128
    height = len(rows) * (bar_h + gap) + 8
    plot_w = width - label_w - 74
    top = max((r.get(value_key) or 0) for r in rows) or 1

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Ranked comparison">']
    for i, row in enumerate(rows):
        value = row.get(value_key) or 0
        y = i * (bar_h + gap) + 4
        w = max(value / top * plot_w, 2)
        label = str(row.get(label_key, ""))
        shown = label if len(label) <= 17 else label[:16] + "…"
        tip = (f'<div class="tk">{esc(label)}</div><div class="tr">'
               f'<strong>{fmt(value, unit, 0)}</strong></div>')
        parts.append(
            f'<text x="0" y="{y + bar_h / 2 + 4:.0f}" font-size="12.5" '
            f'fill="var(--ink-2)">{esc(shown)}</text>')
        parts.append(
            f'<rect data-tip="{esc(tip)}" x="{label_w}" y="{y}" width="{w:.1f}" '
            f'height="{bar_h - 2}" rx="4" fill="var(--s1)" style="cursor:pointer"/>')
        parts.append(
            f'<text x="{label_w + w + 9:.1f}" y="{y + bar_h / 2 + 4:.0f}" '
            f'font-size="12" fill="var(--ink-2)" '
            f'style="font-variant-numeric:tabular-nums">{fmt(value, unit, 0)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def render(report: dict) -> str:
    m = report["metrics"]
    d = report.get("deltas") or {}
    anomalies = report["anomalies"]
    sources = report["sources"]
    generated = report["generated_at"]

    tiles = [
        _tile("Throughput", fmt(m.get("tps"), decimals=0), "TPS",
              f'non-vote {fmt(m.get("tps_non_vote"), decimals=0)}'
              if m.get("tps_non_vote") else "", delta=d.get("tps")),
        _tile("Slot time", fmt(m.get("slot_time_ms")), "ms", "target 400ms",
              delta=d.get("slot_time_ms")),
        _tile("Epoch", fmt_exact(m.get("epoch")), "",
              f'{m.get("epoch_progress_pct", "—")}% complete'
              + (f' · ~{m["epoch_eta_hours"]}h left'
                 if m.get("epoch_eta_hours") is not None else ""),
              extra=(f'<div class="meter"><i style="width:'
                     f'{min(max(m["epoch_progress_pct"], 0), 100)}%"></i></div>'
                     if isinstance(m.get("epoch_progress_pct"), (int, float)) else "")),
        _tile("SOL price", fmt(m.get("sol_price_usd"), "$"), "",
              (f'{m["sol_change_24h_pct"]:+.2f}% 24h'
               if m.get("sol_change_24h_pct") is not None else ""),
              delta=d.get("sol_price_usd")),
        _tile("TVL", fmt(m.get("tvl_usd"), "$"), "",
              f'rank #{m["tvl_rank"]} of all chains' if m.get("tvl_rank") else "",
              delta=d.get("tvl_usd")),
        _tile("DEX volume", fmt(m.get("dex_volume_24h_usd"), "$"), "", "24 hours",
              delta=d.get("dex_volume_24h_usd")),
        _tile("Validators", fmt(m.get("validators_active")), "",
              f'{m.get("validators_delinquent", 0)} delinquent',
              delta=d.get("validators_active")),
        _tile("Nakamoto", fmt(m.get("nakamoto_coefficient")), "",
              "to halt finality", delta=d.get("nakamoto_coefficient")),
        _tile("Stablecoins", fmt(m.get("stablecoin_supply_usd"), "$"), "", "on Solana",
              delta=d.get("stablecoin_supply_usd")),
        _tile("Circulating", fmt(m.get("supply_circulating_sol")), "SOL",
              f'{m.get("supply_circulating_pct", "—")}% of total'),
    ]

    health_ok = m.get("health") == "ok"
    strip = [
        f'<span class="pill"><span class="dot" style="background:'
        f'{"var(--good)" if health_ok else "var(--critical)"}"></span>'
        f'Network {esc(m.get("health") or "unknown")}</span>',
        f'<span class="pill"><span class="dot" style="background:'
        f'{"var(--good)" if sources["healthy"] == sources["total"] else "var(--warning)"}'
        f'"></span>{sources["healthy"]}/{sources["total"]} sources responded</span>',
    ]
    if anomalies["count"]:
        colour = "var(--critical)" if anomalies["critical"] else "var(--warning)"
        strip.append(f'<span class="pill"><span class="dot" style="background:{colour}">'
                     f'</span>{anomalies["count"]} anomalies detected</span>')
    else:
        strip.append('<span class="pill"><span class="dot" style="background:'
                     'var(--good)"></span>No anomalies</span>')

    if anomalies["anomalies"]:
        items = []
        for a in anomalies["anomalies"]:
            sev = a["severity"]
            items.append(
                f'<div class="an"><div class="ico" style="background:{SEV_COLOR[sev]}">'
                f'{SEV_GLYPH[sev]}</div><div class="body">'
                f'<div class="lbl" style="color:{SEV_COLOR[sev]}">{esc(sev)}</div>'
                f'<div class="msg">{esc(a["message"])}</div></div></div>')
        if anomalies.get("correlation"):
            items.append(f'<div class="an"><div class="ico" style="background:'
                         f'var(--serious)">!</div><div class="body">'
                         f'<div class="lbl" style="color:var(--serious)">correlated</div>'
                         f'<div class="msg">{esc(anomalies["correlation"])}</div>'
                         f'</div></div>')
        anomaly_card = f'<div class="card"><h2>Anomalies</h2>{"".join(items)}</div>'
    else:
        note = ("Baseline still building — statistical detection activates after "
                f'{5 - anomalies["baseline_snapshots"]} more run(s).'
                if not anomalies["baseline_ready"]
                else "All tracked metrics are within their recent baselines.")
        anomaly_card = (f'<div class="card"><h2>Anomalies</h2>'
                        f'<p class="msg" style="color:var(--ink-2);margin:0">'
                        f'{esc(note)}</p></div>')

    tps_series = m.get("tps_series") or []
    line = _line_chart([
        {"label": "Total TPS", "color": "var(--s1)",
         "values": [s.get("tps") for s in tps_series]},
        {"label": "Non-vote TPS", "color": "var(--s2)",
         "values": [s.get("tps_non_vote") for s in tps_series]},
    ])

    validators = m.get("top_validators") or []
    dexes = m.get("top_dexes") or []

    validator_rows = "".join(
        f'<tr><td>{esc(v["identity"])}</td>'
        f'<td class="n">{fmt(v["stake_sol"])}</td>'
        f'<td class="n">{v["stake_pct"]}%</td>'
        f'<td class="n">{v["commission"]}%</td></tr>' for v in validators)

    return f"""<!doctype html>
<html lang="en" data-theme="dark"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SolPulse — Solana Ecosystem Report</title>
<style>{CSS}</style></head>
<body class="viz-root"><div class="wrap">

<header class="top">
  <div>
    <h1>SolPulse</h1>
    <div class="sub">Solana ecosystem state · generated {esc(generated)} ·
      auto-refreshing report</div>
  </div>
  <button class="theme" id="themeBtn" type="button">Toggle theme</button>
</header>

<div class="strip">{"".join(strip)}</div>
<div class="tiles">{"".join(tiles)}</div>

{anomaly_card}

<div class="card">
  <h2>Throughput, last hour</h2>
  <div class="legend">
    <span><span class="swatch" style="background:var(--s1)"></span>Total TPS</span>
    <span><span class="swatch" style="background:var(--s2)"></span>Non-vote TPS</span>
  </div>
  <div class="chart" data-chart><div class="tip"></div>{line}</div>
  <details><summary>View as table</summary>
    <table><thead><tr><th>Sample</th><th class="n">Total TPS</th>
      <th class="n">Non-vote TPS</th></tr></thead><tbody>
      {"".join(f'<tr><td>{i + 1}</td><td class="n">{fmt(s.get("tps"), decimals=1)}</td>'
               f'<td class="n">{fmt(s.get("tps_non_vote"), decimals=1)}</td></tr>'
               for i, s in enumerate(tps_series))}
    </tbody></table></details>
</div>

<div class="grid2">
  <div class="card">
    <h2>Top validators by stake</h2>
    <div class="chart" data-bar><div class="tip"></div>
      {_bar_chart(validators, "stake_sol", "identity")}</div>
    <details><summary>View as table</summary>
      <table><thead><tr><th>Identity</th><th class="n">Stake (SOL)</th>
        <th class="n">Share</th><th class="n">Fee</th></tr></thead>
        <tbody>{validator_rows}</tbody></table></details>
  </div>
  <div class="card">
    <h2>Top DEXes by 24h volume</h2>
    <div class="chart" data-bar><div class="tip"></div>
      {_bar_chart(dexes, "volume_24h_usd", "name", "$")}</div>
  </div>
</div>

<footer>
  <strong>Sources.</strong> Solana JSON-RPC (network, validators, supply) ·
  DeFiLlama (price, TVL, stablecoins, DEX volume) · CoinGecko (price fallback,
  market cap). No API keys are used.<br>
  <strong>Method.</strong> Anomalies combine absolute rules with a median/MAD
  modified z-score over this deployment's own snapshot history. Epoch ETA assumes
  the 400ms target slot time. Colours are validated for colour-vision deficiency
  against both surfaces.
</footer>

</div><script>{JS}</script></body></html>"""
