#!/usr/bin/env python3
"""Analyze normalized Meta metric rows; JSON only, no fetching or media reads."""
import argparse
import copy
import datetime as dt
import json
import math
from pathlib import Path
import sys

LEVELS = ('account', 'campaign', 'adset', 'ad')
CORE = ('spend', 'impressions', 'reach', 'clicks_all', 'link_clicks', 'outbound_clicks',
        'landing_page_views', 'purchases', 'purchase_value')
OPTIONAL = ('add_to_cart', 'checkout_initiated', 'leads', 'video_plays',
            'video_3s_views', 'video_thruplays', 'video_25_views', 'video_50_views',
            'video_75_views', 'video_95_views', 'video_100_views')
STATUSES = ('reported', 'unknown', 'suppressed', 'unsupported', 'failed')
SCOPE = ('currency', 'timezone', 'attribution', 'purchase_event', 'purchase_value_event',
         'objective', 'funnel', 'counting_mode', 'report_time_basis', 'metric_scopes', 'filters')
REQUIRED = ('account_id', 'currency', 'timezone', 'report_start', 'report_end', 'attribution',
            'counting_mode', 'report_time_basis')
FORMULAS = {
    'frequency': ('impressions', 'reach', 1, 'impressions per reached Meta account; native reporting row'),
    'ctr_all_pct': ('clicks_all', 'impressions', 100, 'all clicks / impressions × 100'),
    'ctr_link_pct': ('link_clicks', 'impressions', 100, 'link clicks / impressions × 100'),
    'ctr_outbound_pct': ('outbound_clicks', 'impressions', 100, 'outbound clicks / impressions × 100'),
    'cpc_all': ('spend', 'clicks_all', 1, 'spend / all clicks'),
    'cpc_link': ('spend', 'link_clicks', 1, 'spend / link clicks'),
    'cpc_outbound': ('spend', 'outbound_clicks', 1, 'spend / outbound clicks'),
    'cpm': ('spend', 'impressions', 1000, 'spend / impressions × 1000'),
    'purchase_cpa': ('spend', 'purchases', 1, 'spend / supplied purchase event count'),
    'purchase_roas': ('purchase_value', 'spend', 1, 'supplied purchase event value / spend'),
    'purchases_per_lpv_pct': ('purchases', 'landing_page_views', 100, 'purchase events / landing page views × 100; descriptive event ratio'),
    'lpv_per_outbound_pct': ('landing_page_views', 'outbound_clicks', 100, 'landing page views / outbound clicks × 100; diagnostic event ratio'),
    'add_to_cart_cpa': ('spend', 'add_to_cart', 1, 'spend / supplied add-to-cart event count'),
    'checkout_cpa': ('spend', 'checkout_initiated', 1, 'spend / supplied checkout event count'),
    'lead_cpa': ('spend', 'leads', 1, 'spend / supplied lead event count'),
    'video_3s_per_impression_pct': ('video_3s_views', 'impressions', 100, '3-second video views / impressions × 100; not unique viewers'),
    'thruplays_per_video_play_pct': ('video_thruplays', 'video_plays', 100, 'ThruPlay events / video plays × 100; source goal must be supplied'),
    'video_100_per_video_play_pct': ('video_100_views', 'video_plays', 100, '100% video views / video plays × 100; event ratio'),
}


def present(value):
    return value is not None and value != '' and value != [] and value != {}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def check_ids(value, location='input'):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith('_id') and item is not None and (not isinstance(item, str) or not item.strip()):
                raise ValueError(f'{location}.{key}: IDs must be nonempty strings, never JSON numbers')
            check_ids(item, f'{location}.{key}')
    elif isinstance(value, list):
        for i, item in enumerate(value):
            check_ids(item, f'{location}[{i}]')


def numeric(value):
    try:
        return value is None or (type(value) in (int, float) and value >= 0 and math.isfinite(value))
    except OverflowError:
        return False


def coerce(value):
    """Accept clean numeric strings like "12" or "1,234.5"; leave everything else as supplied."""
    if isinstance(value, str):
        try:
            return float(value.strip().replace(',', ''))
        except ValueError:
            return value
    return value


