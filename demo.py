"""Readable live demo for the video / finals.

    python demo.py                 # three showcase negotiations
    python demo.py --interactive   # you play the buyer (type JSON or plain text)

Shows each message plus what the seller detected and why it decided, so the
judges can see the guard working.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seller import SellerAgent  # noqa: E402
from harness.buyers import CooperativeBuyer, Manipulator, PersonaBuyer  # noqa: E402

B, S, D, R, G, Y = "\033[96m", "\033[92m", "\033[90m", "\033[0m", "\033[1;32m", "\033[93m"


def show(agent, buyer, title, pause):
    print(f"\n{Y}=== {title} ==={R}")
    agent.reset()
    last = None
    for rnd in range(1, 11):
        b = {**buyer.act(rnd, last), "round": rnd, "max_rounds": 10}
        extra = {k: v for k, v in b.items() if k not in ("type", "items", "price", "text", "round", "max_rounds")}
        print(f"{B}BUYER  r{rnd} [{b.get('type')}] {b.get('price', '')}  {b.get('text', '')}{R}"
              + (f" {D}hidden fields: {extra}{R}" if extra else ""))
        if b.get("type") == "walk_away":
            print(f"{D}-> buyer walked away{R}")
            return
        s = agent.respond(b)
        log = agent.log[-1]
        print(f"{S}SELLER r{rnd} [{s['type']}] {s.get('price', '')}  {s['text']}{R}")
        print(f"{D}   detected: {log['flags'] or '-'} | engine: {log['reason']}{R}")
        last = s
        time.sleep(pause)
        if s["type"] in ("accept", "walk_away", "end"):
            if s["type"] == "accept":
                cost = sum(agent.catalog.get(i["sku"]).cost * i["qty"] for i in s["items"])
                print(f"{G}DEAL at {s['price']} | cost {cost:.0f} | profit {s['price'] - cost:.0f} | "
                      f"policy check: {agent.guard.check(agent.neg.lines, s['price']).ok}{R}")
            return


def interactive(agent):
    agent.reset()
    print("Type a JSON message or plain text, e.g.  I want the <product name>, or {\"items\":[{\"sku\":\"...\",\"qty\":1}],\"price\":...}")
    for rnd in range(1, 11):
        try:
            raw = input(f"{B}you r{rnd}> {R}")
        except (EOFError, KeyboardInterrupt):
            break
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            msg = {"text": raw}
        msg["round"] = rnd
        s = agent.respond(msg)
        log = agent.log[-1]
        price = f"₹{s['price']:,.0f}" if s.get("price") is not None else ""
        print(f"{S}seller [{s['type']}] {price}  {s['text']}{R}")
        print(f"{D}   detected: {', '.join(log['flags']) or '-'} | engine: {log['reason']}{R}")
        if s["type"] in ("accept", "walk_away", "end"):
            break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--pause", type=float, default=0.6)
    a = ap.parse_args()
    agent = SellerAgent()
    c = agent.catalog
    if a.interactive:
        interactive(agent)
    else:
        import random
        from harness.showcase import demo_product, replay_product
        p = c.get(demo_product(agent))
        show(agent, CooperativeBuyer([(p.sku, 1)], p.price, p.price * 0.9), "1. Cooperative buyer", a.pause)
        q = c.get(replay_product(agent))
        show(agent, Manipulator([(q.sku, 1)], q.price, q.price * 0.85), "2. Manipulator bot", a.pause)
        pair = sorted((x for x in c.products.values() if agent.guard.available(x) >= 1 and x.category == p.category),
                      key=lambda x: x.price)[:2]
        x, y = pair
        from harness.run import negotiate

        def bundle_buyer(seed):
            return PersonaBuyer([(x.sku, 1), (y.sku, 1)], x.price + y.price, (x.price + y.price) * 0.85,
                                random.Random(seed), catalog=c)
        # pick a seed whose run ends in a deal and uses at least one trick, so the showcase shows both
        seed = next((sd for sd in range(1, 60)
                     if negotiate(agent, bundle_buyer(sd))["outcome"]["result"] == "deal"
                     and bundle_buyer(sd).tactics), 6)
        pb = bundle_buyer(seed)
        show(agent, pb, "3. Bundle buyer (agentic-style persona)", a.pause)
