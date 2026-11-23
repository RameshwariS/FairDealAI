# Steps to finish and submit (deadline: 30 Nov 2026, 11:59 PM IST)

Registration and Round 1 submission close at the same time. Only the **team leader** can submit.

## Day 1: get it running (about 30 min)

1. Unzip and open a terminal in the folder.
   ```bash
   cd fairdeal
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Check everything works on the stand-in data.
   ```bash
   python -m pytest tests -q          # expect 21 passed
   python demo.py                     # three sample negotiations
   ```
3. Register the team on techfest.org and note the **Team ID**.

## Day 1–2: plug in the official starter kit (about 1–2 hours)

4. Download the kit (`ps2-selling-to-machines 1.zip`) from the link in the problem statement and unzip it next to this folder.
5. Copy the kit's data over the stand-ins.
   ```bash
   cp ../ps2-selling-to-machines/store.csv ../ps2-selling-to-machines/policy.json data/
   ```
6. Open the kit's `harness.py` and `evaluate.py` and check three things:
   - **Column names** in store.csv. If any aren't recognised, add them to `COLUMN_ALIASES` in `seller/catalog.py`.
   - **How margin is defined.** If `(price − cost) / price`, use `SellerAgent(margin_basis="price")`; if `(price − cost) / cost`, use `margin_basis="cost"`. The default `"strict"` is always safe but gives away a little margin.
   - **What the seller interface looks like** (class name, method names, message keys). Write the small wrapper shown in `INTEGRATION.md`.
7. Run the official harness and scorer against the three kit bots, then save the output.
   ```bash
   python ../ps2-selling-to-machines/evaluate.py  > outputs/official_eval.txt   # adjust to the kit's actual command
   ```
8. Re-run our own checks on the real data.
   ```bash
   python -m pytest tests -q
   python benchmark.py
   python -m harness.redteam
   python -m harness.replay
   python -m harness.ablation         # takes a few minutes
   python -m harness.perf
   ```
   If anything fails, the message says which product or rule. Send it to me and I'll fix it.

## Day 2–3: test against LLM buyers (the final evaluation uses them)

9. Install Ollama and pull a model.
   ```bash
   ollama pull llama3.1:8b
   export LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.1:8b
   python -m harness.llm_buyer --n 30 --out outputs/llm_run.jsonl
   python -m harness.evaluate outputs/llm_run.jsonl > outputs/llm_eval.txt
   ```
10. **Tune to the official scoring.** Open the kit's `evaluate.py` and find how it combines deal rate, margin, deadlocks and violations. Write that as a formula, then search for the best settings:
    ```bash
    python tune.py --objective "deal_rate * margin_kept - 2 * deadlock_rate"          # your formula here
    python tune.py --buyers llm persona --n 20 --seeds 1 --objective "..."           # include LLM buyers (slow)
    python tune.py --objective "..." --apply                                         # save the winner to data/params.json
    ```
    Or score with their script directly: `--score-cmd "python ../ps2-selling-to-machines/evaluate.py --log {log}"` (it uses the last number the script prints; adjust to how their script takes input). After `--apply`, re-run step 8.
11. Read a few of the logs (`outputs/llm_run.jsonl`), or add them to the replay page. Look for:
    - **Messages the parser misread:** wrong product, or a price that wasn't found. Fix by adding keys to `PRICE_KEYS` / `ITEM_KEYS` in `seller/parsing.py`, or turn on `llm_parse=extractor()`.
    - **Buyers that walk too early.** Try `Params(boulware=1.2)` or `Params(end_x=0.0)` in `benchmark.py` and compare `deal_rate_x_margin_kept`.

## Day 3–4: write-up

12. Open the submission doc (the AgentX Round 1 Submission doc). Replace the bracketed note in the **Abstract** with the official `evaluate.py` numbers. It's 479 words now, so the official numbers get about 20 words. Paste it into a word counter before exporting.
13. Build the designed PDFs. Open `docs/build_pdfs.py` and edit `OFFICIAL_LINE` (the note under the results table) and `REPO_URL`. Then run:
    ```bash
    pip install playwright && playwright install chromium
    python docs/build_pdfs.py          # outputs/pdf/Abstract.pdf, Architecture_note.pdf, FairDeal_Round1.pdf
    ```
    Every number is pulled from `outputs/`, so run this after step 8 and the PDFs pick up the new results.

## Day 4–5: video (3 minutes)

14. Two animated clips are ready in `outputs/video/`: `opener.mp4` (the first 14 seconds: logo, three blocked tricks, the promise) and `replay_clip.mp4` (a 12-second replay of a real run, for the middle). Both have sound effects; the `_silent` versions don't. The replay runs the agent live, so after switching to the official kit re-run `python docs/video/make_replay_clip.py` (set `SKU` at the top to one of the kit's products). The opener needs no changes.
    Then follow the timed script in the submission doc. You'll need three windows:
    - a terminal running `python demo.py --pause 1.5`
    - `outputs/replay.html` open in a browser (filter to "manipulator" to show tricks being caught)
    - `outputs/REDTEAM.md` and `outputs/RESULTS.md`
15. Record at 1080p with a large terminal font (18 pt or more). OBS Studio or SimpleScreenRecorder both work on Linux. Export as `Demo_video.mp4`.

## Day 5–6: publish and submit

16. Push the code to a **public** GitHub repo.
    ```bash
    git init && git add . && git commit -m "FairDeal AI: AgentX Challenge 2 seller agent"
    git branch -M main
    git remote add origin https://github.com/<your-username>/fairdeal.git
    git push -u origin main
    ```
    Then replace `<your-username>` in the badge line at the top of `README.md`, and push again. Check the **Actions** tab shows a green tick (it runs the tests, red-team and benchmark on every push).
17. Optional: check the Docker image builds (`docker build -t fairdeal . && docker run -p 8080:8080 fairdeal`, then `curl localhost:8080/health`). I couldn't run Docker where I built this, so it's worth one check.
18. Make one Google Drive folder with:
    - `Abstract.pdf`
    - `Architecture_note.pdf`
    - `Demo_video.mp4`
    - `Code_repository.txt` (the GitHub link)
    - `outputs/`: `official_eval.txt`, `fairdeal_run.jsonl`, `results.json`, `RESULTS.md`, `REDTEAM.md`, `ABLATION.md`, `PERF.md`, `TUNING.md`, `replay.html`, and `llm_eval.txt` if you ran it
19. Set the folder to **Anyone with the link can view**. Open the link in a private window to check it works.
20. The team leader pastes the folder link into the **Submission Link** field on techfest.org. Do this a day early, not at 11:50 PM.

## If you get to the finals (16–18 Dec, IIT Bombay)

- Have `python demo.py --interactive` ready so the jury can play the buyer and try to trick it live.
- Bring `outputs/replay.html` (it works offline) for the walkthrough.
- Prepare answers on: why not let the LLM decide prices; how margin vs. deal rate is tuned (`Params`); cost per negotiation (about 0.15 ms per turn, no model calls); what happens with a buyer you've never seen (words never move price, so new tricks can't pay off).

## Changing the name later

The name only appears in text. Search and replace "FairDeal AI" / "fairdeal" in the `.md` files, `benchmark.py`, `harness/run.py` and `harness/replay.py`, then re-run `python benchmark.py`.