def window(context):
    if context.get('report_start') is None or context.get('report_end') is None:
        return None
    try:
        start, end = (dt.date.fromisoformat(context[k]) for k in ('report_start', 'report_end'))
        if end < start:
            raise ValueError('report_end precedes report_start')
        return start, end
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid reporting window: {exc}') from exc


def derived(metrics, context):
    values, status = {}, {}
    for name, (num, den, multiplier, _) in FORMULAS.items():
        # Optional formulas do not appear unless their event count was requested/supplied.
        if num in OPTIONAL and num not in metrics or den in OPTIONAL and den not in metrics:
            continue
        a, b = metrics.get(num), metrics.get(den)
        value, state = None, 'unknown'
        if a is not None and b is not None:
            if b == 0:
                state = 'undefined_zero_denominator'
            else:
                value = a / b * multiplier
                if math.isfinite(value):
                    state = 'computed'
                else:
                    value, state = None, 'undefined_nonfinite_result'
        if name == 'purchase_roas':
            event, value_event = context.get('purchase_event'), context.get('purchase_value_event')
            if present(event) and present(value_event) and event != value_event:
                value, state = None, 'withheld_event_value_scope_mismatch'
            elif not present(event) or not present(value_event):
                state = 'computed_scope_unverified' if value is not None else state
        values[name], status[name] = value, state
    return values, status


def creative_flags(row, warnings):
    if not isinstance(row.get('copy', {}), dict) or not isinstance(row.get('media', []), list):
        raise ValueError('copy must be an object and media must be an array')
    for key in ('creative_id', 'adset_id'):
        if not present(row.get(key)):
            warnings.append(f'Missing creative identity: {key}')
    statuses = row.get('copy_status', {})
    if not isinstance(statuses, dict):
        raise ValueError('copy_status must be an object')
    for key, state in statuses.items():
        if key not in ('body', 'title', 'description', 'cta', 'destination') or state not in ('reported', 'unused', 'unknown'):
            raise ValueError(f'Invalid copy_status entry: {key}')
        value = row.get('copy', {}).get(key)
        if (state == 'unused' and value != '') or (state == 'reported' and (not isinstance(value, str) or not value)) or (state == 'unknown' and value is not None):
            raise ValueError(f'Contradictory copy value/status: {key} ({state})')
    for key in ('body', 'title', 'description', 'cta', 'destination'):
        if not present(row.get('copy', {}).get(key)) and statuses.get(key) != 'unused':
            warnings.append(f'Missing copy: {key}')
    if not row.get('media'):
        warnings.append('No media supplied for creative review')
    if row.get('identity_status') != 'historical_verified':
        warnings.append('Historical creative identity unverified; current media may differ from reporting period')
    for flag in ('dynamic_creative', 'edited_during_window'):
        if flag in row and type(row[flag]) is not bool:
            raise ValueError(f'{flag} must be a boolean')
    if (row.get('dynamic_creative') or row.get('edited_during_window')) and row.get('creative_coverage') != 'complete':
        warnings.append('Edited or dynamic creative: variant/time coverage incomplete')
    for asset in row.get('media', []):
        if not isinstance(asset, dict) or asset.get('kind') not in ('image', 'video_frame', 'video'):
            raise ValueError('Media entry requires kind: image, video_frame or video')
        if asset.get('inspection_status') not in ('inspected', 'uninspected', 'thumbnail_only'):
            raise ValueError('Media entry requires inspection_status')
        if asset['inspection_status'] != 'inspected':
            warnings.append(f'Media {asset.get("asset_id", "unknown")}: {asset["inspection_status"]}')
        if asset['kind'] != 'image' and asset.get('coverage') != 'complete':
            warnings.append('Video coverage incomplete; frames do not establish full motion/audio review')


