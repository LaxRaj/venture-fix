# Lane: finding clients for other people's services

Method: WebSearch only (no logins, no .env, no vstress edits). Almost every price below comes from vendor marketing blogs with no methodology. Treat as directional. "(est.)" = my estimate, not sourced. "(recall)" = from memory, not verified this session. Search tool returns result summaries, so URLs are the pages the search surfaced; I did not open them all.

## Skeptical headline
- Generic "cold email / appointment-setting agency" is oversupplied. Salesforge's own guide says the barrier is so low the market is crowded with agencies that can send email and cannot deliver results (https://www.salesforge.ai/blog/start-cold-email-agency). GigRadar reports cold email reply rates of 3-5% and CPL climbing every quarter (https://gigradar.io/blog/lead-generation-agency-outbound-channels). Small-client churn cited at 10-15%/month for <10-headcount clients (secondhand Hormozi summary: https://daniliants-com.pages.dev/insights/alex-hormozi-2026-ai-agencies-cold-email.md). No source gave an agency count; the saturation claim is qualitative, but every top result is an agency selling the same thing.
- Your advantage is not the service, it is a narrow vertical plus a pay-on-result structure. Retainer-with-no-guarantee competes with thousands; vertical + per-appointment/per-booked-job does not compete the same way, but shifts all risk to you.
- Pay-per-X models require you to have working traffic first. With $0 and no list, time to first dollar is dominated by your own outreach conversion (route file uses 0.3% contact-to-paid base, 0.1% stress; 100 contacts/week => roughly 0.3 paid/week at base).

## Offers

