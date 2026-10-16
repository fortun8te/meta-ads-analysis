# Data and media

## Source contract

Use the existing authorized connection or supplied export. Discover its current schema before constructing queries. An official API reference does not guarantee the connector exposes the same fields. Validate level, aliases, field types, filter operators and enum values. Preserve raw responses and their query parameters locally. Cross-check suspicious field descriptions against primary documentation; a schema can be valid while its explanatory text is wrong.

Record account, timezone, currency, level, objective/optimization event, date range, collection time, attribution model/window/counting mode, effective report-time basis, filters, breakdowns, API/connector version when available and coverage. A requested setting and an effective returned setting are separate facts. Missing attribution is a comparison limit, not a reason to abandon all descriptive work.

For exports, preserve original files and map columns explicitly. Store IDs as strings before parsing; reject rounded spreadsheet identifiers as identity proof. Record locale, units, date parsing and blank-cell semantics. API amount objects may have a value and currency; raw budget minor units are different from reporting spend units. A source summary row is not another ad. Do not silently truncate full copy for a compact report.

## Retrieval and inspection

Use only the capabilities exposed by the current authorized source. Tool names, limits, media fields and field availability change; verify schemas instead of copying query arguments from another connector.

1. Resolve the authorized account and requested entity. Names locate candidates; exact IDs establish identity. Fetch native outcome totals for explicit dates, then targeted diagnostic metrics and child rows only where useful. Query fields at their supported level.
2. Inspect completion state. Follow read-only continuations and pagination within the same scope. Check returned IDs/date slices, failed batches and active/paused/archived filters. Reconcile compatible additive child totals against the native parent. Record residuals; a successful last page alone does not prove full retrieval. Repair detected omissions with bounded ID/date requests.
3. Retrieve creative only when the question requires it. Deduplicate creative IDs. Preserve full body, title, description, CTA, destination, story IDs and media identity. Post-backed records can omit copy or full media; use another authorized source or label the record incomplete.
4. Resolve full-size images, video renditions and ordered carousel cards through targeted metadata lookups. A thumbnail, download URL and original source have different coverage. Respect current limits and field names. Do not infer nonexistence from a missing optional field.
5. Open actual media with suitable viewers. Validate file type/dimensions and retain checksum/source identity. A URL or successful save is not inspection. For video, inspect timestamped opening/body/ending frames, speech/audio and overlay changes; record sampled coverage. A transcript alone cannot establish visual coverage.

Metrics-only analysis needs no creative fetch. No connector is bundled with this skill: supplied exports are a supported route. See [diagnosis](diagnosis.md) for choosing the next read and stopping unresolved retrieval retries.

## Variants and missing coverage

Dynamic, flexible, catalog and placement-customized ads can use multiple combinations. Inspect available asset feeds, customization rules, catalog context and placement previews only through exposed authorized tools. If these are missing, label variant or delivery coverage incomplete. A primary image is a source asset, not proof of the final rendered ad. Ad-level purchases do not identify the converting dynamic image/text combination. Carousel asset reporting may attribute in-card elements to first-card assets; keep reporting scope intact.

Save the current creative snapshot and ad modification time. When a change might fall inside the results window, check available history or matching dated assets. Otherwise label historical identity unverified. Ad creation, asset upload, report start, collection and first delivery are different dates.

For CDN expiry/403/404, refresh targeted media metadata once and retry once. Preserve failures and mark uninspected if unresolved. Repair a local transport/certificate issue through the system's valid trust store; do not disable verification. Do not broaden permissions, scrape a private session or switch accounts to fill a media gap. Unknown video IDs or null HD URLs mean unavailable to this lookup, not proof the video does not exist.

## Efficient reuse

Cache raw response snapshots by query and collection time. Cache immutable media by account + image hash/video ID plus rendition and checksum. Cache visual notes by checksum + inspection scope. Expiring URLs are locators, not identity. Reuse an unchanged asset's visual notes while refreshing results and current creative associations. Retain prior metrics when checking revisions; never relabel a dated export as live. Batch independent reads and deduplicate IDs. Expand the sample only when unresolved coverage or a decision requires it.