def period_comparisons(rows):
    """Explicit opt-in, adjacent chronological rows only, no guessed comparability."""
    groups = {}
    for index, row in enumerate(rows):
        key = (row['account_id'], row['level'], row['entity_id'], canonical(row.get('breakdown')),
               canonical(row['context'].get('filters')))
        groups.setdefault(key, []).append((index, row))
    comparisons = []
    for identity, entries in groups.items():
        entries.sort(key=lambda entry: (entry[1]['context'].get('report_start') or '', entry[0]))
        for (before_index, before), (after_index, after) in zip(entries, entries[1:]):
            reasons = []
            bw, aw = window(before['context']), window(after['context'])
            if bw is None or aw is None:
                reasons.append('reporting_window_unknown')
            elif bw[1] >= aw[0]:
                reasons.append('reporting_windows_overlap')
            elif bw[1] - bw[0] != aw[1] - aw[0]:
                reasons.append('reporting_window_lengths_differ')
            # Finality is explicit: old-looking dates alone cannot establish attribution maturity.
            if (before['context'].get('is_final') is not True or after['context'].get('is_final') is not True
                    or before['context'].get('provisional') is True or after['context'].get('provisional') is True):
                reasons.append('reporting_finality_unverified_or_provisional')
            for label, row in (('before', before), ('after', after)):
                coverage = row['context'].get('coverage')
                if not isinstance(coverage, dict) or coverage.get('complete') is not True:
                    reasons.append(f'comparison_coverage_unverified:{label}')
                elif coverage.get('has_next_page') is True:
                    reasons.append(f'comparison_coverage_incomplete:{label}')
            if any('filters' not in row['context'] or row['context']['filters'] is None for row in (before, after)):
                reasons.append('comparison_filters_unknown')
            for key in SCOPE:
                a, b = before['context'].get(key), after['context'].get(key)
                if canonical(a) != canonical(b):
                    reasons.append(f'context_differs:{key}')
            required_scope = ['currency', 'timezone', 'attribution', 'counting_mode', 'report_time_basis']
            if before['metrics'].get('purchases') is not None or after['metrics'].get('purchases') is not None:
                required_scope.append('purchase_event')
            if before['metrics'].get('purchase_value') is not None or after['metrics'].get('purchase_value') is not None:
                required_scope.append('purchase_value_event')
            for key in required_scope:
                if not present(before['context'].get(key)) or not present(after['context'].get(key)):
                    reasons.append(f'comparison_context_unknown:{key}')
            for key in ('campaign_id', 'adset_id', 'ad_id', 'breakdown'):
                if canonical(before.get(key)) != canonical(after.get(key)):
                    reasons.append(f'identity_or_breakdown_differs:{key}')
            delta = {}
            if not reasons:
                for group in ('metrics', 'derived_metrics'):
                    for key in before[group].keys() | after[group].keys():
                        a, b = before[group].get(key), after[group].get(key)
                        if type(a) not in (int, float) or type(b) not in (int, float):
                            delta[f'{group}.{key}'] = {'absolute': None, 'percent': None, 'status': 'unavailable'}
                            continue
                        change = b - a
                        percent = change / a * 100 if a else None
                        state = 'computed' if a else 'percent_undefined_zero_baseline'
                        if not math.isfinite(change) or percent is not None and not math.isfinite(percent):
                            change, percent, state = None, None, 'undefined_nonfinite_result'
                        delta[f'{group}.{key}'] = {'absolute': change, 'percent': percent, 'status': state}
            comparisons.append({'account_id': identity[0], 'level': identity[1], 'entity_id': identity[2],
                                'before_row': before_index, 'after_row': after_index,
                                'eligible': not reasons, 'flags': reasons, 'deltas': delta})
    return comparisons


# Only event counts and monetary totals with compatible scopes can be reconciled.
# Reach, frequency, unique metrics, ratios and arbitrary custom metrics are excluded.
ADDITIVE = frozenset(('spend', 'impressions', 'clicks_all', 'link_clicks',
                     'outbound_clicks', 'landing_page_views', 'purchases',
                     'purchase_value', 'add_to_cart', 'checkout_initiated', 'leads'))


