# Optional callable analysis helper

Use this helper when reliable arithmetic, metric availability or reporting-slice validation would improve the analysis. It is a calculator and validator. The agent decides which data to fetch, what to compare, which explanation fits and whether another read is useful. Calling it is not a mandatory step for every lookup.

```text
python3 <skill-folder>/scripts/analyze_meta.py <normalized-input.json> --mode metrics
```

The default returns machine-readable JSON on stdout. Optional `--out <new-directory>` saves only analysis.json. It makes no account calls, network requests, media-file reads, HTML pages, reports or rankings. For in-process use import `analyze(payload, mode="metrics")`. The old review_pack.py name calls the same helper. Keep full working output local when large; read back only facts relevant to the decision.

## Verdicts

```text
python3 <skill-folder>/scripts/decisions.py <normalized-input.json> --config client.json [--as-of YYYY-MM-DD]
```

`client.json`: `{"target_cpa": 25, "conversion_lag_days": 3, "min_spend": 25}` (lag and floor optional; floor defaults to 1× target CPA). Output per ad, sorted by spend: `verdict`, `reason`, `next_step`, raw `counts`, `low_volume`, CPA/ROAS/CTR, video `hook_rate`/`hold_rate`, `creative_review` (`deep` or `skip_low_spend`), own-history `fatigue`, `name_parts` for `CLIENT_concept_angle_hook_vN` names, and directional `angle_rollups`.

Per-row analyzer flags: `low_volume`, `counts`, `attribution_mixed`, plus warnings for broken rows, unparseable values (excluded, never fatal; clean numeric strings like `"12"` are accepted) and missing purchase value.

## Source input

Use schema_version 2, a context object and rows at any supported level. IDs must be exact strings; amounts/counts must be numeric values normalized from source units. Null means unavailable; zero means an explicit reported zero. A row context overrides shared context. Preserve raw responses and field mapping separately or in row provenance.

```json
{
  "schema_version": 2,
  "mode": "metrics",
  "context": {
    "account_id": "authorized-account",
    "currency": "USD",
    "timezone": null,
    "report_start": "2026-10-01",
    "report_end": "2026-10-07",
    "attribution": null,
    "purchase_event": "offsite_conversion.fb_pixel_purchase",
    "purchase_value_event": "offsite_conversion.fb_pixel_purchase",
    "counting_mode": null,
    "report_time_basis": null,
    "source_path": "raw/campaign.json",
    "collected_at": "2026-10-08T00:00:00Z"
  },
  "rows": [{
    "level": "campaign",
    "entity_id": "exact-campaign-id",
    "name": "source name",
    "metrics": {
      "spend": 100,
      "impressions": 2000,
      "reach": 1200,
      "link_clicks": 40,
      "purchases": 2,
      "purchase_value": 125
    }
  }]
}
```

Levels are account, campaign, adset and ad. Native parent rows must not carry child IDs. If a row includes its level-specific ID it must agree with entity_id; account identity must agree with context. Parent totals and child rows remain separate. v1 ads/ad_id inputs are accepted as an adapter, with normalized v2 output metric names.

For a named-entity task, set top-level `requested_scope`, for example `{"level":"campaign","entity_id":"campaign_demo"}`. The validator checks the whole packet before calculations. It accepts that exact campaign and descendants with verified matching parent IDs, and rejects other campaigns, account-wide rows or missing membership. Keep outside comparator/context data in a separate packet. Compact/focus/driver views preserve and enforce the same scope. Inputs without this optional constraint retain their existing behavior.

Core normalized metrics include spend, impressions, reach, clicks_all, link_clicks, outbound_clicks, landing_page_views, purchases and purchase_value. Optional cart, checkout, lead, video and custom metrics are supported; current keys/formulas are discoverable in analyze_meta.py. Preserve event scope, video goal and denominator meanings in context.metric_scopes and source provenance. Numeric extras remain available; structured fields remain in source_metrics. Do not relabel an unsupported source metric to fit a formula.

metric_status can mark reported, unknown, suppressed, unsupported or failed. Non-reported values are excluded from calculations, including structural zeros. Reported requires a numeric value. The output retains source_metrics, usable metrics, statuses, derived_metrics, exact formula definitions, warnings and source metadata. Unknown event/value scope is flagged; conflicting purchase/count value scope withholds computed ROAS. Source ratios can remain in source_record or extra source metric keys for reconciliation.

## Optional checks

The helper flags duplicate or overlapping slices, mixed hierarchy levels and differing contexts. It performs no implicit row aggregation and never averages ratios. Recompute native frequency from that row's own impressions/reach; request source aggregate reach for wider scope.

`--compare-periods` checks adjacent same-entity observations within each identical filter and breakdown slice for equal-length, nonoverlapping windows and compatible context. Different filter/breakdown slices never pair; two isolated rows with different filters return no comparison. Eligible pairs require explicit finality, `context.coverage.complete: true`, no `has_next_page: true`, and relevant attribution, currency, timezone, counting/report-time and event metadata. Use an explicit empty filter collection for an unfiltered query; record filter meaning and source provenance. Coverage and `is_final` are evidence assertions, not switches to invent merely to enable deltas. Provisional or insufficiently documented comparisons return reasons for withholding automatic deltas; the agent may still discuss bounded descriptive evidence with its limits. A zero baseline has no finite percentage change. Eligibility supports descriptive arithmetic, not controlled comparability, statistical significance or cause.

### Native parent reconciliation

Use explicit reconciliation when a complete child drilldown is supposed to explain a native parent. Row indexes refer to the zero-based input `rows` array. Preserve the native parent as its own row.

