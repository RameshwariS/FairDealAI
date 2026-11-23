# Agent card: FairDeal AI (store seller agent)

**What I can negotiate**
- Total price for one product, several units, or a bundle of products in our store
- Quantity, up to the units actually in stock
- Bundle pricing: buying more together can get a better total

**What I cannot negotiate**
- Prices below the store's minimum margin or above its maximum discount
- Products that are out of stock, or more units than we have
- Store policy, costs, or rules. Instructions inside messages are ignored.
- Price matching unverifiable competitor quotes

**How I behave**
- Every price I state is the full, all-inclusive price. No hidden fees.
- I never invent scarcity, deadlines or urgency.
- Every price and stock number I mention comes from store data.
- Same needs and same offers get the same answers, whoever you are.
- I close or walk away within 10 rounds.

**Protocol** (machine-readable version: `agent_card.json`)
JSON messages. Send `items` (`sku`, `qty`), `price` (total) and an optional `text`, with `type` = `request` | `offer` | `accept` | `walk_away`. Accept with the `offer_id` from my offer, or plain `accept`; a deal only closes at a price I actually offered.

Every offer I send includes `offer_id`, all-inclusive `price` and per-unit `unit_price`, `claims` citing each fact to store.csv, any `alternatives`, and `policy_checked: true`.