def reconciliations(rows, requests):
    """Compare explicitly complete, disjoint child slices to a native parent.

    Assertions describe supplied evidence, not proof of retrieval completeness.
    Unknown/incompatible rows withhold totals. A mismatch never certifies coverage.
    """
    if not isinstance(requests, list):
        raise ValueError('reconciliations must be an array')
    results = []
    for request in requests:
        if not isinstance(request, dict):
            raise ValueError('Each reconciliation must be an object')
        parent_index, child_indices = request.get('parent_row'), request.get('child_rows')
        if type(parent_index) is not int or not 0 <= parent_index < len(rows):
            raise ValueError('Reconciliation parent_row must be a valid row index')
        if (not isinstance(child_indices, list) or not child_indices
                or any(type(i) is not int or not 0 <= i < len(rows) for i in child_indices)
                or len(set(child_indices)) != len(child_indices) or parent_index in child_indices):
            raise ValueError('Reconciliation child_rows requires distinct valid child indices')
        metrics = request.get('metrics')
        if (not isinstance(metrics, list) or not metrics
                or any(not isinstance(key, str) or key not in ADDITIVE for key in metrics)
                or len(set(metrics)) != len(metrics)):
            raise ValueError('Reconciliation metrics must be distinct supported additive metrics; no reach or ratios')
        tolerances = request.get('absolute_tolerances', {})
        if (not isinstance(tolerances, dict) or any(key not in metrics or value is None or not numeric(value)
                                                  for key, value in tolerances.items())):
            raise ValueError('absolute_tolerances must contain finite nonnegative values for requested metrics')
        for assertion in ('children_disjoint', 'coverage_complete'):
            if assertion in request and type(request[assertion]) is not bool:
                raise ValueError(f'{assertion} must be boolean')
        parent = rows[parent_index]
        children = [rows[i] for i in child_indices]
        flags = []
        for assertion in ('children_disjoint', 'coverage_complete'):
            if request.get(assertion) is not True:
                flags.append(f'{assertion}_unverified')
        child_levels = {child['level'] for child in children}
        if (len(child_levels) != 1 or any(LEVELS.index(child['level']) <= LEVELS.index(parent['level']) for child in children)):
            flags.append('children_must_be_homogeneous_descendants')
        if any('filters' not in row['context'] or row['context']['filters'] is None for row in [parent] + children):
            flags.append('filters_unknown')
        parent_field = {'account': 'account_id', 'campaign': 'campaign_id', 'adset': 'adset_id', 'ad': 'ad_id'}[parent['level']]
        if any(child.get(parent_field) != parent['entity_id'] for child in children):
            flags.append('parent_membership_unverified')
        if len({child['entity_id'] for child in children}) != len(children):
            flags.append('repeated_child_entity')
        for child in children:
            if child['account_id'] != parent['account_id']:
                flags.append('account_differs')
            if window(parent['context']) is None or window(child['context']) != window(parent['context']):
                flags.append('reporting_window_differs_or_unknown')
            if canonical(child.get('breakdown')) != canonical(parent.get('breakdown')):
                flags.append('breakdown_differs')
            for key in ('timezone', 'filters'):
                if canonical(child['context'].get(key)) != canonical(parent['context'].get(key)):
                    flags.append(f'context_differs:{key}')
            # Explicitly incomplete row retrieval overrides request-level assertions.
            for row in (parent, child):
                coverage = row['context'].get('coverage', {})
                if isinstance(coverage, dict) and (coverage.get('complete') is False or coverage.get('has_next_page') is True):
                    flags.append('row_coverage_incomplete')
        checks = {}
        for metric in metrics:
            metric_flags = list(dict.fromkeys(flags))
            required_scope = ['timezone']
            if metric in ('spend', 'purchase_value'):
                required_scope.append('currency')
            if metric not in ('spend', 'impressions', 'clicks_all', 'link_clicks', 'outbound_clicks'):
                required_scope.extend(('attribution', 'report_time_basis', 'counting_mode'))
            if metric == 'purchases':
                required_scope.append('purchase_event')
            if metric == 'purchase_value':
                required_scope.append('purchase_value_event')
            for key in required_scope:
                if any(not present(row['context'].get(key)) for row in [parent] + children):
                    metric_flags.append(f'context_unknown:{key}')
                if any(canonical(child['context'].get(key)) != canonical(parent['context'].get(key)) for child in children):
                    metric_flags.append(f'context_differs:{key}')
            metric_scopes = [row['context'].get('metric_scopes') for row in [parent] + children]
            selected_scopes = [scope.get(metric) if isinstance(scope, dict) else None for scope in metric_scopes]
            if metric in ('add_to_cart', 'checkout_initiated', 'leads', 'landing_page_views') and any(not present(scope) for scope in selected_scopes):
                metric_flags.append(f'metric_scope_unknown:{metric}')
            if len({canonical(scope) for scope in selected_scopes}) > 1:
                metric_flags.append(f'metric_scope_differs:{metric}')
            values = [child['metrics'].get(metric) for child in children]
            parent_value = parent['metrics'].get(metric)
            if parent_value is None or any(value is None for value in values):
                metric_flags.append('metric_unavailable')
            total, difference, status = None, None, 'withheld'
            tolerance = tolerances.get(metric, 0)
            if not metric_flags:
                try:
                    total = math.fsum(values)
                    difference = total - parent_value
                    if not math.isfinite(total) or not math.isfinite(difference):
                        raise OverflowError
                    status = 'matched' if abs(difference) <= tolerance else 'mismatch'
                except OverflowError:
                    total, difference = None, None
                    metric_flags.append('nonfinite_total')
            checks[metric] = {'parent_value': parent_value, 'child_total': total,
                              'difference': difference, 'absolute_tolerance': tolerance,
                              'status': status, 'flags': metric_flags}
        statuses = {check['status'] for check in checks.values()}
        status = 'matched' if statuses == {'matched'} else 'mismatch' if 'mismatch' in statuses else 'withheld'
        results.append({'parent_row': parent_index, 'child_rows': child_indices,
                        'status': status, 'metrics': checks,
                        'limitations': 'Arithmetic reconciliation of supplied assertions; matching totals do not prove complete retrieval or causality.'})
    return results


