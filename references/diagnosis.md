# Diagnosis and decisions

Use for a deep review, a material allocation/creative recommendation, or why performance changed. Work through the decision, not every available metric. Simple lookups remain simple.

## Start with the action

Identify the choice: continue, investigate, retest, change a concept, change allocation, or defer. State the business outcome and constraints, including known budget and required timing. Retrieve the latest relevant decision/outcome from the existing project ledger before repeating prior research.

Anchor the investigation to the exact requested entity ID. For a campaign question, first account for spend and outcome changes inside that campaign, identify the largest material ad-set/ad contributions, and separate auction cost, click response, arrival and buying signals. Keep all downstream comparisons within the verified campaign subtree. A store-wide finding may be relevant background; it cannot become the main recommendation when the user asks how to improve a particular campaign. Never import an attractive ad from another campaign into the candidate list without explicitly labeling it an outside reference.

Build a small internal working note: decision; reporting scope; decisive observations; leading explanation and strongest alternative; next evidence that could change the choice. This is reasoning structure, not a required report or new file. Distinguish two jobs:

- **Operational choice:** what is sensible to do now given observed outcomes, costs, uncertainty and reversibility.
- **Causal learning:** what the evidence establishes about the effect of a creative feature, page, audience or advertising itself.

A useful operational choice can precede a proven causal explanation. Avoid both confident storytelling and withholding every recommendation until perfect data exists.

## Fetch the next useful evidence

Start with compatible native outcome totals and the relevant baseline. Preserve exact IDs, dates/timezone, collection time, metric definitions, attribution, report-time basis, filters and coverage. Complete calendar days can still have immature conversions; retain recent extracts for revision checks. Do not invent finality to enable arithmetic.

Before an additional query, identify internally which possible result would change the recommendation. Prefer evidence that separates the leading explanations. If no result would change the choice, omit that optional query. Batch independent reads, then reassess; avoid fetching every breakdown, creative or competitor before discovering where the material change lies.

| Decision uncertainty | Usually useful next evidence | Defer unless it changes the decision |
|---|---|---|
| Does the drilldown cover the campaign? | Required fields, returned IDs/date slices, continuations, status filters, compatible native totals | Creative explanations from an unreconciled subset |
| Did the same ads worsen or did delivery mix change? | Exact-ad periods plus native totals; continuing, entering and exiting delivery | Wider competitor research |
| Did Meta freely favor an ad? | Current minimums/caps/bids, optimization and actual spend; dated changes where available | Treating allocation as proof of superiority |
| Is fatigue a plausible explanation? | Native same-period weekly reach/frequency and exact-ad response; material placement mix | Monthly frequency or a universal frequency cutoff |
| Is the post-click experience a problem? | Exact click/LPV/checkout/purchase definitions; public destination and measurement changes | Blaming a page from cross-system ratios alone |
| Which creative direction deserves the next test? | Actual media/full copy, comparable source ads, failed/under-delivered alternatives, customer evidence | Generating many variants before choosing the learning question |
| Is acquisition or profit improving? | Matching orders/new-customer identity and cost basis | Inferring products, subscriptions or profit from Meta names/ROAS |

Current settings and pages establish current observations. Seek historical evidence before attributing a past result to them. For Shopify pages, verify a fresh public context, redirects, final URL, theme role and preview status. Use the actual creative/destination branch when making visual or page claims.

## Validate enough to support the choice

For a complete drilldown, check requested versus returned entity/date coverage, failed batches, duplicate keys, absent fields and active/paused/archived status scope. Follow required read continuations. Finished pagination alone can hide omissions. Reconcile spend and decisive outcomes against native totals, retaining exact residuals and justified rounding tolerance. Equal totals support additive consistency, not exhaustive identity or causality.

Repair a detected retrieval problem with a narrower bounded ID/date request. If that repair still cannot resolve it, state the subset limit and the specific missing evidence instead of repeating the same query. Use another genuinely different authorized route only if it is available and could change the decision. Never replace missing values with invented zeroes.

Use optional analysis tools for compact rows and driver calculations. Keep every relevant ID and source pointer; record any selection/omission. Decompose a rate change into same-entity change and delivery mix, keeping entrants/exits separate. Weight by the rate's denominator and verify that contributions reconstruct the total. This is an arithmetic explanation, not a causal estimate. Entry means newly observed delivery within the selected windows, not necessarily a newly created ad.

Use native reach/unique measures. Separate age and placement breakdowns are not joinable customer records. Purchases with absent LPVs can reflect reporting scope; they do not prove duplicate tracking.

## Make the business meaning explicit

Meta purchase CPA and attributed ROAS describe platform-reported outcomes. Without order-level evidence, use “Meta-reported value per attributed purchase,” not basket contents or new-customer CAC. Shopify orders, attribution credits, sessions, customers and subscription memberships have different denominators. Record report/model, timezone, revenue components and refunds. Any-click credits can overlap. Verify report-definition changes before comparing exports from different versions.

For a profitability or acquisition decision, identify the smallest missing commerce bridge: matched order/customer acquisition identity, first subscription versus renewal, or net revenue and variable costs. Verify those inputs through authorized sources where available. First-order contribution before advertising can support an acquisition target only for the same population and cost basis. Later repeat revenue needs an observed cohort and follow-up horizon. All-store revenue divided by Meta spend is not true Meta ROAS.

When economics are unknown, provide the supported platform comparison and conditional next action. Do not manufacture a break-even target, profit claim or guaranteed return.

## Make the call, then pick the test

Give every ad a verdict with `scripts/decisions.py` and the client config (`target_cpa`, `conversion_lag_days`, `min_spend`): wait, kill, scale or iterate with a reason code. Report the deciding number and raw counts beside it; low-volume rows (<10 purchases) are labelled, not hidden. Rows on a mixed attribution window get no verdict. Check that an apparent winner is not one large order or one favourable breakdown.

Angle comparisons are directional: same ad set and window only, 2+ ads per angle (`angle_rollups`). Advantage+/CBO shifts budget toward winners, so cross-ad-set angle totals are confounded.

Name the learning question before the variation and change one level at a time (concept > angle > hook > execution). Keep the existing ad as control. Ground each fresh direction in a campaign observation and a concrete scene or story; collapse look-alike ideas. With small budgets, test fewer, bigger contrasts. See `creative-and-tests.md` for the checklist, fix mapping and `tests.csv` rows.

## Close the decision loop

Return the leading action, decisive evidence, main uncertainty and what would change the decision. Keep this short. A bounded reversible test can be the right next action while the mechanism remains unresolved. Do not automatically turn analysis into production or account changes.

Stop optional collection when accessible evidence cannot change the recommendation, its cost exceeds the likely decision value, or the required source is unavailable. Honor explicit scope and depth requests; stop rules are not permission to abandon requested work. For lengthy current reviews, verify that the cutoff still answers the question and add a separately labeled provisional update if needed.

Save only reusable findings and decisions in the existing project ledger, including the exact scope, selected action/test, unresolved evidence and a future observation that would confirm, contradict or reopen it. On a later request, read that record and its outcome before repeating the full investigation. No new tracker, schedule or automatic account action is implied.

See [primary sources](sources.md). Query selection is a qualitative decision aid, not a numerical prediction model. Instructions and arithmetic checks do not establish improved live advertising results.
