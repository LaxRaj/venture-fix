# Phase 2: Channel evidence for contact -> paid conversion

Scope: free web sources only, retrieved 2026-11-06. The repo's `DEFAULT_CONVERSION = 0.6%` is meant to be contact -> PAID customer. Almost every published benchmark is a reply rate or a meeting rate, and almost all of them come from outreach-tool vendors or lead-gen agencies, who have a reason to report high numbers. Rows marked (assumed) are my own stage assumptions, not sourced data.

## (a) Funnel table

Implied contact->paid = reply x meeting x paid, computed by me, not quoted from any source.

| Channel | contact->reply | reply->meeting | meeting->paid | implied contact->paid | source URL | bias note |
|---|---|---|---|---|---|---|
| Cold email, mass send, all B2B | 0.45% (unique replies / sends; open tracking off) | about 3.5% (1,200 meetings / 34,393 replies; my arithmetic) | 3.53% (appointment->close, Belkins 2023, outsourced appointments) | about 0.0006% (0.016% meeting/email x 3.5%) | https://belkins.io/blog/cold-email-response-rates.md ; https://belkins.io/blog/lead-generation-conversion.md | Large sample (7.5M emails, 2025), denominator is sends, so it is the most honest reply figure. It is an agency's client campaigns, mostly generic lists and not tuned for one niche. The 1,200-appointments figure may be partial. Replies include negatives. |
| Cold email, micro firms (0-10 employees) | 0.72% (11-50 employees: 0.49%) | n/a | n/a | n/a | same Belkins page | The size breakdown is the only SMB cut I found. |
| Cold email, vendor "typical" claims | 5% or more (usually per opened or per delivered email) | n/a | n/a | not usable | https://instantly.ai/blog/cold-email-reply-rate-benchmarks | Inflated by the denominator. Do not use. |
| Cold email, meeting rate | n/a | n/a | n/a | meeting per email: about 1% claimed (vendor roundup), 0.2% "good" (other source), 0.016% (Belkins arithmetic) | https://www.shno.co/marketing-statistics/cold-email-statistics | The sources conflict by 60x. No clean primary data. |
| Cold call, B2B | 9.9% connect per dial (24.5% of prospects connect at least once over about 3 attempts) | 4.6% of conversations become a meeting | about 20% (assumed, from the vendor win-rate range below) | about 0.2% per prospect (24.5% x 4.6% x 20%). The 1-per-370-dials figure is 0.27% meeting per dial. | https://belkins.io/blog/cold-calling-benchmarks | 175k dials by an SDR agency on its own dialer, with no SMB cut. Gong's figure of about 5.4% connect per dial is secondary and I could not confirm it first-hand. |
| LinkedIn outreach (free manual) | 25-28% connection acceptance; 8-10% of messages get a reply, so about 2% per invite | 20-30% (assumed) | about 20% (assumed) | about 0.1-0.15% | https://expandi.io/blog/linkedin-outreach-benchmarks (13.2M attempts) ; https://belkins.io/blog/linkedin-outreach-study.md | Automation-tool vendor data. Connection-note reply rates are falling (3.5% to 2.2% in 11 months, per Expandi). The reply->meeting and meeting->paid stages are my assumptions. |
| Warm referral / partner / association intro | n/a (the intro is the reply) | n/a | 25-26% (referral SQL->close) vs 9.4% for cold calling in the same source; other vendors claim 25-40% for warm intros | not a contact rate, so see the note | https://prospeo.io/s/how-to-win-clients ; https://growsurf.com/statistics/b2b-referral-marketing-statistics/ | Weakest evidence. Claims are often attributed to HBR or Forrester with no traceable study. Referral figures range from 3.6% to 70% across sources. The usable point is that warm leads close roughly 2-4x better than cold. |
| Meeting->paid, services generally | n/a | n/a | 20-30% opportunity win rate (Ebsta/Pavilion via Gigradar: about 20-21% average, above 30% for top teams); 28% for professional services in a 2026 IT-services benchmark | n/a | https://gigradar.io/blog/win-rate-calculator ; https://www.data-mania.com/blog/it-services-firm-gtm-benchmarks-2026/ | Vendor blogs, mostly mid-market or SaaS. I found no sourced SMB meeting->paid benchmark. |
| Repo's own measured data | not stated | not stated | not stated | 1.1% (verified list) vs 0.05% (purchased) | analysis/reverse_report.txt section 4 | The only first-party number. A 22x spread comes from list quality alone. The funnel stage it measures is unclear and should be confirmed, because 1.1% sits well above every cold-channel product above. |

Reading the table: every cold channel built from published stage rates lands at about 0.001-0.2% contact->paid. The repo's 0.6% default is above all of them. Only a verified, niche-matched list plus a warm element (referral, association credibility, a relevant trigger) gets near 1%.

