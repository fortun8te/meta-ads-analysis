# Metrics and evidence

## Metric identity

Use one named event and matching value scope. Website purchases, omni purchases, app purchases, first conversion and all conversions can overlap or describe different events. Preserve action names and counting mode; do not sum purchase aliases or hierarchical action arrays. ROAS is attributed value divided by spend, not profit or incrementality.

| Diagnostic | Formula with compatible data | Interpretation limit |
|---|---|---|
| CTR all | clicks all / impressions × 100 | Includes interactions beyond destination traffic |
| Link CTR | link clicks / impressions × 100 | Links can lead on or off Meta |
| Outbound CTR | outbound clicks / impressions × 100 | Off-Meta clicks; definitions can differ across formats |
| CPC all/link/outbound | spend / that exact click type | Label the denominator |
| CPM | spend / impressions × 1000 | Auction and delivered audience context matter |
| CPA | spend / selected purchases | Unknown or zero purchases makes CPA undefined |
| Purchase ROAS | matching purchase value / spend | Match website/omni/app scope, currency and attribution |
| Purchase-to-LPV ratio | selected purchases / LPV × 100 | Descriptive event ratio, not a same-user cohort conversion rate |
| LPV-to-outbound ratio | LPV / outbound clicks × 100 | Page/measurement diagnostic, not a strict funnel probability |
| Frequency | impressions / aggregate reach | Reach is deduplicated; child reach does not add |

A zero denominator makes a ratio undefined. Missing numerator makes it unknown. Explicit zero purchase value with positive spend can yield zero ROAS; missing value cannot. Preserve source ratios alongside recomputed ratios and investigate discrepancies in scope/rounding rather than silently overwriting them. Additive compatible disjoint totals can recompute aggregate CPA, CTR and ROAS; averaging row percentages/CPAs/ROAS is wrong. Reach and other unique measures require a requested aggregate. Overlapping date windows, nested attribution windows, total rows plus breakdowns, repeated snapshots and aggregate-plus-component events cannot be added.

Video metric labels must specify numerator and denominator. A 3-second-play/impression ratio is an operational hook proxy, not a universal definition. Verify the returned ThruPlay definition and goal against the source's current documentation rather than hard-coding a duration. Different goals, clip lengths and denominators make ratios incomparable. Static images have no video hook/hold metrics.

## Attribution and maturity

Read effective account/ad-set settings and export column definitions. Click-through, view-through and engagement definitions can change across rollout/account contexts. Preserve model, window, counting mode and collection date instead of hard-coding a default. A short-click window can be a sensitivity check; it is not causal ground truth. Compare to shop/CRM totals only on compatible dates, timezones, event/value definitions and refund treatment. Attributed sales do not imply unique store orders or incremental sales.

Recent results may acquire late conversions or be revised. Compare matched complete periods, preferably weekdays and relevant seasonality, with the account's observed lag. Keep the most recent window provisional when warranted. Do not impose a universal 72-hour or seven-day finalization rule. Record requested and effective reporting basis; API docs and implementations can disagree. Unsupported/mixed-attribution breakdowns can omit conversion fields. Hourly reach/frequency zeros can mean unsupported metrics. Retain missing, suppressed, unsupported, failed and explicit zero states.

## Descriptive analysis

Choose the reporting level and metric families for the actual question; use [account and hierarchy analysis](account-analysis.md) for native totals, allocation and drilldown. Pure metrics analysis does not require creative retrieval. Parent totals and their children overlap; keep them as separate scopes. Mixed-objective account figures describe a blend, not a common-purpose competition among campaigns.

Start with the business outcome, then trace available supporting signals. For a sales objective, show spend, purchase count, CPA and matching revenue value/ROAS. Attention helps diagnose the path. A high CTR with weak purchases is an attention signal with conversion evidence to investigate; it does not prove poor traffic or a bad page.

Choose peers by actual objective/optimization, funnel, product/offer, destination, audience and placement, period and attribution where available. Preserve missing comparison fields. Use the account's relevant baseline rather than universal benchmarks. Check current vs historical creative identity, delivery share, campaign/ad-set constraints and major changes. Higher allocation can reflect Meta's optimization and feedback loop; it is not randomized superiority. Very little delivery is insufficient evaluation, not a demonstrated loser.

When a trend changes, locate its scope: one ad, siblings, ad set or wider account. Inspect compatible dated CPM, click, purchase and exposure signals; check placement/audience composition, bid/budget/learning/status changes, tracking, offer and page. Rising CPA or frequency alone does not prove fatigue. Report suspected fatigue and test a fresh execution when that is the most useful hypothesis. Disentangle creative deterioration from auction pressure, mix, measurement and post-click changes without claiming the available data isolates the cause.

Use two confidence dimensions in prose: data completeness/identity/maturity and how strongly the observation supports the explanation. A fully inspected image can still have weak performance evidence. Avoid numeric confidence scores without a defined validated model.

## Tests and causal claims

Ordinary Ads Manager comparisons are directional. Matching breakdowns improves relevance but does not remove hidden selection. Meta randomized A/B allocates eligible groups, while delivery can optimize differently within them. Describe the tested creative + delivery strategy result. Randomization does not necessarily isolate a headline's psychological effect. A Lift experiment answers a different incremental question. Neither attributed ROAS nor a platform's modeled incremental attribution alone proves that this task ran an independent lift experiment.

For formal testing, prespecify hypothesis, primary business outcome, comparator, population, changed variables, attribution/reporting basis, practically useful effect, duration/sample rationale and stopping rule. A bundled concept test estimates the bundle. Monitor operational health without declaring a statistical win through repeated favorable peeking. Use a justified sequential method if sequential stopping is intended. Exploratory many-ad/many-metric slicing needs replication or appropriate multiple-comparison handling before formal certainty.

Low outcome volume needs counts and uncertainty, not a magic spend/impression floor. If statistical intervals are useful, establish the model and independent experimental unit first. Wilson/exact binomial intervals can fit a legitimate independent binary-outcome experiment; they do not automatically fit impression-level modeled purchases, repeated exposures, event ratios or ROAS. Zero observed purchases does not prove zero underlying demand. Inconclusive is a useful outcome. Further testing should be worth the decision's business cost.
