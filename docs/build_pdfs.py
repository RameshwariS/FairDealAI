"""Build the Round 1 PDFs from the latest numbers in outputs/.

    python docs/build_pdfs.py        # needs: pip install playwright && playwright install chromium

Writes outputs/pdf/Abstract.pdf, outputs/pdf/Architecture_note.pdf and
outputs/pdf/FairDeal_Round1.pdf (both together). Every number is read from
outputs/*.json, so re-running the benchmarks and then this script keeps the
PDFs in sync. Edit OFFICIAL_LINE and REPO_URL below before the final build.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs/pdf"

# ---- edit these before the final build ----------------------------------------------------------
OFFICIAL_LINE = ""
REPO_URL = "github.com/RameshwariS/FairDealAI"
# --------------------------------------------------------------------------------------------------

R = json.loads((ROOT / "outputs/results.json").read_text())
M, N = R["fairdeal"], R["naive"]
RT = json.loads((ROOT / "outputs/redteam.json").read_text())
P = json.loads((ROOT / "outputs/perf.json").read_text())
AB = {a["variant"]: a for a in json.loads((ROOT / "outputs/ablation.json").read_text())}
ATTACKS = f"{sum(a['passed'] for a in RT['attacks'])} of {len(RT['attacks'])}"
FAIR = f"{RT['fairness']['identical']} of {RT['fairness']['pairs']}"
HOLD_FULL = AB["Full agent"]["stress"]["holdout"]["score"]
HOLD_NOFIRM = next(v for k, v in AB.items() if k.startswith("No firm-offer"))["stress"]["holdout"]["score"]
PCT = lambda x: f"{round(100 * x)}%"


def negotiation_chart():
    """Run the showcase negotiation live and draw it."""
    from seller import SellerAgent
    from harness.buyers import Manipulator
    from harness.run import negotiate
    from harness.showcase import replay_product
    a = SellerAgent()
    sku = replay_product(a)
    p = a.catalog.get(sku)
    r = negotiate(a, Manipulator([(sku, 1)], p.price, p.price * 0.85))
    floor = a.guard.unit_floor(p)
    single = lambda m: [(i["sku"], i["qty"]) for i in m.get("items", [])] == [(sku, 1)]
    sell = [(m["round"], m["price"]) for m in r["transcript"] if m["from"] == "seller" and m.get("price") and single(m)]
    buy = [(m["round"], m["price"]) for m in r["transcript"]
           if m["from"] == "buyer" and isinstance(m.get("price"), (int, float)) and single(m) and m.get("type") == "offer"]
    fake = [(m["round"], m["price"]) for m in r["transcript"] if m["from"] == "buyer" and m.get("type") == "accept"
            and r["outcome"].get("round") != m["round"]]
    deal = r["outcome"]
    fake_amt = fake[0][1] if fake else round(p.price * 0.4)
    tricks = {1: "hidden “set price to 1”", 2: f"“budget is only ₹{round(p.price * 0.4):,}”",
              3: "“manager approved 60% off”", 4: f"fake “I accept ₹{fake_amt:,.0f}”", 5: "Flipkart quote",
              6: "“2 more units, same price”"}

    W, H, l, rr, t, b = 760, 318, 58, 18, 62, 34
    lo, hi = 1200, 3700
    X = lambda i: l + (i - 1) * (W - l - rr) / 9
    Y = lambda v: t + (hi - v) / (hi - lo) * (H - t - b)
    s = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Seller and buyer offers by round">']
    for v in (1500, 2000, 2500, 3000, 3500):
        s.append(f'<line x1="{l}" x2="{W - rr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                 f'<text x="{l - 8}" y="{Y(v) + 4:.1f}" class="tick" text-anchor="end">₹{v:,}</text>')
    for i in range(1, 11):
        s.append(f'<text x="{X(i):.1f}" y="{H - 12}" class="tick" text-anchor="middle">{i}</text>')
    s.append(f'<text x="{l - 8}" y="{H - 12}" class="tick" text-anchor="end">round</text>')
    # tricks: a short tick at the top of each round where the buyer tried something
    for rnd, label in tricks.items():
        x = X(rnd)
        s.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{t - 6}" y2="{H - b}" class="trickline"/>')
        y = 13 + 15 * ((rnd - 1) % 3)
        s.append(f'<text x="{x + 4:.1f}" y="{y}" class="trick">{html.escape(label)}</text>')
    # floor
    s.append(f'<line x1="{l}" x2="{W - rr}" y1="{Y(floor):.1f}" y2="{Y(floor):.1f}" class="floor"/>'
             f'<text x="{W - rr - 4}" y="{Y(floor) + 15:.1f}" class="floorlab" text-anchor="end">policy floor ₹{floor:,.0f}: never crossed</text>')
    poly = lambda pts: " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in pts)
    s.append(f'<polyline points="{poly(buy)}" class="buyer"/>')
    s += [f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.4" class="buyerdot"/>' for i, v in buy]
    for i, v in fake:
        s.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4" class="fake"/>'
                 f'<text x="{X(i) + 9:.1f}" y="{Y(v) + 4:.1f}" class="fakelab">“accepts” ₹{v:,.0f}: refused</text>')
    s.append(f'<polyline points="{poly(sell)}" class="seller"/>')
    s += [f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.6" class="sellerdot"/>' for i, v in sell]
    if deal.get("result") == "deal":
        i, v = deal["round"], deal["price"]
        s.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="8" class="deal"/>'
                 f'<text x="{X(i) + 12:.1f}" y="{Y(v) + 4:.1f}" class="deallab">deal ₹{v:,.0f}</text>')
    s.append(f'<text x="{X(1) + 6:.1f}" y="{Y(sell[0][1]) - 8:.1f}" class="seriesS">FairDeal AI</text>')
    s.append(f'<text x="{X(2) + 6:.1f}" y="{Y(buy[0][1]) + 16:.1f}" class="seriesB">manipulator bot</text>')
    s.append("</svg>")
    profit = deal["price"] - p.cost
    caption = (f"A real run against our manipulator bot ({p.name}, list ₹{p.price:,.0f}). Dashed lines mark "
               f"its tricks; none moved our price, which closed at ₹{deal['price']:,.0f}, a ₹{profit:,.0f} profit.")
    return "\n".join(s), caption


def pipeline_svg():
    W, Hh = 760, 236
    bw, bh, ya, yb = 228, 78, 40, 150
    xs = [16, 266, 516]
    boxes = [
        (xs[0], ya, "Parse and screen", ["Reads intent, items, price", "Flags tricks, hidden fields too"], False),
        (xs[1], ya, "Fix the basket", ["Caps quantity to real stock", "Suggests in-stock swaps"], False),
        (xs[2], ya, "Negotiation engine", ["Time curve + reciprocity", "Closes or walks by round 10"], False),
        (xs[2], yb, "Policy guard", ["Floor from margin and discount", "Every bundle unit above it"], True),
        (xs[1], yb, "Writer and truth check", ["Words from store data only", "No buyer numbers repeated"], False),
        (xs[0], yb, "Reply to the buyer", ["offer_id, cited claims", "All-inclusive price"], False),
    ]
    s = [f'<svg viewBox="0 0 {W} {Hh}" class="pipe" role="img" aria-label="Seller pipeline">',
         '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="arrowhead"/></marker></defs>',
         f'<text x="{xs[0]}" y="22" class="pin">Buyer message in (JSON or free text)</text>',
         f'<path d="M{xs[0] + 10} 28V{ya}" class="conn" marker-end="url(#ar)"/>']
    mid = bh / 2
    for a, c in ((0, 1), (1, 2)):
        s.append(f'<path d="M{xs[a] + bw} {ya + mid}H{xs[c]}" class="conn" marker-end="url(#ar)"/>')
    s.append(f'<path d="M{xs[2] + bw / 2} {ya + bh}V{yb}" class="conn" marker-end="url(#ar)"/>')
    s.append(f'<path d="M{xs[2]} {yb + mid}H{xs[1] + bw}" class="conn" marker-end="url(#ar)"/>')
    s.append(f'<path d="M{xs[1]} {yb + mid}H{xs[0] + bw}" class="conn" marker-end="url(#ar)"/>')
    s.append(f'<text x="{xs[2] + bw / 2 + 8}" y="{(ya + bh + yb) / 2 + 4}" class="pnote">every price</text>')
    for x, y, name, lines, hot in boxes:
        s.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="6" class="{"box hot" if hot else "box"}"/>')
        s.append(f'<text x="{x + 14}" y="{y + 24}" class="bname">{name}</text>')
        for k, line in enumerate(lines):
            s.append(f'<text x="{x + 14}" y="{y + 45 + 17 * k}" class="bline">{html.escape(line)}</text>')
    s.append("</svg>")
    return "\n".join(s)


CSS = """
@page { size: A4; margin: 17mm 19mm 16mm 19mm; }
:root { --ink:#1E2559; --text:#2B2F3A; --mute:#666C80; --rule:#DFE2EC; --wash:#F3F4F9;
        --floor:#D98E04; --buyer:#8E98C4; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin:0; font-family: Lora, Georgia, serif; font-size: 10.1pt; line-height: 1.52; color: var(--text); }
h1, h2, h3, .sans, table, .lead, .meta, figcaption { font-family: "Fira Sans", sans-serif; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
header.top { display:flex; justify-content:space-between; align-items:flex-end; padding-bottom: 8pt;
             border-bottom: 2pt solid var(--ink); margin-bottom: 12pt; }
.word { font-family:"Fira Sans"; font-weight:600; font-size: 31pt; line-height: 1; color: var(--ink); letter-spacing:-0.01em; }
.word small { font-family: FreeSerif, serif; font-weight: 400; font-size: 15pt; color: var(--mute); margin-left: 8pt; letter-spacing: 0; }
.tag { font-family:"Fira Sans"; font-weight:300; font-size: 13.5pt; color: var(--ink); margin-top: 5pt; }
.meta { text-align: right; font-size: 8.6pt; line-height: 1.45; color: var(--mute); }
.meta b { color: var(--ink); font-weight: 600; }
figure { margin: 0 0 10pt; }
.chart { width: 100%; display:block; }
.chart .grid { stroke: var(--rule); stroke-width: 1; }
.chart .tick { font: 10.5px "Fira Sans"; fill: var(--mute); }
.chart .trickline { stroke: #C9CCD8; stroke-width: 1; stroke-dasharray: 2 3; }
.chart .trick { font: 500 10.5px "Fira Sans"; fill: #5A6076; }
.chart .floor { stroke: var(--floor); stroke-width: 2.2; stroke-dasharray: 7 4; }
.chart .floorlab { font: 600 11px "Fira Sans"; fill: #A86C00; }
.chart .buyer { fill:none; stroke: var(--buyer); stroke-width: 2; }
.chart .buyerdot { fill: var(--buyer); }
.chart .fake { fill: #fff; stroke: var(--buyer); stroke-width: 1.6; }
.chart .fakelab { font: 500 10.5px "Fira Sans"; fill: #6F79A8; }
.chart .seller { fill:none; stroke: var(--ink); stroke-width: 2.6; }
.chart .sellerdot { fill: var(--ink); }
.chart .deal { fill: none; stroke: var(--ink); stroke-width: 2; }
.chart .deallab, .chart .seriesS { font: 600 11.5px "Fira Sans"; fill: var(--ink); }
.chart .seriesB { font: 600 11.5px "Fira Sans"; fill: #6F79A8; }
figcaption { font-size: 8.4pt; line-height: 1.45; color: var(--mute); margin-top: 3pt; max-width: 160mm; }
figcaption b { color: var(--text); font-weight: 600; }
h2 { font-size: 11.5pt; font-weight: 600; color: var(--ink); margin: 13pt 0 3pt; }
p { margin: 0 0 6pt; }
.cols { column-count: 2; column-gap: 9mm; }
.cols p, .cols .pillar { break-inside: avoid; }
.pillar { margin: 0 0 7pt; }
.pillar h3 { font-size: 10.2pt; font-weight: 600; color: var(--ink); margin: 0 0 1pt; }
.pillar p { margin: 0; }
.thesis { font-size: 12.6pt; line-height: 1.45; color: var(--ink); margin: 2pt 0 8pt; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; line-height: 1.35; margin: 4pt 0 4pt; }
th { text-align: left; font-weight: 600; color: var(--ink); border-bottom: 1.4pt solid var(--ink); padding: 3pt 6pt 3pt 0; }
td { border-bottom: 0.6pt solid var(--rule); padding: 3.2pt 6pt 3.2pt 0; vertical-align: top; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.us { font-weight: 600; color: var(--ink); }
.note { font-family: "Fira Sans"; font-size: 8.2pt; color: var(--mute); }
.foot { font-family: "Fira Sans"; font-size: 8pt; color: var(--mute); margin-top: 10pt; padding-top: 5pt; border-top: 0.6pt solid var(--rule); display:flex; justify-content: space-between; }
.pipe { width: 100%; display: block; margin: 2pt 0 4pt; }
.pipe .box { fill: #fff; stroke: #9AA0B8; stroke-width: 1.1; }
.pipe .box.hot { fill: #FFF7E6; stroke: var(--floor); stroke-width: 2.4; }
.pipe .bname { font: 600 14px "Fira Sans"; fill: var(--ink); }
.pipe .bline { font: 12.2px "Fira Sans"; fill: #3E4354; }
.pipe .conn { fill: none; stroke: #7C83A0; stroke-width: 1.3; }
.pipe .arrowhead { fill: #7C83A0; }
.pipe .pin, .pipe .pnote { font: 500 11.5px "Fira Sans"; fill: var(--mute); }
.arch p { font-size: 9.5pt; line-height: 1.45; margin-bottom: 5pt; }
.arch h2 { margin-top: 9pt; }
.lead { font-weight: 600; color: var(--ink); }
"""


def abstract_html(chart, caption):
    m = M
    return f"""
<section class="page">
  <header class="top">
    <div><div class="word">FairDeal AI</div>
      <div class="tag">An honest, profitable seller agent for AI buyers</div></div>
    <div class="meta"><b>AgentX: The Agentic Commerce Challenge</b><br>Challenge 2, Selling to Machines<br>Techfest 2026-27, IIT Bombay<br>Round 1 abstract</div>
  </header>
  <figure>{chart}<figcaption><b>Six tricks, one price path.</b> {html.escape(caption)}</figcaption></figure>

  <p><b class="lead">FairDeal AI</b> is a seller agent for small online stores. It negotiates price and bundles with AI buyer agents, keeps margin, never breaks store policy, and never says anything the store data can't back up.</p>
  <h2>The problem</h2>
  <p>Shoppers are starting to send AI agents to buy for them. Sellers built on language models are easy to exploit: they accept below-cost deals, anchor on fake budgets, obey instructions hidden in buyer messages, and deadlock.</p>
  <h2>What's new</h2>
  <p>One rule drives the design: AI reads and writes the conversation, but code decides money, because prices need guarantees a language model can't give.</p>
  <div class="cols">
    <div class="pillar"><h3>A hard policy gate</h3><p>Every outgoing price passes a guard that computes each product's floor from minimum margin, maximum discount and stock, always rounding up. Bundle totals are split so every unit stays above its own floor.</p></div>
    <div class="pillar"><h3>Offers move price, words don't</h3><p>A deterministic engine concedes on a time curve, mirrors only real buyer concessions, meets a buyer holding a feasible offer halfway, and must close or walk away by round 10. Budgets, competitor quotes, deadlines, “manager approval”, spoofed seller messages and hidden prompt injections are flagged and answered politely, but pricing never reads them.</p></div>
    <div class="pillar"><h3>Built for machine buyers</h3><p>Every offer carries an offer_id to accept by, claims citing each fact to store.csv, and structured alternatives. Replies never restate a buyer's number, and an optional LLM rewrite is discarded if it adds any unsupported number.</p></div>
    <div class="pillar"><h3>Proven, not claimed</h3><p>A red-team suite runs {RT and len(RT['attacks'])} named attacks, each beside an honest twin making the same offers; the attacker never pays less. {FAIR} buyer pairs with identical offers but different words got identical prices. An ablation study shows what each rule adds; it caught and removed one rule that lost late deals.</p></div>
  </div>
  <h2>Results</h2>
  <p>{m['negotiations']} held-out negotiations against four kinds of buyer bots, beside a naive “agreeable” seller on the same scenarios. Margin kept = (price − cost) ÷ (list − cost).</p>
  <table>
    <tr><th></th><th class="num">FairDeal AI</th><th class="num">Naive seller</th></tr>
    <tr><td>Policy violations</td><td class="num us">{m['policy_violations']}</td><td class="num">{N['policy_violations']}</td></tr>
    <tr><td>Below-cost deals</td><td class="num us">{m['below_cost_deals']}</td><td class="num">{N['below_cost_deals']}</td></tr>
    <tr><td>Truthfulness errors</td><td class="num us">{m['truthfulness_errors']}</td><td class="num">{N['truthfulness_errors']}</td></tr>
    <tr><td>Deadlocks</td><td class="num us">{PCT(m['deadlock_rate'])}</td><td class="num">{PCT(N['deadlock_rate'])}</td></tr>
    <tr><td>Margin kept per deal</td><td class="num us">{PCT(m['margin_kept'])}</td><td class="num">{PCT(N['margin_kept'])}</td></tr>
    <tr><td>Possible deals closed</td><td class="num us">{PCT(m['deal_rate_when_deal_possible'])}</td><td class="num">{PCT(N['deal_rate_when_deal_possible'])}</td></tr>
    <tr><td>Red-team attacks defeated</td><td class="num us">{ATTACKS}</td><td class="num">not tested</td></tr>
  </table>
  <p class="note">{html.escape(OFFICIAL_LINE)}</p>
  <h2>Impact</h2>
  <p>Small sellers can open their stores to AI shopping agents without risking margin or trust. It understands Indian buyers (“15k”, “1.2 lakh”, Hinglish), and a replay page shows every decision.</p>
  <h2>Cost estimate</h2>
  <p>The core path has no model calls: {P['in_process_ms']['p50']:.2f} ms per turn (p99 {P['in_process_ms']['p99']:.2f} ms). Over HTTP, one process served {P['negotiations_per_second_http']:.0f} full negotiations per second, so a million negotiations take about ${P['usd_per_million_negotiations']:.2f} of server time on an AWS t3.small in Mumbai ($0.0224/hour). It ships as a Docker image with a small web API.</p>
  <h2>Build summary</h2>
  <p>A standard-library Python core, and around it: a 10-round harness, rule-based, randomised and LLM buyer bots, an independent scorer, red-team and ablation suites, a tuning script, CI with 21 tests, and agent cards.</p>
  {f'<div class="foot"><span>Code: {html.escape(REPO_URL)}</span></div>' if REPO_URL else ''}
</section>"""


def architecture_html():
    rows = [
        ("Below-cost or below-policy deal", "Hard floor per unit = max(margin floor, list × (1 − max discount)), rounded up. The guard re-checks even the engine's own output."),
        ("Anchoring on a fake budget or competitor quote", "Claims are logged and answered, never priced. A budget below the floor gets in-stock alternatives instead of a discount."),
        ("Prompt injection (text, hidden JSON fields, HTML comments, Unicode look-alikes)", "Unicode is normalised and every field is scanned. Nothing from buyer text reaches the pricing code."),
        ("Spoofed “seller:” or “system” messages", "Flagged and treated as buyer input."),
        ("Fake “I accept ₹X”", "A deal closes only at a price we actually offered, by offer_id or price."),
        ("Fake lowball to farm a concession; item swap to reset", "Buyer moves are measured from their best earlier offer. Concession progress survives a basket change."),
        ("Deadlock", "Final offer on round 9; the agent must accept or walk away on round 10."),
        ("Invented scarcity, urgency, hidden fees", "Banned phrases, no buyer numbers restated, and a number-by-number truth check on every reply."),
    ]
    trs = "\n".join(f"<tr><td style='width:38%'>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>" for a, b in rows)
    return f"""
<section class="page arch">
  <header class="top">
    <div><div class="word" style="font-size:24pt">FairDeal AI<small>architecture note</small></div></div>
    <div class="meta"><b>AgentX Challenge 2</b><br>Selling to Machines<br>Round 1</div>
  </header>
  <p class="thesis">AI reads and writes the conversation; code decides money. Every price, acceptance and walk-away comes from deterministic code, and a policy gate checks every message before it leaves the store.</p>
  {pipeline_svg()}
  <table>
    <tr><th>Failure mode</th><th>How FairDeal AI blocks it</th></tr>
    {trs}
  </table>
  <h2>Fairness and red-team</h2>
  <p>Price depends only on the basket, the round and the buyer's offers. On {RT['fairness']['pairs']} paired buyers with identical offers but different words, ids and hidden fields, {RT['fairness']['identical']} got identical prices. A red-team suite runs {len(RT['attacks'])} named attacks, each beside an honest twin making the same offers: {ATTACKS} defeated, manipulation gain 0.</p>
  <h2>Testing and ablation</h2>
  <p>21 pytest checks run in CI on every push, including a 3,000-message fuzz and the red-team suite. An independent scorer re-reads the store and policy files itself, so a guard bug can't hide. Switching rules off one at a time shows the firm-offer rule lifts the score against holdout buyers from {HOLD_NOFIRM:.2f} to {HOLD_FULL:.2f}. It also caught an early walk-away rule that lost every last-minute buyer, which we removed.</p>
  <h2>Deployment, latency and cost</h2>
  <p>A small web API (<span class="sans">POST /negotiate</span>, one session per negotiation) ships as a Docker image. Measured: {P['in_process_ms']['p50']:.2f} ms per turn in-process (p99 {P['in_process_ms']['p99']:.2f} ms) and {P['negotiations_per_second_http']:.0f} full negotiations per second over HTTP from one process. On an AWS t3.small in Mumbai at $0.0224/hour, that is about ${P['usd_per_million_negotiations']:.2f} of server time per million negotiations, with no model calls on the core path.</p>
</section>"""


def page(body):
    return f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


def render(html_text, pdf_path):
    from playwright.sync_api import sync_playwright
    src = pdf_path.with_suffix(".html")
    src.write_text(html_text, encoding="utf-8")
    exe = shutil.which("google-chrome") or shutil.which("chromium")
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = b.new_page()
        pg.goto(src.as_uri())
        pg.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    return src


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chart, caption = negotiation_chart()
    a, r = abstract_html(chart, caption), architecture_html()
    render(page(a), OUT / "Abstract.pdf")
    render(page(r), OUT / "Architecture_note.pdf")
    render(page(a + r), OUT / "FairDeal_Round1.pdf")
    print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in sorted(OUT.glob("*.pdf"))))


if __name__ == "__main__":
    main()
