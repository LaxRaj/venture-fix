# Phase 1: arithmetic screen, corrected for a solo founder

Script: `python3 analysis/corrected_screen.py` (imports `vstress`, edits nothing). Tests: `cd tests && python3 -I test_arithmetic.py` -> 13 passed.
Baseline (173.2 h, $10k) reproduces `reverse_report.txt` section 1 exactly: DOT = DEAD; RFP, Environmental permit = BURNS; other 11 REACHABLE.

## Assumptions (declared, not measured)
- 60-80 hrs/wk = 260-345 hrs/month. Delivery share 60-75% (rest = selling, admin, support).
- Delivery capacity 150 / 190 / 230 h/month (about 260x0.6, 300x0.63, 345x0.67). The repo's 173.2 h is 40 hrs/wk of pure delivery, which a solo founder doing their own sales does not have.
- Time-to-customer ignores sales-cycle lag and churn; contacts treated as independent (geometric).

## 1. Verdict sweep (capacity x target MRR)
Bars: `$/delivery-hr >= target/capacity`; `price*buyers*conv >= 2*target`.

| Capacity | $3k needs | $5k needs | $10k needs |
|---|---|---|---|
| 150 h | $20.00/hr | $33.33/hr | $66.67/hr |
| 190 h | $15.79/hr | $26.32/hr | $52.63/hr |
| 230 h | $13.04/hr | $21.74/hr | $43.48/hr |

Only three rows ever change. The other 11 are REACHABLE in every cell.

| Row | Baseline | Flips |
|---|---|---|
| DOT compliance ($50/hr) | DEAD | DEAD only at 150h/$10k and 190h/$10k. REACHABLE in all $3k and $5k cells and 230h/$10k. |
| RFP drafting (mkt $13.5k) | BURNS | REACHABLE at $3k and $5k (all capacities). Still BURNS at $10k. Capacity-independent (reach test). |
| Environmental permit (mkt $6k) | BURNS | REACHABLE only at $3k. BURNS at $5k and $10k. |

Capacity only moves DOT. Target MRR moves the two reach rows. Capacity is not the binding constraint for 13 of 14 rows.

## 2. Time to first customer (price-independent; one account)
Weeks = 1/(contacts_wk x conv) expected; p50 / p90 from geometric.

| Conv | 20/wk exp (p50, p90) | 60/wk exp (p50, p90) | 100/wk exp (p50, p90) |
|---|---|---|---|
| 1.1% | 4.5 (3.1, 10.4) | 1.5 (1.0, 3.5) | 0.9 (0.6, 2.1) |
| 0.6% | 8.3 (5.8, 19.1) | 2.8 (1.9, 6.4) | 1.7 (1.2, 3.8) |
| 0.1% | 50 (35, 115) | 17 (11.5, 38) | 10 (6.9, 23) |
| 0.05% | 100 (69, 230) | 33 (23, 77) | 20 (14, 46) |

Weeks to $3k at 60 contacts/wk (expected; `-` = needs > 50% of pool):

| Row | accts | 1.1% | 0.6% | 0.1% | 0.05% |
|---|---|---|---|---|---|
| Insurance subrogation | 1 | 2 | 3 | 17 | - |
| RFP drafting | 2 | 3 | 6 | - | - |
| Prior-auth appeals / Medical billing | 3 | 5 | 8 | 50 | - / 100 |
| Customs HTS, Freight audit | 4 | 6 | 11 | - | - |
| Grant compliance | 4 | 6 | 11 | 67 | - |
| Veterinary | 5 | 8 | 14 | - | - |
| Utility bill audit | 6 | 9 | 17 | 100 | - |
| Trademark watch | 10 | 15 | 28 | 167 | - |
| Lien waiver / Title searches | 12 | 18 | 33 | - | - |
| DOT compliance | 20 | 30 | 56 | - | - |
| Environmental permit | 2 | 3 | - | - | - |

$5k roughly doubles these (full table in script output). Takeaways:
- Conversion dominates everything. Moving from 0.6% to 0.05% multiplies time by 12 and kills nearly every row's pool test. The screen's default 0.6% is an invented input and is the least safe one.
- High price / few accounts wins on first-dollar speed (subrogation 1 account, prior-auth 3). DOT, lien, title, which the old screen treats as fine, need 12-20 accounts: 30-56 weeks at 60 contacts/wk.
- First dollar needs one account: `1/conv` contacts is under 50% of pool for every row, so the old three tests never gate it.

## 3. What the test measures, cannot measure, minimal version
Measures: given four declared inputs (price, hours/account, pool, conversion), whether one person at a fixed capacity could in principle reach target MRR without contacting over half the pool. It is two inequalities: `price/hours >= target/capacity` and `price*buyers*conv >= 2*target` (proved in `reverse_report.txt`).

Cannot measure:
- Whether anyone will pay. Price is anchored on 4 of 14 rows, hours and buyers are mostly invented; conversion is a published blend, not yours.
- Speed. It checks the end state, not time to first dollar, sales cycle, trust, or churn.
- Non-delivery time: no sales/support hours subtracted (fixed here only by changing capacity).
- Pool 50% limit is arbitrary; contacts are not independent (same buyers recontacted, small pools saturate).
- Capital: ignored (fine for the no-capital constraint, but data/list cost is hidden).
- Passing is necessary, never sufficient. It can only kill; it cannot rank survivors (11 of 14 pass in every cell).

Minimal version worth keeping:
1. `price / hours_per_account >= target / delivery_hours` (use 150-190 h, $3-5k target).
2. `price * buyers * conv >= 2 * target`, with conv at 0.1% as the stress case, not 0.6%.
3. Replace "fully reachable at $10k" with weeks to first customer = `1/(contacts_wk*conv)` and to $3k = `ceil(3000/price)/(contacts_wk*conv)`.
Everything else (margins, nearest-input, 4-way flip table) restates these. The one real unknown is conversion; measure it with ~100-300 real contacts rather than refining the screen.