### 1. Done-for-you appointment setting for ONE vertical (home-service contractors: roofing/HVAC), per-appointment or low retainer + per-appointment
- Buyer: owner of roofing/HVAC/plumbing firm with 3-30 staff who has a sales closer.
- Price today (vendor-sourced): B2B per-meeting $50-$300 (Intelemark), $150-$500 qualified (Prospeo), up to $750-$1,500+ for enterprise: https://www.intelemark.com/blog/b2b-appointment-setting-pricing-guide-models-costs-and-roi-standards-for-2025/ , https://prospeo.io/s/appointment-setting-pricing . Retainers: small-business $1k-$3k/mo (low), $3k-$8k typical, $10k+ high (https://www.devcommx.com/blogs/b2b-appointment-setting-cost , https://stealthagents.com/blog/b2b-appointment-setting-services). Hybrid $2-4k base + $150-400/meeting. Contractor-side: a contractor already pays $40-$110 per shared roofing lead and $80-$220 exclusive (https://blog.99calls.com/2026/02/02/roofing-lead-generation-costs-in-2026/). So a set, kept appointment is worth maybe $150-$400 to a roofer (est. from those numbers; booked-job cost via shared leads ~$400 per one source).
- Delivery hrs/account/month: 15-30 (est.: list build, sequences, replies, calendar handoff, reporting).
- Buyer pool: roofing contractors ~19k establishments in older Census tables (stale, mid-2000s; https://webarchive.library.unt.edu/web/20081105102538/http://www.census.gov/compendia/statab/tables/08s0925.pdf); current CBP is likely 20-25k (recall). HVAC (NAICS 238220) ~ 100k+ establishments (recall, not verified). Free count: Census CBP API/data.census.gov by NAICS and state, plus Google Maps scraping per metro (the route file notes a CBP API key is free).
- Free reach channel + benchmarks: cold email/call to owners from Google Maps/state license boards (public licensing lists are free). Benchmarks: cold email 3-5% reply (GigRadar), LinkedIn cold reply 3% to 15% depending on source, "good" >20% reply claimed by vendors only (https://www.stackmatix.com/blog/linkedin-lead-generation-services). Contractors are not on LinkedIn much; calls and text-free email/direct mail are more realistic (est.).
- Compliance: calls/texts to cell phones need TCPA prior express written consent for marketing autodialed/prerecorded/text; FCC one-to-one consent rule was vacated by the 11th Circuit Jan 2025, but consent and new revocation rules remain (https://www.steptoe.com/en/news-publications/one-to-none-the-fcc-and-eleventh-circuit-issue-last-minute-rulings-gutting-the-one-to-one-tcpa-consent-rule.html). Live manual B2B calls to business lines are lower risk but check the National DNC / state mini-TCPA (FL, OK, others) (recall). CAN-SPAM: B2B cold email legal if truthful headers, physical address, opt-out honored; per-email penalty is about $53k (recall). You (the sender on their behalf) share liability.
- Time to first dollar: 2-5 weeks (est.) if you sell a pilot with pay-per-appointment; slower if retainers.
- Saturation: very high for generic; moderate for trade-specific. Buyers have been burned by agencies; they will demand guarantees.

### 2. Pay-per-lead / pay-per-booked-job lead gen for home-service trades (own the lead, resell)
- Buyer: same contractors, but you carry the traffic.
- Price: exclusive roofing $60-$220 per lead (typ. $80-$220), shared $15-$85; HVAC exclusive $40-$150, shared $25-$75; booked-job cost via shared leads ~$400 at 10% close (https://blog.99calls.com/2026/02/02/roofing-lead-generation-costs-in-2026/ , https://www.nopio.com/blog/hvac-lead-generation/ , https://elevarus.com/roofing-lead-generation-2026-generate-or-buy-verified/). Angi annual fee ~$288-300 plus per-lead (cited in same search).
- Delivery hrs: 20-40/account-month (est.) if running organic/GBP/landing pages; paid ads need ad spend, which you do not have at $0 capital, so only organic/SEO-fed leads are viable.
- Pool: same as above. Count method: Census CBP + Maps scrape.
- Reach: you need demand-side traffic with no money, i.e. SEO pages/GBP. That is slow (months). Outreach benchmark for selling to contractors: see offer 1.
- Compliance: lead forms need clear TCPA consent language; selling a lead to one buyer is cleaner after the one-to-one rule vacatur, but plaintiffs still sue over vague consent. State contractor-licensing rules in some states restrict who can advertise roofing (recall).
- Time to first dollar: 6-16 weeks (est.) because you must rank/seed demand first.
- Saturation: very high; Angi, Thumbtack, large lead brokers with paid traffic dominate. Zero-capital entrant has no cost advantage.

### 3. Rank-and-rent local sites (service-area niches)
- Buyer: local contractor in a thin-competition niche (junk hauling, tree work, garage door, towing).
- Price: one rental vendor lists flat rentals from about $500/mo (junk hauling ~$500, tree work ~$550) (https://bold-coast-leads.pages.dev/services/website-rentals/). Sellers claim sale value 24-36x monthly rent (unsourced; Raven blog https://raventools.com/blog/rank-and-rent-seo/). Low about $300 (est.), high $1,500+ (est., big metros/legal-adjacent niches). Only one vendor data point; no independent survey found.
- Delivery hrs: build 20-40 hrs once per site, then 3-8 hrs/month (est.).
- Pool: tied to niche x metro count; no meaningful national count. Free method: Google Maps pack check, rank before pitching.
- Reach: build site first and let calls show up as proof, then call the top-3 competitors in that niche. Benchmark: none published that I found.
- Compliance: low. Avoid legal/medical niches (referral fee and advertising rules). Call tracking needs recording-consent notices in two-party-consent states.
- Time to first dollar: 2-6 months (est.) because ranking takes time. Worst fit for speed.
- Saturation: high among SEO hobbyists; actual rankings in competitive metros are hard; Google updates can wipe rankings.

### 4. LinkedIn outreach management (done-for-you) for B2B service firms
- Buyer: agencies, consultancies, SaaS founders, recruiters who want meetings.
- Price: tool-only $39-ish; managed services $500-$3,000/mo typical; $2k-$6k for named agencies (Impactable), $3k flat (Salesbread), Outbound System from $499/mo; enterprise $5k-$15k (https://www.stackmatix.com/blog/linkedin-lead-generation-services , https://derrick-app.com/en/best-linkedin-outreach-agencies-us/ ). Low $500, typical $1.5k-$3k, high $5k+.
- Delivery hrs: 10-20/account-month (est., with automation tools).
- Pool: founders/owners of B2B firms; LinkedIn Sales Navigator search shows counts but needs a paid seat (free count: LinkedIn basic search result totals, or Census CBP NAICS 5416 consulting ~ 300k+ establishments, recall).
- Reach: LinkedIn itself plus cold email. Benchmarks 3% (cold) to 8-15% (personalized) reply; vendor-only claims of 20%+. The channel is the product; selling LinkedIn outreach by LinkedIn outreach is the best proof, and also where competing agencies are most numerous.
- Compliance: LinkedIn User Agreement bans automation; account bans are a real delivery risk to the client (recall). GDPR if EU targets. CAN-SPAM n/a for LinkedIn DMs.
- Time to first dollar: 2-4 weeks (est.).
- Saturation: very high. This is the most oversupplied offer on the list (agency-on-agency market).

### 5. Referral / finder-fee deals (commission brokerage) in non-regulated services
- Buyer: businesses that pay a % for new customers, e.g. solar, home security, merchant services, commercial insurance via licensed partners; or B2B services with partner programs. Also legal and medical lead gen, see compliance.
- Price: no verified benchmark for finder fees across these; general sponsorship brokers charge 10-35% of raised amount (https://powersponsorship.com/?p=25334, non-newsletter). Affiliate/partner commissions vary by program (not researched this session). Mark as unverified.
- Delivery hrs: 5-15/month once a pipeline exists (est.); the work is sourcing.
- Pool: depends on the vertical; no single count.
- Reach: community groups, local business networks, content. No published benchmarks found.
- Compliance (the main blocker): Lawyers: under Model Rule 7.2 lawyers may not pay for referrals, per-lead fees are allowed in some states and banned in others (RI Op. 19-03 bars per-lead payment to for-profit internet lead services: https://www.courts.ri.gov/AttorneyResources/ethicsadvisorypanel/Opinions/19-03.pdf ; NJ Joint Op. 741 allows per-lead but not per-retained-client and warns about disguised referrals: https://law.justia.com/cases/new-jersey/advisory-committee-on-professional-ethics/2021/acp741-1.html ; NY Op. 1131 allows flat/per-lead if lawyer selection is mechanical; SC 16-06 bars fees tied to lawyer's fee; Arizona repealed Rule 7.2 in 2021). Medical/dental: federal Anti-Kickback applies where federal payers are involved, and many states prohibit fee-splitting or patient brokering (recall, not verified here). Insurance and mortgage referrals require licenses or RESPA-compliant structure (recall). Real estate referral fees require licensed broker involvement in most states (recall).
- Time to first dollar: 4-12 weeks (est.), one deal at a time; commission paid after the sale closes.
- Saturation: low in ad hoc niches, but cash is irregular and you depend on the vendor honoring payment. Get written agreement.

### 6. Newsletter sponsorship brokerage / UGC creator management
(two adjacent models, both marketplace-style)
- Buyer: (a) small/mid newsletters that cannot sell ads; (b) DTC brands needing UGC videos.
- Price: sponsorship broker commissions 10-35% (general sponsorship, not newsletter-specific: https://powersponsorship.com/?p=25334); ad networks take 20-50% (unverified, e.g. Kit Sponsor Network 20% per https://dupple.com/learn/best-newsletter-advertising-platforms ). No newsletter-specific broker rate found. UGC: per-video $50-$150 beginner, $150-$300 experienced, $250-$500+ premium (https://www.influee.co/gb/blog/ugc-price , https://blog.xolo.io/top-ugc-creator-pricing-guide-with-rate-examples); agency adds 20-40% management markup (https://superscale.ai/learn/how-much-does-ugc-cost-real-pricing-breakdown-for-2025/). Marketplace fees: Fiverr 20%, Upwork 10%, JoinBrands 15%.
- Delivery hrs: newsletters 5-10/month per publisher (est.); UGC 3-6 hrs per brief (est.).
- Pool: newsletters: thousands on Beehiiv/Substack (Substack and Beehiiv directories are free to browse); DTC brands: Shopify store lists via free builtwith-style crawls or Meta Ad Library (free). Counts not verified.
- Reach: DM/email publishers and brands; benchmark cold reply 3-5%.
- Compliance: FTC endorsement rules require disclosure of paid sponsorships and UGC ads (recall); contracts and usage rights/ whitelisting terms; 1099 tax handling.
- Time to first dollar: 3-8 weeks (est.).
- Saturation: newsletter brokerage is crowded by platforms (Paved, Passionfroot, Kit, beehiiv Ad Network) that take the margin. UGC is flooded with creators and AI-generated video pressuring rates down (one source "apxlab" title references AI changing UGC rates; unverified). Thin margins.

## Cross-cutting benchmarks
- Cold email reply 3-5% (GigRadar); LinkedIn 3%-15% (sources disagree; vendor-supplied).
- Dental reference: cost per new patient $150-$350 via Google Ads, $50-$150 SEO, $180-$400 Denver metro (https://www.webtonic.io/blog/dental-digital-marketing-statistics , https://ainora.lt/blog/dental-patient-acquisition-cost-statistics). Dental/medical lead gen: HIPAA applies to any PHI you handle (recall; not confirmed in search).

## Ranking for a $0, 60-80 hr/week solo operator
1. Vertical appointment setting for home-service contractors (pay per kept appointment, one metro first). Fastest to money, price anchored by known lead costs; saturation exists but vertical + guarantee differentiates. Biggest risk: TCPA on any calls/texts, and you carry outreach quality risk.
2. Newsletter sponsorship / UGC brokerage (small, 3-8 weeks, low compliance, but low margins and platform competition). Better as a side stack.
3. LinkedIn outreach management for B2B service firms (fast to first dollar, but the most oversupplied and exposed to LinkedIn automation bans).
Rank-and-rent and pay-per-lead resale rank below because they need weeks to months of lead time before any dollar, and pay-per-lead needs ad spend. Referral/finder-fee in legal/medical is a compliance trap; only consider non-regulated verticals.

## Gaps
- No independent (non-vendor) pricing or benchmark for any offer. Pool counts for HVAC/dental/consulting are from memory. Reddit and Upwork demand not checked. Newsletter broker commission and finder-fee rates not found.
