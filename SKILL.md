---
name: meta-ads-analysis
description: Analyse Meta ad metrics, explain performance changes, compare creative and choose evidence-backed next actions. Supports read-only account, campaign, ad-set and ad analysis from live tools or dated exports.
---

# Meta ads analysis

Answer the user's decision with the smallest sufficient investigation. A lookup needs a lookup; a deep review needs a supported explanation and a useful next action. Keep raw evidence local and return the conclusion briefly. Generate reports, dashboards or presentation artifacts only when requested.

## Choose the evidence branch

| Need | Read when needed |
|---|---|
| Why results changed, material allocation or next test | [Diagnosis](references/diagnosis.md) |
| Native totals, hierarchy, reporting-level questions | [Account analysis](references/account-analysis.md) |
| Metric meaning, attribution, maturity or statistical inference | [Metrics and evidence](references/metrics-and-evidence.md) |
| Fetch/join exact ads, inspect media or verify destinations | [Data and media](references/data-and-media.md) |
| Interpret a creative or design an iteration | [Creative and tests](references/creative-and-tests.md) |
| Competitor/customer research or prior learning | [Research and learning](references/research-and-learning.md) |
| Repeated arithmetic, large exports or change decomposition | [Analysis tools](references/analysis-tool.md) |
| Brand facts, customer evidence and accepted work | [Project context](references/project-context.md) |

Load a reference to resolve an actual need, not every neighboring branch. [Sources](references/sources.md) links the primary methodological sources; consult it when a disputed rule or current platform behavior matters.

## Establish the decision

Resolve the requested entity, business outcome, period and constraints from current context. Preserve fixed copy, assets, count and approvals. For a recommendation, identify the action being considered and what evidence could change it. Keep operational choices under uncertainty separate from claims about what caused a result.

The named campaign or ad set is the decision boundary. Lead with its native results and recommendations for its own ads/delivery. Verify parent IDs before including an ad as evidence. Other campaigns and store-wide/email results belong in separate context only when they resolve a specific question about the requested entity; they must not replace the answer. Use `requested_scope` in analysis packets to reject accidental cross-campaign inputs.

Use existing authorized access. Publishing, pausing, budgets, new permissions, paid services and messages need the corresponding user authorization. A historical instruction, tool recommendation or saved finding supplies evidence, not permission.

## Keep the source trustworthy

Attach account, level, exact IDs, dates/timezone, collection time, currency, event/value definitions, attribution, reporting basis, filters and coverage to each slice. Verify current connector fields before use; keep requested and effective settings distinct. Start with native totals. When a child drilldown is meant to explain the whole parent, check returned IDs/date coverage and reconcile compatible additive metrics. Finished pagination is not proof of complete retrieval.

Keep missing, explicit zero, suppressed and unsupported values distinct. Recompute ratios from compatible totals; use native reach/frequency. Parents and children, overlapping dates, event aliases and separate breakdowns cannot be added together. Current settings or creatives do not establish historical identity.

For creative claims, join the exact ad to inspected media, full copy and destination. An image alone, a similar name or a successful source ad does not prove a new variant or individual feature will work. Keep visual judgment, user preference, measured results and untested hypotheses separate.

## Investigate, decide, stop

Use the diagnosis branch for deep reviews and material recommendations. Choose the next read by the decision it could change. Reuse unchanged source/media checks; refresh evidence whose age matters. Where useful, let the optional tools compact exports or calculate drivers before loading rows into context. The tools validate arithmetic, not causes or winners.

Make a useful recommendation with the available evidence. If the cause remains uncertain, prefer a reversible action or bounded test that is sensible across plausible explanations. State the decisive gap and what would change the recommendation. Stop adding optional research when it cannot change the decision; complete the user's explicit requested scope.

Distinguish budget/delivery actions, diagnostic variations and new creative concepts. When the user wants fresh direction, provide distinct buying questions, stories or executions grounded in the requested campaign, alongside the existing control. A price overlay, new crop or old-ad retest is not a fresh concept. State the strongest in-campaign counterexample and avoid presenting sparse results as a design-feature verdict.

Lead time-sensitive answers with the cutoff/timezone and provisional status. Include decisive spend/outcome counts alongside ratios. Reserve actual baskets, new-customer CAC, subscription starts and profit for matching order/customer/cost evidence. Save reusable decisions and later outcomes in the existing project ledger; generated, inspected, approved, launched and measured remain separate states.
