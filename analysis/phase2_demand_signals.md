# Phase 2: Demand signals (free web sources)

Date run: 2026-11-06. Method: WebSearch/WebFetch only.

## Coverage caveats (read first)
- Reddit is blocked for the search tool (domain not accessible), so NO Reddit threads were retrieved. Reddit is unverified, not negative.
- Upwork job pages return HTTP 403 on fetch; only search snippets were available. HN Algolia returned only tangential hits.
- Result: most evidence below is INDIRECT (market price points, labor-cost proxies, vendor and trade-press figures). No signal here is a verified buyer posting "I will pay $X" except #7, whose cached snippet could not be re-fetched. Treat everything as hypothesis, not validation. Next step is manual outreach or Reddit/Upwork browsing in a real browser.

## Signals

| # | Problem | Who pays | Stated price / budget | URL | Recency | Independent mentions | Maps to venture |
|---|---|---|---|---|---|---|---|
| 1 | Denied claims written off because small practices lack staff time to appeal (e.g. $400-$600 claims abandoned; "not worth $800 of time on a $200 claim") | Small practices, clinics | Done-for-you billing plan $599/mo (under 150 denials/mo); Upwork denial-management gigs $600-$1,200/project; staff rework ~$25-$118/claim | https://www.medicaleconomics.com/view/we-re-writing-off-revenue-we-already-earned-and-calling-it-inevitable ; https://ravenswoodbilling-landing.pages.dev/pricing ; https://www.upwork.com/hire/billing-freelancers/ | Apr 2026 / Nov 2026 | 5+ (trade press, vendor pages, AMA survey: 55% say insufficient staff to appeal) | Yes: Medical billing denials (Keystone Billing / Verity Medical) |
| 2 | Freight invoice errors / carrier overcharges, hard to audit in-house | Shippers, 3PLs | Audit firms take 15-25% of recovered savings or flat per-invoice fee; errors 3-8% of invoices (vendor claims) | https://www.inboundlogistics.com/articles/freight-payment-and-auditing-services-cash-is-king ; https://rabot.us/blog/3-5-of-parcel-spend-is-hiding-in-invoice-errors/ | 2025-2026 | 6+ vendor/trade pieces (all vendor-sourced) | Yes: Freight audit |
| 3 | Same freight audit as a labor spend: companies hire auditors at $18-$32/hr remote contract | Logistics firms | $18-$23/hr (Insight Global contract), $22-$32/hr, avg $29.11/hr | https://www.ziprecruiter.com/Jobs/Remote-Freight-Audit ; https://insightglobal.com/jobs/find_a_job/florida/deerfield-beach/freight-coordinator/job-513876/ | Jun 2026 / Aug 2025 | 4+ postings | Yes: Freight audit (sets a labor-replacement price ceiling) |
| 4 | Commercial utility bill overcharges and missed sales-tax exemptions | Multi-site commercial property owners | Contingency (percentage of recovered; exact % not stated); recoveries 3-30% vendor-claimed | https://www.costanalysts.com/services/utility-auditing/ ; https://nyrej.com/print/32573 | 2025-2026 | 4+ (all vendors) | Yes: Utility bill audit (Summit Utilities) |
| 5 | Gov-contract RFP/proposal writing outsourced by small contractors | Small gov contractors | $20-$40/hr (Upwork expert-level, 30+ hrs/wk, 6+ months); Fiverr/Upwork gigs many | https://www.upwork.com/freelance-jobs/apply/Proposal-Writer-Need-for-Gov-Contractor_~022082120165123507110/ (fetch 403; from search snippet) ; https://www.upwork.com/hire/proposal-writers/ | Cached, undated | 1 job post plus ~15 seller listings (supply, not demand) | Yes: RFP response drafting (Lantern RFP) |
| 6 | HTS/HS tariff classification confusion amid tariff churn | Importers, small e-commerce | Upwork tariff consultants $40-$70/hr entry, $70-$130/hr audits; per-product gigs from ~$40 | https://www.upwork.com/hire/tariff-experts/ ; https://news.ycombinator.com/item?id=49802472 (HN thread on small-biz EU shipping, Sep 2026) ; https://news.ycombinator.com/item?id=45080330 (businesses can't price under tariffs, Aug 2025) | Sep 2026 | 3 (HN threads are complaints, no price) | Yes: Customs HTS classification (Tidewater Customs) |
| 7 | Freight-audit industry insider asking whether to build tooling in-house (payback unclear) | Freight audit firm | No figures stated; no replies | https://news.ycombinator.com/item?id=41197880 | Aug 2024 | 1 (weak) | Yes: Freight audit (weak) |
| 8 | Lien waiver chasing is "tedious and complicated"; spreadsheet-based, tools have ~0 reviews | GCs, subs | None found | https://www.levelset.com/?p=50493 ; https://www.capterra.com/p/10044019/Waivr/ | 2026 | 2 (vendor content only; Capterra listings show 0 reviews) | Yes: Lien waiver filing (Redwood Lien) - NO price evidence |

## Ranking by strength of evidence of payment
1. Medical billing denials (#1): clearest quantified pain plus visible prices ($599/mo, $600-$1,200/project) and survey data on staff shortage. Risk: HIPAA/BAA overhead, 67% of physicians doubt appeals will succeed.
2. Freight audit (#2, #3, #7): established contingency pricing (15-25%), labor market $18-$32/hr. Risk: incumbents (Trax etc.) and carrier-dispute access.
3. Customs HTS classification (#6): consultants charge $40-$130/hr, topic is hot in 2026 tariff environment. Risk: liability for misclassification.

## Not found / gaps
- No verified Reddit/HN posts with stated budgets (tool limits). No evidence found for: veterinary claims, subrogation, grant compliance reporting, trademark watch, environmental permit monitoring, title search (no queries run beyond those above).
- No signals outside the 14 ventures were identified; none are "new".
- Vendor-sourced percentages are marketing claims.