## (b) Recommended contact->paid range

For a no-budget solo operator who uses verified lists, sends personalized outreach by hand, and works one niche:

| Case | contact->paid | Reasoning |
|---|---|---|
| Low | 0.1% | Cold email or LinkedIn alone, with good targeting. Matches the call and LinkedIn products above. |
| Base | 0.3% | Mixed cold email, calls and LinkedIn on a verified list, plus some referral lift. Half of the repo's 0.6%. |
| High | 1.0% | Verified list, trigger-based or warm-adjacent contacts, association or referral lift. Consistent with the repo's measured 1.1%, which should be treated as a best case. |

Implications:
- Do not hold 0.6% as the base case. Stress the board at 0.1%, 0.3% and 1.0%, and keep 0.05% (purchased list) as the failure case.
- The ventures that only pass at 0.6% or higher are fragile. report section 4 shows 11 of 14 ventures pass at 0.6% and 0 of 14 at 0.1%, so the verdict flips inside this range.
- Measure the real number with a small pilot. About 300-500 verified contacts per venture gives roughly 1-5 paid customers at base, enough to tell 0.1% from 1%. Track the stages separately (reply, meeting, paid).
- Sample-bias caveat: all the sourced figures come from firms that sell outreach, so treat them as upper bounds for a solo amateur.

## (c) Free channels for a solo no-budget operator

| Channel | Notes |
|---|---|
| Trade association member rosters and directories | Many are public. Check the association's terms before bulk-exporting. Members are pre-qualified by niche. Attending or sponsoring a chapter event is the warm route. |
| State licence and registry lookups (contractor boards, insurance and medical licensing boards, bar associations, state business registries) | Public records. They give name, licence type and sometimes address. Some states restrict commercial use or bulk download, so read each state's terms. Emails are often missing, which means calls or mail. |
| LinkedIn free tier | Manual search, connection requests, and posts. Free accounts hit weekly invite and search limits. |
| Niche communities (Reddit, Slack and Discord groups, Facebook groups, association forums) | Answer questions, no pitching. Many ban promotion, so read the rules. Slow, but leads arrive warm. |
| Partnerships and referrals (accountants, brokers, software vendors and consultants who serve the same buyers) | Highest conversion per the sources above (about 2-4x cold), but slowest to set up. Offer a referral fee or a reciprocal intro. |
| Public filings and trigger events (permits, new licences, court or regulatory filings, job posts) | Free data that gives a reason to reach out now. |

## (d) Legal constraints (not legal advice)

- **CAN-SPAM (US email).** It applies to B2B email too, with no exemption. Requirements: truthful From, Reply-To and routing headers; non-deceptive subject lines; disclose that it is an ad; include a valid physical postal address; give a clear opt-out that works for at least 30 days and is honored within 10 business days; and you stay responsible even if a vendor sends for you. Penalty is up to $53,088 per violating email. Source: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business . Cold B2B email is allowed if it complies. GDPR/PECR apply if you target the EU or UK, and CASL applies in Canada. I did not research those.
- **TCPA and Do Not Call (calls and texts).** The FCC page was blocked (403), so this comes from general knowledge and is unverified here. The National DNC Registry covers consumer numbers, and B2B calls are generally outside it. Autodialed or prerecorded calls and texts to cell phones need prior consent, and the sole-proprietor line between "business" and "consumer" is a common trap (small-business owners often use personal cell numbers). Several states have their own telemarketing rules. Manually dialed calls to business landlines are the lowest risk. Check with a lawyer before any dialer or SMS use.
- **LinkedIn ToS.** The User Agreement prohibits bots and automated access to the service. In hiQ v. LinkedIn, the court ruled in 2022 that hiQ breached the agreement by scraping and by using fake accounts, and the case then settled (https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn ; https://proskauer.com/blog/court-finds-hiq-breached-linkedins-terms-prohibiting-scraping-but-in-mixed-ruling-declines-to-grant-summary-judgment-to-either-party-as-to-certain-key-issues). Practical rule: manual use, no scraping, no automation tools, no fake profiles, and expect account restriction if you break it. Federal CFAA exposure for public data is narrow, but contract exposure remains.
- **Public records and rosters.** Terms of use and state commercial-use restrictions can limit bulk collection of the data even when it is publicly viewable.

## Gaps

- No independent (non-vendor) study of contact->paid for SMB services.
- No sourced SMB meeting->paid rate. The 20-30% used above is from general B2B win-rate blogs.
- Cold-email meeting rates conflict by 60x across sources.
- Whether the repo's measured 1.1% is contact->reply, contact->meeting or contact->paid is not established.