def validate_requested_scope(payload, container, version):
    """Reject an out-of-scope packet before computing any row metrics."""
    if 'requested_scope' not in payload:
        return
    scope = payload['requested_scope']
    if (not isinstance(scope, dict) or scope.get('level') not in LEVELS
            or not isinstance(scope.get('entity_id'), str) or not scope['entity_id'].strip()):
        raise ValueError('requested_scope requires a supported level and exact string entity_id')
    target_level, target_id = scope['level'], scope['entity_id']
    membership_field = {'account': 'account_id', 'campaign': 'campaign_id', 'adset': 'adset_id', 'ad': 'ad_id'}[target_level]
    for index, row in enumerate(payload[container]):
        if not isinstance(row, dict):
            raise ValueError(f'{container}[{index}] must be an object')
        level = 'ad' if version == 1 else row.get('level')
        identity = row.get('ad_id') if version == 1 else row.get('entity_id')
        member = row.get(membership_field)
        if target_level == 'account':
            row_context = row.get('context', {})
            if not isinstance(row_context, dict):
                raise ValueError(f'{container}[{index}].context must be an object')
            member = row.get('account_id') or row_context.get('account_id') or payload['context'].get('account_id')
        allowed = (level == target_level and identity == target_id) or (
            level in LEVELS and LEVELS.index(level) > LEVELS.index(target_level) and member == target_id)
        if not allowed:
            raise ValueError(f'{container}[{index}] {level} {identity!r} is outside requested_scope '
                             f'{target_level} {target_id!r} or lacks matching {membership_field}; '
                             'keep external context/comparators in a separate packet')