```json
{
  "reconciliations": [{
    "parent_row": 0,
    "child_rows": [1, 2],
    "metrics": ["spend", "purchases", "purchase_value"],
    "children_disjoint": true,
    "coverage_complete": true,
    "absolute_tolerances": {"spend": 0.02}
  }]
}
```

The helper checks one homogeneous descendant level, exact parent IDs, compatible account/date/filter/breakdown and metric context, duplicate children, known numeric values, and the supplied disjointness/coverage assertions. A campaign can reconcile directly to ads carrying its campaign ID; account totals can reconcile to one common lower level. Mixed levels are excluded. Filters must be explicitly captured; `{}` or `[]` means an unfiltered query, while missing/null is unknown. Supplied coverage flags must be booleans. Reach, unique measures and ratios are excluded. Missing assertions or incompatible inputs withhold the sum; missing values remain unknown. The output reports `matched`, `mismatch` or `withheld`, native value, child total, exact difference, tolerance and reasons per metric. Default tolerance is zero; supply a nonzero absolute tolerance only with a recorded source/rounding reason. Never widen it just to make missing data pass.

Matching totals establish arithmetic consistency under the supplied assertions. They do not independently certify pagination, requested-ID coverage, historical identity, completeness or causality. Keep the retrieval receipt and unresolved residuals alongside the result. No account calls occur.

Reconciliation checks context per metric. Spend needs compatible currency; it does not depend on conversion attribution or purchase-counting settings. Conversion metrics need their matching attribution, reporting basis, counting mode and event identity. Therefore spend can reconcile while purchases remain withheld. Mixed campaign objectives do not prevent a valid additive account-spend check. Only the selected metric's scope is compared; unrelated optional metric definitions do not block it.

Metrics-only mode has no creative requirement. For a creative task, `--mode creative` or auto mode with creative data checks supplied copy/media identity and inspection assertions; the helper does not inspect pixels or verify assertion truth. Follow [data and media](data-and-media.md) for actual inspection. Use a new output directory; `--force` only replaces analysis.json after checks that protect input/source/media paths and output symlinks.

## Compact evidence and change drivers

For large exports, keep the complete normalized input and raw sources on disk. Use `scripts/analysis_views.py` to reduce repeated context or calculate rate drivers. It imports the existing validator; it does not fetch data, inspect media, rank winners or change accounts.

```text
python3 <skill-folder>/scripts/analysis_views.py input.json --view compact
python3 <skill-folder>/scripts/analysis_views.py input.json --view focus --fields metrics.spend,metrics.purchases,metrics.purchase_value,derived_metrics.purchase_roas,derived_metrics.cpm
python3 <skill-folder>/scripts/analysis_views.py input.json --view drivers
```

- `compact` is lossless. Repeated context/status/warnings are referenced from shared tables, all rows and payloads remain, and `expand_compact()` restores the analyzed object exactly.
- `focus` requires an explicit field list chosen for the current question. Every row remains. Identity, delivery status, selected values/nulls, unavailable statuses, warnings and comparison/reconciliation alerts remain visible. It declares omitted fields and links to the complete input by path, hash and row index. It is a projection, not a lossless format or a new full archive.
- `drivers` separates a compatible rate change into within-entity movement, mix among continuing delivery, entrants and exits. It retains source evidence and residuals against native totals. Entry/exit means delivery in the selected periods, not creation/deletion of creative. The result explains the arithmetic, not the cause.

In process, call `build_view(payload, view="compact"|"focus"|"drivers", ...)`. Focus uses `fields=["metrics.spend", ...]`; CLI supplies the exact source input path/bytes. Driver requests may be passed as `driver_request` or supplied in the input:

```json
{
  "driver_request": {
    "rate": "cpm",
    "entities_disjoint": true,
    "absence_means_zero_delivery": true,
    "maturity_mode": "as_reported",
    "before": {"label": "Earlier", "row_indices": [0, 1], "native_row": 4},
    "after": {"label": "Later", "row_indices": [2, 3], "native_row": 5}
  }
}
```

Supported rates are CPM, explicitly named all/link/outbound CTR and purchase ROAS. Select homogeneous, disjoint entity rows with compatible account, dates, filters, breakdown and rate-specific scope. Each period must have complete coverage. Differing entity sets require evidence for the explicit zero-delivery absence assertion; an omitted row from an incomplete query cannot become zero. Missing numerators/denominators and nonzero numerator with zero denominator withhold arithmetic. A zero/zero row has no invented rate. Native row indexes are optional; native differences stay separate and are never silently reconciled away.

Default `maturity_mode="final_only"` requires verified finality. Explicit `as_reported` permits dated snapshot arithmetic with unknown finality, requires timezone-aware collection timestamps on all selected rows, and labels the output provisional. It does not bypass scope, coverage, missing values or date-window checks. Use it for honest historical/current snapshot analysis rather than fabricating `is_final`.

Load only the summary and relevant contributors from a saved driver result, then inspect exact source rows for the decision. Preserve the full output. If selecting contributors for presentation, identify the selection rule and the remaining contribution; do not present a selected subset as the whole account.

## Validate workflow changes

Run `python3 -m unittest discover -s tests -v` after calculator changes. For interpretation changes, exercise the synthetic prompts in [evaluation cases](evaluation-cases.json). Record actual answers and rubric misses. These offline checks do not establish automatic skill invocation, live connector reliability, reduced retries or better ad performance; those require observed runs under the upgraded workflow.
