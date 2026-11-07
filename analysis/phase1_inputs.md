# Phase 1 inputs: what is invented, and what free public source could replace it

Scope: 14 ventures x 4 inputs (price, service hours, buyer pool, conversion), from `vstress/data.py`.
Rows are ordered by revenue per delivery hour (price / service_hours); higher means more money rides on the verdict. The bar is $57.74/hr.

Status key: invented = "estimate / judgment, no source"; anchored = a cited range exists but not from this venture's own market test; measured = counted or tested.

"Value found" legend: **FETCHED** = I opened the page and read the number. **SEARCH** = number appeared in a search snippet only; open the URL before relying on it. "not found" = no free number retrievable this session.

Environment notes: the Census CBP API (`api.census.gov/data/2022/cbp`) returns "Missing Key". A free key is required (https://api.census.gov/data/key_signup.html), so no CBP counts were pulled. Direct `curl` from the sandbox is blocked, so only WebFetch/WebSearch were used.

Two inputs are the same for nearly every row, so they are described once here.

- **Service hours** is invented on all 14 rows. No free public source measures hours per account for a product that does not exist yet. Public data bounds it only indirectly: BLS OEWS gives the wage a human doing this work costs (https://www.bls.gov/oes/), and trade surveys and vendor claims give task times. The real replacement is a timed pilot on 3 to 5 accounts (`run.py field`). Value found: not found, by design.
- **Conversion** is a single blended constant (0.6%, "published") on 13 rows. It is not a measurement of any venture. The one exception is Customs (1.1%, verified list vs 0.05% purchased). No free public source gives venture-specific contact-to-customer rates. The replacement is the outbound test in `fieldtest.py`. Value found: not found, by design.

## Priority table (top rows, most effort)

| Venture ($/hr) | Input | Status today | Free source + URL | Value found |
|---|---|---|---|---|
| Trademark watch ($300/hr) | price $300/mo | invented | Markify public price list: https://www.markify.com/services/trademark-watch.html | **FETCHED**: $39-$129 per YEAR per watch (US Federal Full $39/yr, Global 190 registers $129/yr). That is about $3-11/mo, 25-100x below $300/mo. Higher end: Trademarkia $59/mo and Corsearch about $6,300/mo are third-party claims (SEARCH, https://gleanmark.com/pricing, https://g2.com/products/corsearch-trademark-and-brand-clearance/pricing). Screen verdict is at risk: $300 is only defensible if sold as a managed service, not a watch feed |
| Trademark watch | buyer pool 25,000 | invented | USPTO Trademark Data Visualization Center / bulk trademark assignment + case-file datasets: https://developer.uspto.gov/product/trademark-case-files-dataset ; owner counts by filing | SEARCH: >824,000 new classes filed FY2025, about 767,000 in FY2024 (implied); 3.3M+ live registrations (https://www.jdsupra.com/legalnews/filings-up-pendency-down-uspto-2024-6596406). Distinct small-owner count not found; needs a dedupe of owner names in the case-file dataset |
| Trademark watch | service hours 1.0 | invented | see note above | not found |
| Trademark watch | conversion | invented (blended) | see note above | not found |
| Customs HTS classification ($250/hr) | price $750/mo | anchored (CrossCode GTM) | Incumbent pricing pages (e.g. classification SaaS: Zonos, Avalara, Descartes) - not fetched | not found |
| Customs HTS | buyer pool 5,200 | measured ("counted") | CBP broker directory https://www.cbp.gov/about/contact/brokers-listing and filer code list https://www.cbp.gov/document/report/filer-code-list ; NCBFAA roster | **FETCHED** (CBP customs-brokers page): confirms the directory and filer-code list exist and are public; no total on the page. SEARCH: archived CBP page ~14,454 licensed brokers (2018), ~13,950 individuals (Jan 2022) (https://webharvest.gov/congress115th/20181203194740/https://www.cbp.gov/trade/programs-administration/customs-brokers/becoming-customs-broker). 5,200 is plausibly filer-code firms, not people; reconcile the definition before reuse |
| Customs HTS | conversion 1.1% | measured | own list test | n/a, already measured |
| Customs HTS | service hours 3.0 | invented | see note above | not found |
| RFP response drafting ($250/hr) | price $1,500/mo | invented | Loopio pricing page https://loopio.com/pricing/ ; Vendr marketplace | **FETCHED**: Loopio shows no price, "Let's Talk", Foundations tier includes 10 seats. SEARCH: starts about $20,000/yr (Loopio) = $1,667/mo; Vendr median $22,786/yr, range $11,770-$55,620 (https://www.vendr.com/marketplace/loopio). Supports $1,500/mo as plausible for a software-only buyer; a services buyer will compare against that |
| RFP response drafting | buyer pool 1,500 | invented | SAM.gov entity registrations (https://sam.gov/data-services) and Census CBP firm-size cells (key required) | not found |
| RFP response drafting | hours 6.0 / conversion | invented | see notes | not found |
| Environmental permit monitoring ($250/hr) | price $2,000/mo | invented | Incumbent compliance-monitoring pricing pages (Enhesa, Intelex, EHS software); no public list found | not found |
| Environmental permit monitoring | buyer pool 500 | invented | EPA ECHO downloads https://echo.epa.gov/tools/data-downloads (facility counts by CAA Title V / CWA NPDES / RCRA) | SEARCH: about 15,000 CAA Title V major facilities in ECHO (July 2016 figure, https://echo.epa.gov/resources/guidance-policy/guide-to-regulated-facilities). **This is 30x the 500 in the model.** If the true pool is 15,000, this row flips from BURNS THE MARKET toward reachable. Highest-leverage fix in the table. Facility pages themselves did not state counts (FETCHED, no number) |
| Environmental permit monitoring | hours 8.0 / conversion | invented | see notes | not found |
| Insurance subrogation ($233/hr) | price $3,500/mo | invented | Vendor pricing is contingency, not monthly (public fee schedules) | SEARCH: 15%-33% of recovery; 25% pre-suit, 33.3% after suit (https://www.mwl-law.com/faqs/what-fee-arrangement-does-mwl-use-for-subrogation/); a municipal contract 30% (https://permarisk.gov/resources/vendors-services/subrogation-recovery). Unit of price is wrong for a flat $/mo; model as % of recovery times recoveries/mo |
| Insurance subrogation | buyer pool 2,000 | invented | NAIC annual statement filer list; Census CBP NAICS 5241/524126 (key required); state DOI licensed-insurer lists | SEARCH only: 524291 (claims adjusting) about 4,554 establishments, unknown year, aggregator (https://naicslist.com/naics/524291). Not the carrier pool. Not found for carriers |
| Insurance subrogation | hours 15.0 / conversion | invented | see notes | not found |
| Freight audit ($229/hr) | price $800/mo | invented | Trade press / vendor pages | SEARCH: outsourced audit 5-10% of benchmark cost per bill; about $6.26 per invoice outsourced vs $10.74 in-house for small/medium shippers (JOC, https://www.joc.com/sites/default/files/u45421/Whitepapers/Freight-Payment-report-78441.pdf); recoveries 2-8% of spend. Price is usually per invoice or % of spend; $800/mo implies a spend/volume assumption nobody checked |
| Freight audit | buyer pool 6,000 | invented | Census Commodity Flow Survey / CBP wholesale NAICS 42 (key required); FMCSA is carriers, not shippers | not found |
| Freight audit | hours 3.5 / conversion | invented | see notes | not found |
| Grant compliance reporting ($225/hr) | price $900/mo | invented | Incumbent pricing (Fluxx, Submittable, Foundant) | not found |
| Grant compliance reporting | buyer pool 12,000 | invented | IRS EO Business Master File https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf ; NCCS Core PC file https://urbaninstitute.github.io/nccs/datasets/core/ ; USAspending.gov subrecipients | SEARCH: about 1.26M tax-exempt orgs, ~1M 501(c)(3) (aggregator). Count of orgs with federal grants not found; needs USAspending filter |
| Grant compliance reporting | hours 4.0 / conversion | invented | see notes | not found |

## Remaining rows (lower $/hr, lighter effort)

| Venture ($/hr) | Input | Status today | Free source + URL | Value found |
|---|---|---|---|---|
| Utility bill audit ($200) | price $500 | invented | Incumbent pricing is contingency on savings (public vendor pages) | not found |
| Utility bill audit | buyer pool 12,000 | invented | EIA CBECS https://www.eia.gov/consumption/commercial/ ; Census CBP NAICS 531 | not found |
| Medical billing denials ($200) | price $1,000 | invented | Billing-company pricing pages (typically % of collections) | not found |
| Medical billing denials | buyer pool 15,000 | invented | NPPES https://download.cms.gov/nppes/NPI_Files.html ; Census CBP NAICS 6211/6212 (key required) | not found |
| Lien waiver filing ($167) | price $250 | invented | Incumbent pricing (Levelset/Procore, Siteline) | not found |
| Lien waiver filing | buyer pool 20,000 | invented | Census CBP NAICS 238 (specialty trade contractors) (key required); state contractor licence registries | not found |
| Title searches ($167) | price $250 | anchored ($150-400; flat-fee rivals $29-385) | already anchored; re-verify with 3 incumbent pricing pages | not found |
| Title searches | buyer pool 20,000 | invented | Census CBP NAICS 541191 (key required); state DOI title-agent licence lists; ALTA member directory | not found |
| Prior-auth appeals ($141) | price $1,200 | anchored ($25-50/denial) | anchored; CMS/AMA prior-auth survey for volumes https://www.ama-assn.org/practice-management/prior-authorization | not found (not fetched) |
| Prior-auth appeals | buyer pool 8,000 | invented | NPPES (above) | not found |
| Veterinary claims ($133) | price $600 | invented | Pet-insurance claim-service pricing pages; none public found | not found |
| Veterinary claims | buyer pool 9,000 | invented | Census CBP NAICS 541940 (key required); AVMA practice counts https://www.avma.org/resources-tools/reports-statistics | not found |
| DOT compliance ($50, fragile) | price $150 | anchored (incumbents $29-199/mo) | already anchored; incumbent pages | not found |
| DOT compliance | buyer pool 30,000 | invented | FMCSA Registration Statistics https://ai.fmcsa.dot.gov/registrationstatistics ; Pocket Guide | SEARCH: 787,189 active motor carriers (2023), 813,844 (2022) (https://www.fmcsa.dot.gov/sites/fmcsa.dot.gov/files/2025-09/FMCSA%20Pocket%20Guide%202024-v6%20508%20.pdf). Pool of 30,000 is about 4% of that; filter by size/for-hire to get an honest pool |
| DOT compliance | hours 3.0 | invented | fragile: verdict flips at 2.60 hrs, so this is the one hours input worth a real timing | not found |

Rows not listed separately (hours, conversion for every venture) follow the two notes at the top.

## What to do first

1. Environmental permits pool: pull ECHO bulk facility counts; model has 500, public data suggests thousands.
2. Trademark watch price: public competitors sell for $39-129/yr; $300/mo needs a managed-service justification.
3. DOT pool: filter FMCSA census by for-hire and fleet size.
4. Customs pool: reconcile 5,200 with CBP's roughly 14k broker listing (people vs firms vs filer codes).
5. Subrogation and freight audit: restate price as % of recovery / per invoice before trusting $/hr.
6. Get a free Census API key and pull CBP establishment counts for NAICS 5241, 6211/6212, 238, 541940, 541191, 531, 42 in one script.
