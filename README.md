# Venture stress test

A screening system for pre-revenue ventures that refuses to forecast revenue.
It computes what each venture **requires**, checks that requirement against a
physical limit, and names the value of every input at which the verdict flips.
A judgment model may move an input band. It may never produce an output.

```bash
python3 run.py screen                    # the board, with break-evens
python3 run.py brief                     # per-venture verdict and what flips it
python3 run.py field                     # the shopping list
python3 run.py field --venture NAME      # what to measure, and the call script
python3 run.py calibrate --provider stub # prove the harness
python3 run.py calibrate --provider jev  # needs TYPESAFE_API_KEY
python3 run.py ingest --file FILE.json   # replace invented values with measured ones
cd tests && python3 -I test_arithmetic.py
```

## The arithmetic

For every row: `accounts = $10,000 MRR / price`.

| Test | Arithmetic | Fails when |
|---|---|---|
| Accounts needed | `target / price` | — |
| One person can serve them | `accounts / service hours <= 173.2 hours/month` | capacity falls below the bar |
| Enough buyers can be reached | `contacts / pool <= 50%` | you must contact most of the market |

`contacts = accounts / conversion`. The conversion default is 0.6% per contact;
the phone multiplier (12x) is isolated as a declared assumption.

Every row prints the value at which the verdict flips:

| Venture | service hrs now -> flips at | price now -> flips at |
|---|---|---|
| DOT compliance | 3.0 -> **2.60** | $150 -> **$173** |
| Prior-auth appeals | 8.5 -> 20.78 | $1,200 -> $490 |
| Veterinary claims | 4.5 -> 10.39 | $600 -> $259 |
| Insurance subrogation | 15.0 -> 60.62 | $3,500 -> $866 |

DOT is the only fragile row: a 13% move in an invented service-hours number
flips it. That is why `field` asks for 38 calls on DOT and 8 everywhere else.

## The safety property

```python
combine("DEAD ON ARITHMETIC", "REACHABLE")   == "DEAD ON ARITHMETIC"   # model cannot revive
combine("REACHABLE", "BURNS THE MARKET")     == "BURNS THE MARKET"     # model can raise
combine("REACHABLE", "garbage-from-timeout") == "REACHABLE"            # fails open
```

Hard checks fail closed and set a floor. The model fails open and may only
raise severity above it.

## Files

```
vstress/questions.py   15 typed questions + import-time admission tests
vstress/client.py      jev | generative | stub providers behind one interface
vstress/mapping.py     answers -> input bands, with floors and a confidence gate
vstress/arithmetic.py  all outputs, break-evens, sensitivity, combine()
vstress/calibrate.py   AUC, permutation test, BH control, holdout, thresholds
vstress/fieldtest.py   shopping list, sample size, call script, ingest
vstress/data.py        43 labelled ventures + 14 economics rows with provenance
tests/                 arithmetic and the floor rule
run.py                 screen | brief | field | calibrate | ingest
```

## Question bank

Fifteen questions, three each across buyer, pain, supply, workflow and access.
Each declares the one arithmetic input it may move (or `""` for diagnostic-only).
The bank is rejected at import time by four tests:

- **T1 single hop** — no inference chain, no negation
- **T2 no arithmetic** — no counting, comparing or units
- **T3 no dates** — no before/after, durations or deadlines
- **T4 enumerable** — named options plus exactly one escape hatch

Options are shuffled on every call. The module also keeps six known-bad
questions and asserts each one is rejected.

## Calibration

Three gates: discovery AUC, permutation test with Benjamini-Hochberg control,
and replication on a held-out half. With the stub provider the raw cutoff keeps
one question, the permutation test keeps it at `p=0.018`, BH control rejects
it, and the final count is zero. The harness prints that result rather than
pretending coverage. The `data or workflow moat` gate has no question and is
printed as **UNCOVERED**.

## Provenance

`screen` prints the provenance counts. Anchored prices and estimated prices are
never presented as the same kind of number. The 43 calibration labels in
`vstress/data.py` are a synthetic fixture: replace `LABELLED` with your own
hand labels before trusting any calibration result.

## Running Jev

Jev is TypeSafe's System One model, not a chat model. The provider posts one
shared state and all fifteen `choice` questions to
`https://api.typesafe.ai/v1/systemone`; the response carries one answer per
question.

```bash
cp .env.example .env
# edit .env and set TYPESAFE_API_KEY
python3 run.py calibrate --provider jev
```

`run.py` loads `.env` automatically. `JEV_MODEL` defaults to `jev-1.13.0` and
`JEV_BASE_URL` can be overridden.

The 43 labelled ventures in `vstress/data.py` are a synthetic fixture. Each
venture is generated from five latent dimensions (buyer, pain, supply,
workflow, access), and each dimension's level is rendered as a short evidence
paragraph whose wording matches the option labels. The labels use a declared
rule: `2*supply + workflow + pain >= 5` and `buyer + access >= 2`, with an
independent moat coin-flip. This gives 18 alive and 25 dead ventures with
varied, readable evidence.

On that fixture Jev keeps the three supply questions:

| question | discovery AUC | permutation p | BH | holdout AUC |
|---|---|---|---|---|
| `supply_current` | 0.875 | 0.002 | 0.010 | 0.897 |
| `supply_alternative` | 0.875 | 0.002 | 0.010 | 0.897 |
| `supply_switching` | 0.875 | 0.002 | 0.010 | 0.897 |

They survive because the label rule weights supply most heavily; the other
families are weaker by construction. This shows the calibration machinery can
find and replicate signal, not that Jev predicts real ventures. Replace
`LABELLED` with 43 real ventures and their primary evidence before treating a
Jev run as a test of the model.

## What this cannot do

- Predict whether a product can be built to the accuracy a liability-bearing
  buyer demands. That is discovered in a pilot.
- Tell you the close rate. It reports the published range and nothing narrower.
- Replace the calls. It ranks which numbers are worth a call.

## Agent fleet (web app)

```bash
python3 fleetapp.py                      # http://127.0.0.1:8780, stub models unless ANTHROPIC_API_KEY is set
python3 fleetapp.py --top 3 --auto 900   # cycle the top 3 ventures every 15 minutes
python3 -I tests/test_fleet.py
```

Each venture (seeded from `ventures_seed.json`, the 15-venture shortlist) gets a team: an **orchestrator**
(heavy model, `FLEET_ORCH_MODEL`) that plans the venture's tasks and reviews progress; **research, web
(landing), demo, code, outreach and reply** workers that start on the cheapest tier (`FLEET_TIER0..2`,
default haiku > sonnet > opus); and a **QA gate** (`fleet/qa.py`) that checks every output with deterministic
rules (price shown, no fabricated proof or guarantees, opt-out line and postal address, personalised, safe code).
Rejected output retries once with the QA feedback, then the task moves up a model tier. A model judge may add
issues in live mode; it can never waive a deterministic one.

What the agents do not do: send email, move money, or invent customers.
- Emails sit in an **approval queue**. Approving re-runs QA on the exact text, refuses unsubscribed addresses,
  and enforces a daily cap. With `FLEET_SMTP_HOST/USER/PASS` set they send; otherwise they are written to
  `runs/outbox/*.eml`.
- Revenue enters the ledger only from a signature-verified Stripe webhook (`POST /webhook/stripe`,
  `STRIPE_WEBHOOK_SECRET`) or a manual entry. The landing button uses your Stripe Payment Link tagged with
  `client_reference_id=<venture id>`.
- Prospects are imported by you (CSV `name,company,email`); the research agent supplies the search recipes.
