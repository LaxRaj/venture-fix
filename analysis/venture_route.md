# Venture route (Phase 3 + 4)

Inputs: the six phase files in `analysis/` plus `analysis/phase3_route.py` (run `python3 -I analysis/phase3_route.py`).
Assumptions: 190 delivery hrs/month, 100 outbound contacts/week, contact-to-paid 0.3% base and 0.1% stress (`phase2_channels.md`). Prices and pools are the agents' cited values where they have one. Pool sizes for Grant, DOT and Trademark are my guesses (marked E in the script). Nothing here is a revenue forecast. It is a ranked hypothesis list.

## What the corrected screen says
| Venture | $/hr | Result at $3k MRR (0.3%) | Result at $10k MRR (0.3%) | Weeks to $3k |
|---|---|---|---|---|
| Customs HTS @ $750, 2,365-firm pool | 250 | fails pool test | fails pool test | 13 |
| Customs HTS @ $1,400 (needs $770+ to break even) | 467 | passes | fails pool test | 7 |
| Grant compliance @ $400 | 100 | passes | **passes** | 25 |
| DOT 1-10 trucks @ $150 | 50 | passes | fails capacity | 67 |
| RFP drafting @ $1,500 | 250 | passes | fails pool (1,500 firms) | 7 |
| Trademark watch @ $33 | 33 | fails pool | fails capacity | 303 |

- **Trademark watch is dead.** Incumbents charge $39-$400 a year, not $300 a month.
- **Only Grant compliance clears $10k**, and only on a pool size I guessed. It is slow: about 83 weeks to $10k at 100 contacts a week.
- **At 0.1% conversion**, nearly everything fails the pool test at $10k. Customs, RFP and Grant all fail.
- **No single venture reaches $10k MRR on cold outreach alone.** The realistic target for one venture is $3k-$5k, so the route is a stack.

## The route: one logistics/trade outreach motion, three ventures
Why this cluster: the three best-evidenced rows (DOT, Freight audit, Customs HTS) sell into trucking, shipping and trade communities, so one set of channels and one list-building effort serves all of them.

1. **Weeks 1-3: DOT/driver-file compliance for 1-10 truck fleets (first dollar).** No licence, flat fee, and FMCSA new-registrant lists plus trucker groups give a warm-ish channel. Cap it around 15-20 accounts. It cannot carry $10k, but the service-first agent estimated a first dollar in 1-3 weeks, and it funds the rest.
2. **Weeks 3-10: Freight invoice audit for small shippers, contingency.** Public pricing is 15-50% of recovered savings, or $0.50-$2 per invoice, with no upfront cost to the buyer. The screen cannot score it because its unit is not a flat monthly price. The buyer pool count is unverified.
3. **Weeks 6+: Customs HTS classification at $1,400-$1,500.** Highest $/hr (467), but the cited pool is only about 2,365 firms. Sell it as a high-ticket service to a short, verified list through broker associations. Treat it as a $3k-$5k venture.
4. **Side option, not in the stack:** Grant compliance ($350-$500/mo, pool of roughly 100k charities with government grants). It is the only row whose pool survives the screen at $10k, but it is a different buyer and a different channel.
5. **Avoid:** Medical billing denials (HIPAA agreements and insurance), lien waivers (unauthorized-practice-of-law rulings), trademark watch (price wrong by 10-90x).

Hours at 60-80 a week: about 60% outreach and list-building in weeks 1-4, shifting to delivery as accounts land. DOT at 3 hours per account caps near 63 accounts at 190 delivery hours, which is below the 67 it needs for $10k at $150 a month. That is why it is capped at about $3k-$5k here.

## The cheapest real-world test for each (do these before building anything)
| Venture | Test | Pass signal |
|---|---|---|
| DOT | DM 100 small fleets from FMCSA new-registrant data with a flat $99-$149 offer | 1 paid within 3 weeks |
| Freight audit | Offer 10 small shippers a free audit of their last 90 days; take 25% of recovery | 1 shipper signs a contingency agreement |
| Customs HTS | Call 40 brokerage firms from the CBP/association lists at $1,400 | 1 paid pilot, and whether "firm" means one buyer |
| Grant compliance | 30 conversations with nonprofit finance leads | 1 paid pilot at $350+ |

## Still unknown (these can change the ranking)
- **Service hours per account:** invented on every row. Time the first two accounts.
- **Conversion:** 0.3% is a vendor-sourced base. The real number only comes from sending.
- **Freight audit pool and flat-fee viability:** unverified.
- **Reddit and Upwork demand:** the demand agent was blocked. Needs a browser check.
- **Census CBP counts:** need a free API key.
- **DOT:** a 787k carrier pool needs a for-hire, size-filtered count.

## Conflicts between agents
- **DOT:** ranked first for speed to first dollar, but the arithmetic caps it near $3k. Used here as the starter, not the engine.
- **Medical billing:** top demand signal, but a top compliance blocker. Excluded.
