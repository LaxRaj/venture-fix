# Phase 1: audit of the vstress model layer

Scope: `vstress/questions.py`, `mapping.py`, `client.py`, `calibrate.py`, `data.py`, plus `reverse_report.txt` s.7 and s.10. Only `python3 run.py calibrate --provider stub` was run. No .env was read, no external API was called, and `vstress/` was not edited.

## Verdict

Drop the model layer as a screening component. Repurpose the 15-question bank as a human discovery-call script. It adds nothing to finding ventures that make money beyond what the arithmetic already does.

## 1. Can model answers raise a verdict, or only veto?

They can only veto.

- `mapping.gated_verdict` computes `hard = verdict(row).hard`, moves the input bands, and recomputes `soft = model_verdict(...)`. It then returns `combine(hard, soft)`.
- `combine` returns `hard` whenever `SEVERITY[hard] >= SEVERITY[model]`, with severity REACHABLE 0, BURNS 1, DEAD 2. A better soft verdict is discarded and a worse one is kept.
- Report s.7 shows this on DOT compliance. The best possible answers move the bands to REACHABLE on arithmetic, and the result is still DEAD.
- So the layer is a one-way ratchet toward DEAD. It adds false negatives and can never rescue a venture.
- The multipliers are also unvalidated. They are hand-set (0.70 to 1.40, plus 4.0 for `visit`, 2.0 for `event` and 12.0 for `phone` on `access_channel`).
- There is a sign inconsistency in `questions.py` versus `mapping.py`. Questions that map to `service_hours` give their highest score to answers that raise hours. Examples are `workflow_system:paper` (score 1.3, multiplier 1.30) and `pain_recurrence:constant`. Raising hours worsens the arithmetic, while the score treats the answer as favourable. Calibration direction and the mapping direction therefore disagree.
- `buyer_geography` has a MULTIPLIERS entry but `maps_to=""`, so it is dead code. `buyer_role` and `access_proof` are diagnostic-only.

## 2. Does calibration show anything?

No. Report s.10 holds, and I checked it against `data.py`.

- `LABELLED` is generated from latent levels with a fixed rule: `alive = (2*supply + workflow + pain >= 5) and (buyer + access >= 2) and moat > 0.15`. The evidence text is rendered from the same levels (`_evidence`). So the "survivors" are the question family the label rule weights double (supply).
- The three questions in each family read the same level, so their AUCs are identical by construction. That is one latent variable counted three times.
- Each question has four substantive options but each evidence block has only three phrases, so one option can never be correct.
- The "data or workflow moat" gate has 0 questions. The moat is independent noise in the generator.
- n=43 is about 21 per half. In the stub (random) run, `supply_switching` reached discovery AUC 0.792 with permutation p=0.018, so one random question cleared two gates. Only BH and holdout blocked it. At this n, a pass is weak evidence.
- Nothing here touches real ventures, real outcomes or real money. The "labels" are synthetic and self-referential.

## 3. Which questions could become a human discovery-call set?

The bank's design is sound for humans: single hop, no arithmetic, no dates, enumerable options plus an escape hatch. The questions are not diagnostic of profit in the model layer, but several probe real constraints that the arithmetic takes as inputs.

Keep as call questions, because each answer can be checked against a buyer's own statement:

- `supply_current`, `supply_alternative`, `supply_switching`. Together they tell you what the buyer pays today and what must be displaced. They bear on the price input, which report s.4 and s.5 show is the least anchored number.
- `buyer_list_source`. Whether a ready list exists bears on cost to reach.
- `access_channel` and `access_gatekeeper`. They bear on conversion and CAC, and `DEFAULT_CONVERSION` is used for 13 of 14 rows.
- `pain_handler`, `workflow_system`, `workflow_handoff`. These bear on service hours (capacity).

Drop or rewrite:

- `buyer_role`, `buyer_geography`, `access_proof`, `pain_recurrence`, `pain_error_caught` are weak as questions and carry no arithmetic input. Keep them only if a buyer can answer them in a sentence.

What to change when turning it into a call script:

- Replace multiple choice with the buyer's own number where a number exists. Ask what they pay now, hours per week spent, and who they would buy from. That measures the inputs directly instead of nudging them by +/-30%.
- Log answers to the arithmetic as observed values with provenance, not as multipliers.

## 4. Recommendation

- **Model-in-the-loop screening: drop.** It cannot raise a verdict, its direction is inconsistent, and its only validation is circular. It also costs API spend.
- **Question bank: repurpose** as a cheap, human-answered discovery-call set. Treat the answers as evidence that replaces estimated inputs (price, service hours, buyers, conversion) with measured ones.
- **`calibrate.py` machinery (AUC, permutation test, BH, holdout): keep.** It is correct and its stub test shows it rejects noise. Use it on real data, not on `data.py`.

## 5. What a real calibration would need

- **Real labels.** Each venture needs an observed outcome tied to profit. Candidates are "reached $X MRR within N months with one person", "paying customers acquired", or "shut down at capacity or reach". Labels must not be produced by a rule that also generates the evidence.
- **Independent evidence.** The answers should come from the buyer or from public records, not from text generated by the label process.
- **Sample size.** For one question to reach AUC 0.70 with 80% power, I estimate roughly 60 to 100 labelled ventures, with at least 25 per class. Testing 15 questions with BH correction at q=0.05, and holding out half, pushes this to about 150 to 300 labelled ventures. This is my own rough power estimate, not computed in the repo. The 43 synthetic ventures are far short, and the deduplicated bank is really 5 questions, so the correction burden is 5, not 15.
- **Cheaper alternative.** Before any calibration, run 20 to 30 real discovery calls and check how often the arithmetic's price, hours and conversion inputs are wrong. That tests the actual weak point and needs no model.