def analyze(payload, mode=None, compare_periods=None):
    if not isinstance(payload, dict) or type(payload.get('schema_version')) is not int or payload['schema_version'] not in (1, 2):
        raise ValueError('Expected schema_version: 1 or 2')
    canonical(payload)  # Reject non-JSON/nonfinite source data even for direct Python callers.
    version = payload['schema_version']
    container = 'ads' if version == 1 else 'rows'
    if not isinstance(payload.get('context'), dict) or not isinstance(payload.get(container), list):
        raise ValueError(f'context must be an object and {container} must be an array')
    check_ids(payload)
    validate_requested_scope(payload, container, version)
    effective_mode = mode or payload.get('mode', 'auto')
    if effective_mode not in ('auto', 'metrics', 'creative'):
        raise ValueError('mode must be auto, metrics or creative')
    if compare_periods is None:
        compare_periods = payload.get('compare_periods', False)
    if type(compare_periods) is not bool:
        raise ValueError('compare_periods must be boolean')
    rows, seen, windows = [], set(), {}
    for index, source in enumerate(payload[container]):
        if not isinstance(source, dict) or not isinstance(source.get('context', {}), dict):
            raise ValueError(f'{container}[{index}] must be an object with object context')
        row = copy.deepcopy(source)
        if version == 1:
            row['level'], row['entity_id'] = 'ad', row.get('ad_id')
        if row.get('level') not in LEVELS or not isinstance(row.get('entity_id'), str) or not row['entity_id'].strip():
            raise ValueError(f'{container}[{index}] requires level account/campaign/adset/ad and string entity_id')
        context = {**payload['context'], **row.get('context', {})}
        if 'filters' in context and context['filters'] is not None and not isinstance(context['filters'], (dict, list)):
            raise ValueError('filters must be an object, array or null')
        if 'coverage' in context and context['coverage'] is not None:
            if not isinstance(context['coverage'], dict):
                raise ValueError('coverage must be an object or null')
            for flag in ('complete', 'has_next_page'):
                if flag in context['coverage'] and type(context['coverage'][flag]) is not bool:
                    raise ValueError(f'coverage.{flag} must be boolean when supplied')
        account_ids = [v for v in (payload['context'].get('account_id'), row.get('account_id'),
                                   row.get('context', {}).get('account_id')) if present(v)]
        if len(set(account_ids)) > 1:
            raise ValueError('Account identity inconsistent between payload context and row')
        if not account_ids:
            raise ValueError('Each row needs account_id, directly or in context')
        account_id = account_ids[0]
        context['account_id'] = account_id
        level_field = {'account': 'account_id', 'campaign': 'campaign_id', 'adset': 'adset_id', 'ad': 'ad_id'}[row['level']]
        if present(row.get(level_field)) and row[level_field] != row['entity_id']:
            raise ValueError(f'entity_id must match {level_field}')
        child_fields = {'account': ('campaign_id', 'adset_id', 'ad_id'),
                        'campaign': ('adset_id', 'ad_id'), 'adset': ('ad_id',), 'ad': ()}
        if any(present(row.get(key)) for key in child_fields[row['level']]):
            raise ValueError('Native parent row must not carry a child entity ID; retain children as separate rows')
        if row['level'] == 'account' and row['entity_id'] != account_id:
            raise ValueError('Account entity_id must match account_id')
        row[level_field] = row['entity_id']
        raw_metrics = row.get('metrics', {})
        if not isinstance(raw_metrics, dict):
            raise ValueError('metrics must be an object')
        warnings = [f'Missing context: {key}' for key in REQUIRED if not present(context.get(key))]
        metrics = {key: None for key in CORE}
        # Clean numeric strings are coerced; anything unparseable is flagged and excluded, never fatal.
        # Scalar numeric extra metrics remain usable; structured source fields are preserved separately.
        for key, value in raw_metrics.items():
            if key in CORE + OPTIONAL:
                value = coerce(value)
                if not numeric(value):
                    warnings.append(f'Unparseable metric: {key}={raw_metrics[key]!r}; excluded from calculations')
                    value = None
                metrics[key] = value
            elif numeric(value):
                metrics[key] = value
        status_map = row.get('metric_status', {})
        if not isinstance(status_map, dict):
            raise ValueError('metric_status must be an object')
        for key, state in status_map.items():
            if state not in STATUSES or key not in set(metrics) | set(OPTIONAL):
                raise ValueError(f'Invalid metric_status entry: {key}')
            if state == 'reported' and metrics.get(key) is None:
                raise ValueError(f'Metric marked reported has no numeric value: {key}')
            if state != 'reported':
                metrics[key] = None
                warnings.append(f'Metric unavailable: {key} ({state}); excluded from calculations')
        source_status = {key: status_map.get(key, 'reported' if value is not None else 'unknown') for key, value in metrics.items()}
        actual_window = window(context)
        if actual_window is None:
            warnings.append('Reporting window unavailable; overlap cannot be checked')
        if present(context.get('purchase_event')) and present(context.get('purchase_value_event')) and context['purchase_event'] != context['purchase_value_event']:
            warnings.append('Purchase event/value scope mismatch: purchase_roas withheld')
        if metrics.get('purchases') is not None and not present(context.get('purchase_event')):
            warnings.append('Purchase event scope unverified')
        if metrics.get('purchase_value') is not None and not present(context.get('purchase_value_event')):
            warnings.append('Purchase value event scope unverified')
        if context.get('is_final') is False or context.get('provisional') is True:
            warnings.append('Provisional reporting window; attribution may change')
        if metrics.get('reach') == 0 and metrics.get('impressions', 0):
            warnings.append('Positive impressions with zero reach; source consistency requires review')
        spend, impressions, purchases = (metrics.get(k) for k in ('spend', 'impressions', 'purchases'))
        if spend and impressions == 0:
            warnings.append('Broken row: spend with zero impressions')
        elif spend and all(metrics.get(k) is None for k in CORE if k != 'spend'):
            warnings.append('Broken row: only spend supplied; delivery and results missing')
        if purchases and metrics.get('purchase_value') is None:
            warnings.append('Purchase value missing: purchase_roas unavailable')
        low_volume = purchases is not None and purchases < 10
        if low_volume and purchases and spend:
            warnings.append(f'Low volume: {purchases:g} purchases on {spend:g} spend; ROAS/CPA are not a verdict')
        creative = row['level'] == 'ad' and (effective_mode == 'creative' or effective_mode == 'auto' and any(present(row.get(k)) for k in ('copy', 'media', 'creative_id', 'identity_status', 'dynamic_creative')))
        if creative:
            creative_flags(row, warnings)
        values, states = derived(metrics, context)
        breakdown = row.get('breakdown', context.get('breakdown'))
        identity = canonical((account_id, row['level'], row['entity_id'], context.get('report_start'),
                              context.get('report_end'), breakdown,
                              {key: row.get(key) for key in ('campaign_id', 'adset_id', 'ad_id')},
                              {key: context.get(key) for key in SCOPE}))
        if identity in seen:
            raise ValueError(f'Duplicate entity/window/scope/breakdown row: {row["entity_id"]}')
        seen.add(identity)
        row.update(account_id=account_id, context=context, source_metrics=copy.deepcopy(raw_metrics),
                   metrics=metrics, metric_status=source_status, derived_metrics=values,
                   derived_status=states, warnings=warnings, creative_review_requested=creative,
                   low_volume=low_volume, counts={k: metrics.get(k) for k in ('spend', 'impressions', 'purchases', 'purchase_value')})
        if breakdown is not None:
            row['breakdown'] = copy.deepcopy(breakdown)
        key = (account_id, row['level'], row['entity_id'])
        if actual_window:
            start, end = actual_window
            for prior, pstart, pend in windows.get(key, []):
                if start <= pend and pstart <= end:
                    flag = 'Same-entity reporting windows overlap; no aggregation performed'
                    if flag not in warnings:
                        warnings.append(flag)
                    if flag not in prior['warnings']:
                        prior['warnings'].append(flag)
            windows.setdefault(key, []).append((row, start, end))
        rows.append(row)
    differing = [key for key in SCOPE if len({canonical(r['context'].get(key)) for r in rows}) > 1]
    flags = []
    if len({r['level'] for r in rows}) > 1:
        flags.append('Mixed hierarchy levels retained separately; parent/child metrics must not be added together')
    if differing:
        flags.append('Comparison context differs across rows: ' + ', '.join(differing))
    # Rows off the most common attribution window are flagged and excluded from comparative verdicts.
    windows_used = [canonical(r['context'].get('attribution')) for r in rows]
    common = max(set(windows_used), key=windows_used.count) if windows_used else None
    tie = windows_used.count(common) * 2 <= len(windows_used) if common else False
    for row, used in zip(rows, windows_used):
        row['attribution_mixed'] = len(set(windows_used)) > 1 and (tie or used != common)
        if row['attribution_mixed']:
            row['warnings'].append(f'Mixed attribution: {row["context"].get("attribution")!r} differs from other rows; excluded from comparisons')
    result = {'schema_version': 2, 'input_schema_version': version, 'context': copy.deepcopy(payload['context']),
              'mode': effective_mode, 'rows': rows, 'flags': flags,
              'metric_definitions': {key: {'numerator': num, 'denominator': den, 'multiplier': mult, 'description': desc}
                                     for key, (num, den, mult, desc) in FORMULAS.items()},
              'limitations': ['No implicit aggregation, averaged ratios, causal diagnosis, rankings or statistical confidence; explicit reconciliation only.',
                              'Native row ratios use its supplied source totals; reach is not additive across children or periods.',
                              'No network requests or media file reads; creative inspection statuses are supplied evidence.',
                              'Extra source metrics are preserved without guessing their event meaning or units.']}
    if 'requested_scope' in payload:
        result['requested_scope'] = copy.deepcopy(payload['requested_scope'])
    if compare_periods:
        result['period_comparisons'] = period_comparisons(rows)
    if 'reconciliations' in payload:
        result['reconciliations'] = reconciliations(rows, payload['reconciliations'])
    # Preserve payload-level provenance/custom metadata without letting it overwrite analyzed output.
    result['source_metadata'] = {key: copy.deepcopy(value) for key, value in payload.items()
                                 if key not in ('schema_version', 'context', container, 'mode', 'compare_periods', 'reconciliations', 'requested_scope')}
    if version == 1:
        result['ads'] = rows  # v1 container adapter; values use the v2 normalized metric keys.
    return result


