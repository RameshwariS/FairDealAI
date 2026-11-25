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
   python -m pytest tests -q          # expect 23 passed
   python demo.py                     # three sample negotiations
   ```
3. Register the team on techfest.org and note the **Team ID**.

## Starter kit: done

The kit is in `ps2-selling-to-machines/` and `fairdeal_seller.py` plugs the agent into it. To re-check:
```bash
cd ps2-selling-to-machines
python evaluate.py --seller ../fairdeal_seller.py          # official score (53.0 on the default run)
cd .. && python docs/official_results.py                    # all seeds -> outputs/OFFICIAL.md, official_run.jsonl
```

## Turn on Rezolve Labs TraceWare (required: at least one Rezolve Labs capability)

```bash
export REZOLVE_API_KEY=...          # from your Rezolve Labs account (credit coupon)
export REZOLVE_MERCHANT_ID=...      # shown under "Your account" in the TraceWare docs
export TRACEWARE_LOG=../outputs/traceware_log.jsonl
cd ps2-selling-to-machines && python evaluate.py --seller ../fairdeal_seller.py --n 30 --workers 8
```
Check `outputs/traceware_log.jsonl`: every line should have a `decision` (PASS/WARN/...) and no `error`. Keep that log in the submission as evidence; the score must not drop.

## Day 2–3: test against LLM buyers (the final evaluation uses them)

9. Install Ollama and pull a model.
   ```bash
   ollama pull llama3.2:latest
   export LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.2:latest LLM_TIMEOUT=300
   cd ps2-selling-to-machines
   python evaluate.py --seller ../fairdeal_seller.py --buyers ../kit_llm_buyers.py --n 30 --workers 4 \
       --log ../outputs/llm_run.jsonl | tee ../outputs/llm_eval.txt
   ```
10. **Tune to the official scoring.** Open the kit's `evaluate.py` and find how it combines deal rate, margin, deadlocks and violations. Write that as a formula, then search for the best settings:
    ```bash
    python tune.py --objective "deal_rate * margin_kept - 2 * deadlock_rate"          # your formula here
    python tune.py --buyers llm persona --n 20 --seeds 1 --objective "deal_rate * margin_kept - 2 * deadlock_rate"  # include LLM buyers (slow)
    python tune.py --objective "deal_rate * margin_kept - 2 * deadlock_rate" --apply                          # save winner to data/params.json
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

14. Two animated clips are ready in `outputs/video/`: `opener.mp4` (the first 14 seconds) and `replay_clip.mp4` (a replay of a real run, for the middle). Both have sound effects; the `_silent` versions don't. The replay picks its product from the loaded store automatically, so re-run `python docs/video/make_replay_clip.py` whenever the data changes. For the live demo, `python -m harness.showcase` prints the seven lines to type for the current store, with the replies they get.
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
