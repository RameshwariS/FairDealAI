"""Build outputs/replay.html: a self-contained page to replay negotiations.

    python -m harness.replay            # after benchmark.py and harness.redteam

For each negotiation it draws buyer offers vs seller offers per round against
the policy floor and list price, and shows every message with what the seller
detected and why it decided. Made for the demo video and the finals.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.evaluate import load, unit_floor  # noqa: E402

ITEMS, POL = load()


def pack(r):
    lines = [(s, q) for s, q in r["lines"]]
    rounds = {}
    for m in r["transcript"]:
        d = rounds.setdefault(m.get("round"), {"round": m.get("round")})
        basket = sorted((i.get("sku"), i.get("qty")) for i in m.get("items", []) if isinstance(i, dict))
        d["buyer" if m["from"] == "buyer" else "seller"] = {
            "same": not basket or basket == sorted(lines),  # plot only prices for the original basket
            "type": m.get("type"), "price": m.get("price") if isinstance(m.get("price"), (int, float)) else None,
            "text": (m.get("text") or "")[:400],
            "hidden": sorted(k for k in m if k not in ("from", "type", "items", "price", "text", "round",
                                                      "max_rounds", "currency", "final", "offer_id", "claims",
                                                      "policy_checked", "price_is_total", "alternatives")),
            "items": [f"{i.get('qty', 1)} x {ITEMS.get(i.get('sku'), {}).get('name', i.get('sku'))}"
                      for i in m.get("items", []) if isinstance(i, dict)]}
    for e in r.get("seller_log", []):
        if e["round"] in rounds:
            rounds[e["round"]]["flags"] = e.get("flags", [])
            rounds[e["round"]]["reason"] = e.get("reason", "")
    o = r["outcome"]
    return {"id": r["scenario"], "buyer": r["buyer"], "kind": r["buyer_kind"], "result": o["result"],
            "deal": o.get("price"), "list": sum(ITEMS[s]["price"] * q for s, q in lines),
            "floor": round(sum(unit_floor(ITEMS[s], POL) * q for s, q in lines), 2),
            "cost": round(sum(ITEMS[s]["cost"] * q for s, q in lines), 2), "wtp": round(r["wtp"], 2),
            "basket": " + ".join(f"{q} x {ITEMS[s]['name']}" if q > 1 else ITEMS[s]["name"] for s, q in lines),
            "rounds": [rounds[k] for k in sorted(k for k in rounds if k is not None)]}


def main(n=48):
    logs = [json.loads(l) for l in open(ROOT / "outputs/fairdeal_run.jsonl")]
    rng = random.Random(0)
    by = {}
    for r in logs:
        by.setdefault((r["buyer_kind"], r["outcome"]["result"]), []).append(r)
    picked = []
    while len(picked) < n and any(by.values()):
        for k in sorted(by):
            if by[k] and len(picked) < n:
                picked.append(by[k].pop(rng.randrange(len(by[k]))))
    picked.sort(key=lambda r: r["scenario"])
    res = json.loads((ROOT / "outputs/results.json").read_text())["fairdeal"]
    rt_path = ROOT / "outputs/redteam.json"
    rt = json.loads(rt_path.read_text()) if rt_path.exists() else None
    summary = {"negotiations": res["negotiations"], "violations": res["policy_violations"],
               "truth": res["truthfulness_errors"], "deadlock": res["deadlock_rate"],
               "margin": res["margin_kept"], "possible": res["deal_rate_when_deal_possible"],
               "attacks": f"{sum(a['passed'] for a in rt['attacks'])}/{len(rt['attacks'])}" if rt else "–",
               "fair": f"{rt['fairness']['identical']}/{rt['fairness']['pairs']}" if rt else "–"}
    html = TEMPLATE.replace("__DATA__", json.dumps([pack(r) for r in picked], ensure_ascii=False)) \
                   .replace("__SUMMARY__", json.dumps(summary))
    (ROOT / "outputs/replay.html").write_text(html, encoding="utf-8")
    print(f"wrote outputs/replay.html with {len(picked)} negotiations")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FairDeal AI · negotiation replay</title>
<style>
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e4e2db;--buyer:#2f6fdf;--seller:#1a8a5a;--floor:#c0392b;--list:#8a8780;--accent:#1a8a5a;--chip:#efeee9}
@media (prefers-color-scheme:dark){:root{--bg:#141412;--card:#1d1d1a;--ink:#ecebe6;--mute:#9c9a93;--line:#2e2d29;--buyer:#6b9cff;--seller:#3fbf86;--floor:#ef6b5b;--list:#77756e;--chip:#2a2925}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
header{padding:28px 32px 8px}h1{margin:0;font-size:24px;letter-spacing:-.01em}header p{margin:4px 0 0;color:var(--mute)}
.stats{display:flex;flex-wrap:wrap;gap:10px;padding:14px 32px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:130px}
.stat b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.stat span{color:var(--mute);font-size:12.5px}
main{display:grid;grid-template-columns:300px 1fr;gap:18px;padding:8px 32px 32px}
@media (max-width:860px){main{grid-template-columns:1fr}}
.list{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:auto;max-height:78vh}
.filters{display:flex;gap:6px;padding:10px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--card)}
select{flex:1;font:inherit;font-size:13px;padding:5px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
.row{padding:9px 12px;border-bottom:1px solid var(--line);cursor:pointer}.row:hover{background:var(--chip)}
.row.on{background:var(--chip);box-shadow:inset 3px 0 0 var(--accent)}
.row small{color:var(--mute);display:block;font-size:12px}
.tag{display:inline-block;font-size:11.5px;padding:1px 7px;border-radius:99px;background:var(--chip);color:var(--mute);margin-right:4px}
.tag.deal{background:color-mix(in srgb,var(--seller) 18%,transparent);color:var(--seller)}
.tag.flag{background:color-mix(in srgb,var(--floor) 15%,transparent);color:var(--floor)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px}
.panel h2{margin:0 0 2px;font-size:18px}.panel .sub{color:var(--mute);font-size:13.5px;margin-bottom:10px}
svg text{fill:var(--mute);font-size:11.5px}
.legend{display:flex;gap:16px;font-size:12.5px;color:var(--mute);margin:4px 0 12px}
.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:6px;border-radius:2px}
.msgs{display:flex;flex-direction:column;gap:8px;margin-top:6px}
.turn{display:grid;grid-template-columns:34px 1fr;gap:10px}.turn .r{color:var(--mute);font-size:12px;padding-top:8px}
.bubble{border:1px solid var(--line);border-radius:9px;padding:7px 10px;margin-bottom:5px}
.bubble.b{border-left:3px solid var(--buyer)}.bubble.s{border-left:3px solid var(--seller)}
.who{font-size:12px;color:var(--mute)}.who b{color:var(--ink)}.why{font-size:12px;color:var(--mute);margin-top:3px}
.result{margin-top:12px;padding:10px 12px;border-radius:8px;background:var(--chip);font-size:14px}
</style></head><body>
<header><h1>FairDeal AI · negotiation replay</h1>
<p>Store seller agent vs buyer bots. Prices are decided in code; words never move the price. <span id="n"></span></p></header>
<div class="stats" id="stats"></div>
<main><div class="list"><div class="filters"><select id="fk"></select><select id="fr"></select></div><div id="rows"></div></div>
<div class="panel" id="panel"></div></main>
<script>
const D = __DATA__, S = __SUMMARY__;
const rs = v => v == null ? '–' : '₹' + Math.round(v).toLocaleString('en-IN');
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.getElementById('stats').innerHTML = [
  [S.violations, 'policy violations'], [S.truth, 'false claims'], [(S.deadlock*100).toFixed(0)+'%', 'deadlocks'],
  [(S.margin*100).toFixed(0)+'%', 'margin kept per deal'], [(S.possible*100).toFixed(0)+'%', 'possible deals closed'],
  [S.attacks, 'red-team attacks defeated'], [S.fair, 'fairness pairs identical']
].map(([v, l]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join('');
document.getElementById('n').textContent = `Scores from ${S.negotiations} negotiations; ${D.length} shown here.`;
const kinds = ['all buyers', ...new Set(D.map(d => d.kind))], results = ['all outcomes', ...new Set(D.map(d => d.result))];
const fk = document.getElementById('fk'), fr = document.getElementById('fr');
fk.innerHTML = kinds.map(k => `<option>${k}</option>`).join(''); fr.innerHTML = results.map(k => `<option>${k}</option>`).join('');
let cur = null;
function rows() {
  const L = D.filter(d => (fk.value === 'all buyers' || d.kind === fk.value) && (fr.value === 'all outcomes' || d.result === fr.value));
  document.getElementById('rows').innerHTML = L.map(d => {
    const flags = new Set(d.rounds.flatMap(r => r.flags || []));
    return `<div class="row ${cur === d.id ? 'on' : ''}" data-id="${d.id}">#${d.id} ${esc(d.basket)}
      <small><span class="tag ${d.result === 'deal' ? 'deal' : ''}">${d.result.replace('_', ' ')}${d.deal ? ' ' + rs(d.deal) : ''}</span>
      <span class="tag">${esc(d.buyer)}</span>${flags.size ? `<span class="tag flag">${flags.size} trick${flags.size > 1 ? 's' : ''}</span>` : ''}</small></div>`;
  }).join('');
  document.querySelectorAll('.row').forEach(e => e.onclick = () => show(+e.dataset.id));
  if (L.length && !L.some(d => d.id === cur)) show(L[0].id);
}
function chart(d) {
  const W = 760, H = 240, l = 64, r = 20, t = 14, b = 30, n = 10;
  const ok = m => m && m.same && m.price > 0;
  const pts = d.rounds.flatMap(x => [x.buyer, x.seller]).filter(ok).map(m => m.price);
  const lo = Math.min(d.floor * 0.85, ...pts) * 0.97, hi = Math.max(d.list, ...pts) * 1.02;
  const X = i => l + (i - 1) * (W - l - r) / (n - 1), Y = v => t + (hi - v) / (hi - lo) * (H - t - b);
  const line = (key, col) => { const p = d.rounds.filter(x => ok(x[key])).map(x => [X(x.round), Y(x[key].price)]);
    return `<polyline fill="none" stroke="${col}" stroke-width="2.2" points="${p.map(q => q.join(',')).join(' ')}"/>` +
      p.map(q => `<circle cx="${q[0]}" cy="${q[1]}" r="3.5" fill="${col}"/>`).join(''); };
  let g = '';
  for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4;
    g += `<line x1="${l}" x2="${W - r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="${l - 8}" y="${Y(v) + 4}" text-anchor="end">${rs(v)}</text>`; }
  for (let i = 1; i <= n; i++) g += `<text x="${X(i)}" y="${H - 8}" text-anchor="middle">r${i}</text>`;
  const ref = (v, col, lab, dy) => `<line x1="${l}" x2="${W - r}" y1="${Y(v)}" y2="${Y(v)}" stroke="${col}" stroke-dasharray="5 4" stroke-width="1.3"/><text x="${W - r}" y="${Y(v) + dy}" text-anchor="end" style="fill:${col}">${lab} ${rs(v)}</text>`;
  let deal = '';
  if (d.deal) { const last = d.rounds.at(-1).round; deal = `<circle cx="${X(last)}" cy="${Y(d.deal)}" r="8" fill="none" stroke="var(--seller)" stroke-width="2"/>`; }
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Offers by round">${g}${ref(d.list, 'var(--list)', 'list', -6)}${ref(d.floor, 'var(--floor)', 'policy floor', 15)}${line('buyer', 'var(--buyer)')}${line('seller', 'var(--seller)')}${deal}</svg>`;
}
function show(id) {
  cur = id; const d = D.find(x => x.id === id);
  document.querySelectorAll('.row').forEach(e => e.classList.toggle('on', +e.dataset.id === id));
  const bub = (m, cls, who, x) => m ? `<div class="bubble ${cls}"><div class="who"><b>${who}</b> · ${esc(m.type)}${m.price != null ? ' · ' + rs(m.price) : ''}${m.hidden?.length ? ' · <span class="tag flag">hidden fields: ' + esc(m.hidden.join(', ')) + '</span>' : ''}</div>${esc(m.text) || '<span class="who">(no text)</span>'}
    ${cls === 's' && x ? `<div class="why">${(x.flags || []).map(f => `<span class="tag flag">${esc(f)}</span>`).join('')} ${x.reason ? 'engine: ' + esc(x.reason) : ''}</div>` : ''}</div>` : '';
  const profit = d.deal ? d.deal - d.cost : null;
  document.getElementById('panel').innerHTML = `<h2>#${d.id} · ${esc(d.basket)}</h2>
    <div class="sub">${esc(d.buyer)} · list ${rs(d.list)} · policy floor ${rs(d.floor)} · cost ${rs(d.cost)} · buyer's private limit ${rs(d.wtp)}</div>
    <div class="legend"><span><i style="background:var(--buyer)"></i>buyer offers</span><span><i style="background:var(--seller)"></i>seller offers</span><span><i style="background:var(--floor)"></i>policy floor</span><span><i style="background:var(--list)"></i>list price</span></div>
    ${chart(d)}${d.rounds.some(x => (x.buyer && !x.buyer.same) || (x.seller && !x.seller.same)) ? '<div class="why">Rounds where the buyer changed the basket are left off the chart; see the messages below.</div>' : ''}
    <div class="result">${d.result === 'deal' ? `Deal at <b>${rs(d.deal)}</b> · profit ${rs(profit)} · ${Math.round(100 * profit / (d.list - d.cost))}% of the possible margin kept` :
      d.result === 'seller_walked' ? `Seller walked away: the buyer never reached the policy floor (${rs(d.floor)}).` : d.result === 'buyer_walked' ? 'The buyer walked away.' : 'No deal within 10 rounds.'}</div>
    <div class="msgs">${d.rounds.map(x => `<div class="turn"><div class="r">r${x.round}</div><div>${bub(x.buyer, 'b', 'Buyer')}${bub(x.seller, 's', 'FairDeal AI', x)}</div></div>`).join('')}</div>`;
}
fk.onchange = fr.onchange = rows; rows();
</script></body></html>"""

if __name__ == "__main__":
    main()