def local_path(raw, root):
    if not isinstance(raw, str) or not raw or '://' in raw or raw.startswith('data:') or '\x00' in raw:
        raise ValueError('Only local filesystem paths are supported')
    path = Path(raw).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def persist(analysis, input_path, output, force=False):
    # Output is a directory with one generated file. Reject all source/symlink aliases first.
    if output.is_symlink():
        raise ValueError('Output directory must not be a symlink')
    output = output.resolve()
    target = output / 'analysis.json'
    protected = {input_path.resolve()}
    for row in analysis['rows']:
        paths = [row['context'].get('source_path'), row.get('source_path')]
        if isinstance(row.get('media'), list):
            paths.extend(asset.get('path') for asset in row['media'] if isinstance(asset, dict))
        for raw in paths:
            try:
                protected.add(local_path(raw, input_path.parent))
            except ValueError:
                pass
    if target.is_symlink() or target.resolve() in protected:
        raise ValueError('Output would replace an input/source/media snapshot or symlink')
    if output.exists() and not force:
        raise ValueError('Output directory exists; use a new directory or --force')
    if output.exists() and not output.is_dir():
        raise ValueError('Output must be a directory')
    # A hardlinked source is also protected, even though resolve() does not expose the alias.
    if target.exists():
        for path in protected:
            if path.exists() and target.samefile(path):
                raise ValueError('Output is a hardlink to an input/source/media snapshot')
    output.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(analysis, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Normalized schema v1 ads or v2 rows JSON')
    parser.add_argument('--mode', choices=('auto', 'metrics', 'creative'))
    parser.add_argument('--compare-periods', action='store_true', default=None, help='Check adjacent same-entity periods; withhold incompatible/provisional comparisons')
    parser.add_argument('--out', type=Path, help='Optional directory; writes analysis.json only')
    parser.add_argument('--force', action='store_true', help='Replace generated analysis.json after source safety checks')
    args = parser.parse_args()
    try:
        input_path = args.input.resolve()
        payload = json.loads(input_path.read_text(encoding='utf-8'), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'Invalid JSON number: {value}')))
        analysis = analyze(payload, mode=args.mode, compare_periods=args.compare_periods)
        if args.out is not None:
            persist(analysis, input_path, args.out, force=args.force)
        print(json.dumps(analysis, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
