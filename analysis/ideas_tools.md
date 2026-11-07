# Lane: TOOLS (micro-SaaS / templates / automations)

Method: WebSearch only (standard mode, one pass per topic). Prices come from third-party comparison blogs that often disagree with each other and are often vendor- or affiliate-written. Verify on vendor pricing pages before relying on any number. Items marked (E) are my estimates, not sourced.

## Bottom line
- Every tool below competes with a free tier or a bundled feature from a company with far more money. A $0 solo builder can only charge a "small convenience" price ($5-$15/mo).
- Arithmetic: $3k MRR at $9/mo is 334 paying accounts. At 5% monthly churn (the middle of the 5-10% range cited for low-touch micro-SaaS), annual churn is ~46%. Holding 334 accounts needs ~17 new paying accounts every month forever, before any growth.
- Churn evidence: micro-SaaS low-touch 5-10%/mo; SMB micro-SaaS 3-5%/mo; one dataset puts micro-businesses at 8.9%/mo (69% annual). Sources: [userjot](https://userjot.com/blog/saas-churn-rate-benchmarks), [winsavvy](https://winsavvy.com/?p=66887), [calcplanet/bigideasdb](https://bigideasdb.com/help/how-to-calculate-churn-rate), [withorb](https://www.withorb.com/blog/saas-churn-statistics). Methodology is weak across all of them, but none show freelancer tools below 3%.
- Tools do not fit the repo's current route (logistics/trade B2B services at $150-$1,500 per account). Per-account revenue here is 10-100x lower. Best use of this lane: build tools for your own outreach (dogfooding) and sell only what falls out.

## Competitor price snapshot (third-party figures)
| Incumbent | Free | Paid | Source |
|---|---|---|---|
| OpusClip | 60 credits/mo, watermark | Starter $15, Pro $29/mo | [ssemble](https://www.ssemble.com/blog/opus-clip-pricing-2026), [castmagic](https://www.castmagic.io/blog/opus-clip-pricing) |
| Vizard | 60 upload min/mo, 720p, watermark | ~$14.50-$20/mo (sources conflict) | [techsy](https://techsy.io/en/blog/opusclip-vs-vizard) |
| CapCut | Free editor, limited auto-captions (sources conflict) | Pro $7.99/mo older; a 2026 report says annual rose to ~$180 | [flowith](https://flowith.io/blog/capcut-pricing-free-vs-pro-vs-team-paid-plan-worth-it), [eesel](https://eesel.ai/blog/capcut-pricing) |
| Submagic | Trial, 3 watermarked videos | $19 / $39 / $69 per member per mo | [hooked](https://www.hooked.so/compare/submagic-pricing), [costbench](https://costbench.com/software/ai-video-editing-saas/submagic/) |
| Captions app | Free tier | Max $24.99, Scale $69.99/mo (Pro $9.99 reportedly removed) | [pricingsaas](https://pricingsaas.com/companies/captions) |
| Frame.io | Free: 2 members, 2 GB, 2 projects | Pro ~$15/user, Team ~$25/user per mo | [capterra](https://www.capterra.com/p/148214/Frame-io/pricing/) |
| Dropbox Replay | Time-stamped comments on a free Dropbox plan (vendor claim) | Add-on ~$10-$12/user/mo | [shade](https://shade.inc/blog/dropbox-review-video-production), [dropbox](https://www.dropbox.com/features/content-collaboration/video-feedback-tool) |
| Vimeo review | Basic comments free (terms unconfirmed) | From ~$12/seat/mo | same shade link |
| HoneyBook | Trial | $29 / $99 / $109 per mo | [assembly](https://assembly.com/blog/honeybook-pricing) |
| Dubsado | 21-day trial | ~$35 / $55 per mo (conflicting) | [prospeo](https://prospeo.io/s/dubsado-pricing-reviews-pros-and-cons) |
| Bonsai | Trial | ~$9-$25/mo (sources conflict) | [niche-blog](https://niche-blog.pages.dev/reviews/bonsai-pricing/) |
| Apollo | Free, ~900-1,200 credits/yr | Basic ~$49/user/mo | [apollo](https://www.apollo.io/insights/apollo-vs-lemlist) |
| Lemlist | 14-day trial (free tier claims conflict) | ~$69/mo | [mailmeteor](https://mailmeteor.com/blog/lemlist-pricing) |
| Instantly | None found | ~$30-$97/mo | [aitoolsatlas](https://aitoolsatlas.ai/tools/instantly/pricing) |
| Notion/Gumroad templates | n/a | Templates EUR 5-15 simple, 15-49 systems; Gumroad ~10% fee | [fungies](https://fungies.io/?p=40040), [kajabi](https://kajabi.com/blog/can-you-make-money-selling-notion-templates) |

Not checked: Wave and Invoice Ninja free tiers (search returned nothing). Assume free invoicing exists; treat any invoicing idea as lost until shown otherwise.

## The six tools

### 1. Clipper campaign tracker (multi-platform views, payouts, rule checklist)
- Buyer: clippers working Whop Content Rewards, Vyro and similar pay-per-view campaigns.
- Competitors: no dedicated tracker found. Adjacent: AutoClip (connects to Whop/Vyro/Kick, [autoclip.dev](https://autoclip.dev/earn)) and spreadsheets. Platforms show their own dashboards.
- Free vs paid: platforms give per-campaign stats free. Gap is a cross-platform view of earnings, rule compliance, and what to clip next.
- Price: $5-$9/mo (E). Clippers are low-income and most run 2-3 platforms ([clipaffiliates](https://www.clipaffiliates.com/blog/best-clipping-platforms-compared)).
- Support: ~0.25 hr/account/mo (E). Breakage whenever a platform changes its page or API.
- Pool: one vendor blog says ~62,000 clippers, avg $3,000/mo ([ssemble](https://www.ssemble.com/blog/best-clipping-platforms-2026)). Unverified. Count free: Whop/Vyro public leaderboards and Discord member counts.
- Free reach: clipper Discords, X, TikTok/YouTube Shorts "how I clip" posts, Whop community posts.
- Build time: 1-2 weeks (E). Scraping platforms may breach their terms, so use manual entry/CSV import first.
- First dollar: 2-4 weeks (E).
- Risks: platforms add their own analytics; clippers churn out of clipping fast (no data, but "earn" side hustle population); income pool depends on payouts (>$150k/mo on Whop per one blog) that can shrink; vendor-sourced pool figures.

### 2. AI clip-finder / caption tool for clippers
- Buyer: clippers, podcast repurposers.
- Competitors: OpusClip, Vizard, Submagic, Captions, CapCut (table above).
- Free vs paid: free tiers give 60 credits or minutes with watermarks. CapCut includes captions in a free editor.
- Price a solo could charge: $9-$15 (E), below OpusClip's $15 and undercutting only by giving up quality. Per-video GPU/transcription API cost eats margin when you have $0 capital.
- Support: 1 hr/account/mo (E) (failed renders, quality complaints).
- Pool: same ~62k clippers, but they already have free options. 
- Free reach: same clipper channels. Crowded; many "OpusClip alternative" SEO pages already (see search results).
- Build time: 3-6 weeks for acceptable quality (E).
- First dollar: 4-8 weeks (E).
- Risks: worst of the six. Red ocean, free alternatives, variable cost per user, incumbents improve weekly. Skip.

### 3. Client tracker + invoicing for freelance video editors
- Buyer: freelance editors.
- Competitors: Bonsai ~$9-$25, HoneyBook $29+, Dubsado ~$35+; free invoicing apps (not verified).
- Free vs paid: invoicing/contracts are the paid core; free invoice generators exist.
- Price: $7-$12 (E). Niche angle: per-video pricing, revision counts, retainer clips.
- Support: 0.5 hr/account/mo (E) (payment/Stripe/tax questions).
- Pool: no reliable count. Estimates run 27k US freelance editors (Zippia) to 1.2M-7.3M worldwide (blog stats, wildly inconsistent) ([zippia](https://www.zippia.com/freelance-video-editor-jobs/trends)). Free count: Upwork category search result totals, r/editors and r/VideoEditing subscriber counts.
- Free reach: r/editors, r/VideoEditing, editing Discords, X "build in public". Self-promotion rules limit this.
- Build time: 2-3 weeks (E). Payments handling adds compliance burden.
- First dollar: 3-6 weeks (E).
- Risks: HoneyBook/Bonsai already serve freelancers; Notion/Sheets template is the true competitor; freelancers cancel when they have a quiet month. Money handling and tax features create liability.

### 4. White-label video review/approval portal
- Buyer: editors and small agencies who want clients to leave timestamped comments on their own brand.
- Competitors: Frame.io (free 2 GB, $15-$25/user), Dropbox Replay (~$10-$12 add-on, free comments on free Dropbox per vendor), Vimeo (~$12/seat).
- Free vs paid: free tiers cover 1-2 projects; storage and seats are the paywall.
- Price: $9-$19 flat (E).
- Support: 0.5-1 hr/account/mo (E) (upload failures, large files).
- Pool: same editors, no count. Free count as above.
- Free reach: r/editors threads "Frame.io alternative" (people ask regularly, e.g. [this r/editors post](https://redlib.hyperreal.coffee/r/editors/comments/1jvvvm8/i_tested_8_frameio_alternatives_for_media_review)).
- Build time: 3-4 weeks (E). Video hosting and bandwidth cost real money. At $0 capital you need free-tier storage or links to the user's own Drive/Dropbox/YouTube-unlisted. Link-only version (embed + timestamped comments) is cheap but thin.
- First dollar: 4-8 weeks (E).
- Risks: Frame.io, Dropbox, Vimeo, Google Drive all ship this; the free tiers match solo-editor needs; storage cost scales with users.

### 5. Lead-list builder + outreach tracker for freelancers
- Buyer: freelancers/service sellers doing cold outreach.
- Competitors: Apollo (free, ~900-1,200 credits/yr; $49 paid), Lemlist (~$69), Instantly (~$30-$97), plus free Sheets/Notion/Airtable CRMs.
- Free vs paid: Apollo free gives limited credits; sequencing and volume are paid.
- Price: $10-$19 (E).
- Support: 1-2 hr/account/mo (E). Email deliverability and data-quality complaints are the heavy part.
- Pool: huge but undefined. Not countable free in a meaningful way.
- Free reach: X/LinkedIn "cold outreach for freelancers" content; crowded with agency owners selling the same.
- Build time: 2-4 weeks for a tracker; data sourcing is the hard part (E).
- First dollar: 4-8 weeks (E).
- Risks: generic version loses to Apollo free; data licensing and spam-law exposure; high churn once a user lands clients or gives up outreach.
- Better variant: do NOT sell a generic tool. Build the FMCSA new-registrant / CBP broker list pipeline the route already needs (see `venture_route.md`) and sell it as a niche list product or use it purely internally. That has a proven buyer segment (the route's service ventures) and no SaaS support load.

### 6. Template and prompt packs (proposal/pricing generator, editor client onboarding kit, clipper workflow pack)
- Buyer: editors, clippers, freelancers.
- Competitors: Notion templates on Gumroad/Notion marketplace (EUR 5-49 each), free Notion templates, free GPT/prompt libraries. Proposal generators are bundled free into Bonsai/HoneyBook funnels.
- Free vs paid: lots free as lead magnets; paid are curated systems and bundles.
- Price: $9-$39 one-time (E from [fungies](https://fungies.io/?p=40040)).
- Support: ~0.05 hr per sale (E). Lowest of the six.
- Pool: not countable as a pool; it is a traffic game. Top creators claim six-to-seven figures (Thomas Frank ~$1M from two templates, per a blog), but that is survivorship; typical creators sell a few copies a month ([kajabi](https://kajabi.com/blog/can-you-make-money-selling-notion-templates), [dev.to](https://dev.to/fermainpariz/how-to-make-money-selling-notion-templates-in-2026-realistic-guide-5g09)).
- Free reach: Reddit, X, Pinterest/Etsy search, YouTube. Etsy/Gumroad give some discovery traffic.
- Build time: 1-3 days per pack (E).
- First dollar: 1-3 weeks (E) if you post to channels daily; could also be never.
- Risks: no recurring revenue (one-off sale means restart each month), platform fees ~10% Gumroad, copycats, AI-made templates flooding the market.

## Ranking (for this operator)
| Rank | Tool | Why |
|---|---|---|
| 1 | #1 Clipper campaign tracker | Least-served gap I found (no dedicated competitor), cheapest to build, reachable channels are free and dense. Weakest points: unverified pool, low price, churn. Treat as a 30-day test, not a business. |
| 2 | #6 Template/prompt packs | Fastest to a first dollar and no support. No recurring revenue and discovery is luck-dependent. Use as a cash experiment and as lead magnets for #1. |
| 3 | #5 variant: niche lead-list pipeline | Only option that reinforces the existing logistics/trade route; value is mostly internal. Not a SaaS. |

Not recommended: #2 (clip AI, red ocean + variable cost), #3 (bundled/free competitors), #4 (hosting cost + Frame.io/Dropbox/Vimeo).

## Cheapest tests before building
| Tool | Test | Pass signal |
|---|---|---|
| Clipper tracker | Build as a Google Sheet + 1-page landing; post in 5 clipper communities | 10 sheet downloads and 3 people pay $5-$9 for a hosted version |
| Template pack | List 1 pack on Gumroad, post 14 days | 5 sales |
| Lead-list pipeline | Build for own use first | Produces >100 usable contacts in a week |

## Unknowns
- No verified clipper count or willingness to pay; the 62k figure is from a vendor blog.
- Editor/freelancer pool counts conflict by 100x. Needs a free count from Upwork/Reddit.
- Support hours and build times are all estimates.
- Reddit demand not checked (blocked/unavailable in this lane).
