# Account, campaign, ad-set and ad analysis

Use the reporting level that answers the question. An account overview, a campaign comparison, an ad-set delivery problem and a creative diagnosis need different evidence. Choose the useful checks below; they are not a fixed audit or required output structure.

## Scope and retrieval

Use the existing authorized connector or dated export. Discover its current supported levels and fields before requesting account, campaign, ad-set or ad data. Connector capabilities vary; an API field is not necessarily exposed by the installed tool.

Request native totals for the requested level and period. Account queries provide account-wide totals directly; campaign/ad-set queries provide their own totals. A few fetched children cannot stand in for a full parent. Keep exact IDs, requested/effective dates, timezone, currency, event/value definition, attribution, filters, breakdowns and completeness attached to the results. Current settings are not proof of historical settings.

Common supported metric families include spend, impressions, reach/frequency, distinct click types, landing-page views, website/omni/app purchase counts and values, cart/checkout/lead events and available video measures. Query the fields relevant to the business question; do not fetch every field for a simple lookup. Preserve extra returned source metrics rather than forcing them into a small sales template. A campaign name cannot establish the purchased product, subscription, margin or customer status.

| Scope | Useful source context | Boundary |
|---|---|---|
| Account | Native totals, currency, timezone and outcome mix | Mixed objectives need interpretation; fetch child settings separately. |
| Campaign | Objective, delivery, bid strategy, actual spend and budget | Campaign attributes do not establish every child ad set's settings. |
| Ad set | Campaign ID, optimization, targeting, attribution, delivery and budget | Current settings may postdate the period; distinguish budget ownership. |
| Ad | Parent IDs, metrics and creative identity when relevant | Metrics need no image; a creative explanation needs actual copy/media. |

Keep connector-provided account context at account scope even when it accompanies child rows. Use queries that support explicit dates for period analysis; an all-history trend is not an exact-period substitute. Tool recommendations remain hypotheses to assess.

## Questions and adaptive drilldown

- **What changed?** Compare compatible complete periods; keep the partial current day and recent conversion lag visible. Inspect absolute spend/outcome counts as well as percentage changes. A previous zero has no finite percentage increase.
- **Where is it concentrated?** Move from account to campaigns, or campaign to ad sets/ads, when needed. Distinguish a within-entity decline from a shift toward a different objective, audience, offer or delivery mix. Prefer a material contribution over a spectacular rate on tiny spend.
- **Why might it have changed?** Select relevant evidence: auction cost, click response, post-click events, purchase value, frequency, delivery/status, targeting/placement mix, budget/bid edits, tracking or destination. Missing funnel fields do not establish the cause. Several explanations may remain plausible.
- **Which result supports the decision?** Compare peers for the intended business outcome and period. Keep prospecting/retargeting and different optimization/event scopes distinct. Mixed-objective account totals can describe overall spend and attributed return, but cannot rank all campaigns as if they had the same job.
- **What would resolve uncertainty?** Retrieve a specific missing field, inspect creative, check a narrower compatible slice or propose a test. Stop expanding when the question is answered or further accessible data would not change the decision.

## Totals, shares and comparisons

Never total account + campaign + ad-set + ad rows together. Each is a different view of overlapping delivery. Prefer source-native parent totals. If a disjoint complete child set is used for additive metrics, label its coverage and reconcile it to the native total. Filters, deleted/archived objects, pagination, event scope, rounding and attribution can explain differences; preserve the unexplained difference.

Recompute aggregate CPA, CPC, CTR, CPM and ROAS from compatible additive totals, not averages of child ratios. Reach and other unique measures require native aggregation; child/day reach cannot be summed, and frequency must use impressions and reach at the same native scope. Keep source-reported ratios alongside recomputation. Budget is configuration, not actual spend; verify units before converting raw minor amounts.

Spend/outcome/value shares require a compatible parent denominator and full known coverage of that measure. An observed spend share describes delivery allocation; it does not prove causality or an optimum allocation. Do not convert sparse outcome counts into automatic pause/scale recommendations. Account attributed purchase value is not Shopify revenue, profit or incrementality.

Use the optional [analysis helper](analysis-tool.md) for calculations and evidence checks when useful. It provides machine-readable facts; the agent chooses the investigation and assesses explanations.
