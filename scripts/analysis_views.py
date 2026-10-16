#!/usr/bin/env python3
"""Optional lossless compact view and descriptive rate decomposition of Meta rows."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

if __package__:
    from .analyze_meta import analyze, canonical, present, window, LEVELS, CORE, OPTIONAL, FORMULAS
else:
    from analyze_meta import analyze, canonical, present, window, LEVELS, CORE, OPTIONAL, FORMULAS

RATES = {
    'cpm': ('spend', 'impressions', 1000),
    'ctr_link_pct': ('link_clicks', 'impressions', 100),
    'ctr_outbound_pct': ('outbound_clicks', 'impressions', 100),
    'ctr_all_pct': ('clicks_all', 'impressions', 100),
    'purchase_roas': ('purchase_value', 'spend', 1),
}
INTERN = ('context', 'warnings', 'metric_status', 'derived_status')


def compact_analysis(analysis):
    """Factor repeated dictionaries; preserve all evidence, including raw/media fields.

    No truncation, ranking or sampling. References point to values in this document.
    Row envelopes avoid collisions with arbitrary source field names.
    """
    pools, lookups = {key: [] for key in INTERN}, {key: {} for key in INTERN}
    rows = []
    for row in analysis['rows']:
        data, refs = {}, {}
        for key, value in row.items():
            if key not in INTERN:
                data[key] = copy.deepcopy(value)
                continue
            signature = canonical(value)
            if signature not in lookups[key]:
                lookups[key][signature] = len(pools[key])
                pools[key].append(copy.deepcopy(value))
            refs[key] = lookups[key][signature]
        rows.append({'data': data, 'refs': refs})
    aliases = {'ads': 'rows'} if 'ads' in analysis and analysis['ads'] == analysis['rows'] else {}
    metadata = {key: copy.deepcopy(value) for key, value in analysis.items()
                if key != 'rows' and key not in aliases}
    return {'view_version': 1, 'view': 'compact', 'metadata': metadata,
            'pools': pools, 'rows': rows, 'aliases': aliases,
            'omitted_payloads': [],
            'coverage': {'input_rows': len(analysis['rows']), 'output_rows': len(rows),
                         'sampled': False},
            'instructions': 'Each row is data plus the named pool values at refs indices. No raw/media payloads or evidence omitted.'}


def expand_compact(view):
    """Restore the original analyzed object, useful for losslessness verification."""
    result = copy.deepcopy(view['metadata'])
    result['rows'] = []
    for row in view['rows']:
        restored = copy.deepcopy(row['data'])
        for key, index in row['refs'].items():
            restored[key] = copy.deepcopy(view['pools'][key][index])
        result['rows'].append(restored)
    for alias, key in view.get('aliases', {}).items():
        result[alias] = copy.deepcopy(result[key])
    return result


def source_reference(payload, source_path=None, source_bytes=None):
    """Hash actual serialized input when available, otherwise canonical JSON."""
    if source_bytes is not None:
        if not isinstance(source_bytes, bytes) or canonical(json.loads(source_bytes)) != canonical(payload):
            raise ValueError('source_bytes must encode exactly the supplied payload')
        serialized, hash_basis = source_bytes, 'exact_input_bytes'
    else:
        serialized, hash_basis = canonical(payload).encode('utf-8'), 'canonical_json_utf8'
    return {'path': str(source_path) if source_path is not None else None,
              'sha256': hashlib.sha256(serialized).hexdigest(), 'hash_basis': hash_basis,
              'row_container': 'ads' if payload['schema_version'] == 1 else 'rows'}


def focus_analysis(analysis, payload, fields, source_path=None, source_bytes=None):
    """Explicit field projection retaining every row and all analysis alerts.

    This is not lossless. Hash/index locators and omission counts identify the
    original input required to retrieve excluded media, raw records and metrics.
    """
    if not isinstance(fields, list) or not fields or any(not isinstance(f, str) for f in fields) or len(set(fields)) != len(fields):
        raise ValueError('focus requires a nonempty distinct fields list')
    known_metrics = set(CORE + OPTIONAL) | {key for row in analysis['rows'] for key in row['metrics']}
    for field in fields:
        parts = field.split('.')
        if len(parts) != 2 or parts[0] not in ('metrics', 'derived_metrics') or parts[1] not in (known_metrics if parts[0] == 'metrics' else FORMULAS):
            raise ValueError(f'Unsupported focus field: {field}')
    source = source_reference(payload, source_path, source_bytes)
    pool_names = ('context', 'warnings', 'metric_alerts', 'derived_alerts', 'omissions')
    pools, lookups = {name: [] for name in pool_names}, {name: {} for name in pool_names}
    projected, totals = [], {'metric_fields': 0, 'derived_metric_fields': 0, 'source_metric_fields': 0, 'payload_fields': 0}
    selected_metrics = {field.split('.')[1] for field in fields if field.startswith('metrics.')}
    selected_derived = {field.split('.')[1] for field in fields if field.startswith('derived_metrics.')}
    for index, row in enumerate(analysis['rows']):
        # Keep identity, original scope, source locators and arbitrary explicit alerts.
        retained = {key: copy.deepcopy(value) for key, value in row.items()
                    if key.endswith('_id') or key in ('id', 'level', 'name', 'breakdown', 'source', 'provenance',
                                                      'source_path', 'collected_at', 'created_time', 'updated_time', 'identity_status',
                                                      'dynamic_creative', 'edited_during_window', 'creative_coverage',
                                                      'effective_status', 'configured_status', 'status',
                                                      'flags', 'creative_review_requested')}
        values = {}
        for field in fields:
            group, key = field.split('.')
            status_group = 'metric_status' if group == 'metrics' else 'derived_status'
            entry = {'value': row[group].get(key), 'status': row[status_group].get(key, 'unknown')}
            if group == 'metrics' and key in row['source_metrics']:
                entry['source_value'] = copy.deepcopy(row['source_metrics'][key])
            values[field] = entry
        excluded = sorted(set(row) - set(retained) - {'context', 'warnings', 'metrics', 'derived_metrics',
                                                       'metric_status', 'derived_status', 'source_metrics'})
        omission = {'metric_fields': sorted(set(row['metrics']) - selected_metrics),
                    'derived_metric_fields': sorted(set(row['derived_metrics']) - selected_derived),
                    'source_metric_fields': sorted(set(row['source_metrics']) - selected_metrics),
                    'payload_fields': excluded}
        for key in totals:
            totals[key] += len(omission[key])
        pooled = {'context': row['context'], 'warnings': row['warnings'],
                  'metric_alerts': {key: state for key, state in row['metric_status'].items() if state != 'reported'},
                  'derived_alerts': {key: state for key, state in row['derived_status'].items() if state != 'computed'},
                  'omissions': omission}
        refs = {}
        for key, value in pooled.items():
            signature = canonical(value)
            if signature not in lookups[key]:
                lookups[key][signature] = len(pools[key])
                pools[key].append(copy.deepcopy(value))
            refs[key] = lookups[key][signature]
        projected.append({'identity_and_provenance': retained, 'input_row_index': index,
                          'values': values, 'refs': refs})
    metadata = {key: copy.deepcopy(value) for key, value in analysis.items()
                if key not in ('rows', 'ads', 'metric_definitions')}
    # Comparisons/reconciliations and their alert details stay untouched in metadata.
    return {'view_version': 1, 'view': 'focus', 'fields': list(fields), 'source_input': source,
            'metadata': metadata, 'pools': pools, 'rows': projected,
            'metric_definitions': {key: copy.deepcopy(analysis['metric_definitions'][key]) for key in selected_derived},
            'coverage': {'input_rows': len(analysis['rows']), 'output_rows': len(projected), 'sampled': False},
            'omissions': {'counts': totals, 'detail': 'Per-row omitted field names are in pools.omissions via refs.omissions; excluded payload values remain in the hashed original input.',
                          'lossless': False, 'duplicate_ads_alias_omitted': 'ads' in analysis},
            'instructions': 'Rows retain the original input index; source_input hash/path identifies the full input. All comparison/reconciliation flags and all unavailable metric/derived statuses remain. No top-N selection.'}


def _scope(row, rate):
    keys = ['timezone', 'filters']
    if rate in ('cpm', 'purchase_roas'):
        keys.append('currency')
    if rate == 'purchase_roas':
        keys += ['attribution', 'counting_mode', 'report_time_basis', 'purchase_value_event']
    numerator, denominator, _ = RATES[rate]
    context = row['context']
    values = {key: context.get(key) for key in keys}
    scopes = context.get('metric_scopes')
    values['metric_scopes'] = {metric: scopes.get(metric) if isinstance(scopes, dict) else None
                              for metric in (numerator, denominator)}
    return values


def _scope_flags(row, rate, maturity_mode='final_only'):
    flags = []
    scope = _scope(row, rate)
    for key, value in scope.items():
        if key == 'metric_scopes':
            continue
        if key == 'filters':
            if 'filters' not in row['context'] or value is None:
                flags.append('filters_unknown')
        elif not present(value):
            flags.append(f'context_unknown:{key}')
    if rate == 'purchase_roas' and row['derived_status'].get('purchase_roas') == 'withheld_event_value_scope_mismatch':
        flags.append('purchase_event_value_scope_mismatch')
    coverage = row['context'].get('coverage')
    if (not isinstance(coverage, dict) or coverage.get('complete') is not True
            or coverage.get('has_next_page') is True):
        flags.append('coverage_unverified')
    if maturity_mode == 'as_reported':
        collected = row['context'].get('collected_at')
        try:
            stamp = dt.datetime.fromisoformat(collected.replace('Z', '+00:00')) if isinstance(collected, str) else None
            if stamp is None or stamp.tzinfo is None:
                raise ValueError('Timezone-aware collection timestamp required')
        except (ValueError, TypeError):
            flags.append('collection_time_unknown_or_invalid')
    elif row['context'].get('is_final') is not True or row['context'].get('provisional') is True:
        flags.append('reporting_finality_unverified_or_provisional')
    return flags


def _sum(values):
    value = math.fsum(values)
    if not math.isfinite(value):
        raise OverflowError('Nonfinite sum')
    return value


def driver_analysis(analysis, request, source_input=None):
    """Exact midpoint decomposition, conditional on supplied scope assertions.

    Entry/exit refer to positive denominator delivery in these two slices, never
    inferred launch dates. The decomposition is arithmetic, not a causal model.
    """
    if not isinstance(request, dict) or request.get('rate') not in RATES:
        raise ValueError('driver_request requires a supported rate')
    rate = request['rate']
    maturity_mode = request.get('maturity_mode', 'final_only')
    if maturity_mode not in ('final_only', 'as_reported'):
        raise ValueError('maturity_mode must be final_only or as_reported')
    numerator, denominator, multiplier = RATES[rate]
    for key in ('entities_disjoint', 'absence_means_zero_delivery'):
        if key in request and type(request[key]) is not bool:
            raise ValueError(f'{key} must be boolean')
    result = {'view_version': 1, 'view': 'drivers', 'rate': rate,
              'numerator': numerator, 'denominator': denominator, 'multiplier': multiplier,
              'status': 'withheld', 'flags': [], 'periods': {}, 'components': None,
              'entities': [], 'native_residuals': {},
              'limitations': ['Descriptive arithmetic under supplied complete/disjoint scope assertions; no causal explanation or winner ranking.',
                              'Entry/exit means positive-denominator delivery in the selected periods, not creative creation or retirement.',
                              'Midpoint allocation is one exact accounting convention, not a unique economic attribution.']}
    result['source_input'] = copy.deepcopy(source_input)
    if 'requested_scope' in analysis:
        result['requested_scope'] = copy.deepcopy(analysis['requested_scope'])
    flags, rows = result['flags'], analysis['rows']
    if request.get('entities_disjoint') is not True:
        flags.append('entities_disjoint_unverified')
    selected, native_indices = {}, {}
    for side in ('before', 'after'):
        spec = request.get(side)
        if not isinstance(spec, dict) or not isinstance(spec.get('label'), str) or not spec['label'].strip():
            raise ValueError('before/after each require a nonempty label and row_indices')
        indices = spec.get('row_indices')
        if (not isinstance(indices, list) or not indices or any(type(i) is not int or not 0 <= i < len(rows) for i in indices)
                or len(set(indices)) != len(indices)):
            raise ValueError('row_indices must be nonempty distinct valid indices')
        native = spec.get('native_row')
        if native is not None and (type(native) is not int or not 0 <= native < len(rows) or native in indices):
            raise ValueError('native_row must be a separate valid index')
        native_indices[side] = native
        selected[side] = [(i, rows[i]) for i in indices]
        result['periods'][side] = {'label': spec['label'], 'row_indices': indices,
                                   'report_start': rows[indices[0]]['context'].get('report_start'),
                                   'report_end': rows[indices[0]]['context'].get('report_end'),
                                   'collection_times': sorted({r['context']['collected_at'] for _, r in selected[side] if isinstance(r['context'].get('collected_at'), str)})}
    if request['before']['label'] == request['after']['label']:
        raise ValueError('Period labels must differ')
    all_rows = [row for side in selected.values() for _, row in side]
    evidence_indices = sorted({i for entries in selected.values() for i, _ in entries}
                              | {i for i in native_indices.values() if i is not None})
    evidence_rows = [rows[i] for i in evidence_indices]
    finality_verified = all(r['context'].get('is_final') is True and r['context'].get('provisional') is not True for r in evidence_rows)
    known_provisional = any(r['context'].get('is_final') is False or r['context'].get('provisional') is True for r in evidence_rows)
    result['reporting_maturity'] = {
        'mode': maturity_mode, 'finality_verified': finality_verified,
        'provisional': True if maturity_mode == 'as_reported' or known_provisional else False if finality_verified else None,
        'label': ('AS REPORTED: provisional snapshot arithmetic; results may be revised' if maturity_mode == 'as_reported'
                  else 'Finality explicitly asserted by every supplied row' if finality_verified
                  else 'Finality unverified or provisional; affected calculations withheld')}
    result['evidence'] = _driver_evidence(analysis, evidence_indices, numerator, denominator)
    first = all_rows[0]
    result['scope'] = {'account_id': first['account_id'], 'level': first['level'],
                       'breakdown': copy.deepcopy(first.get('breakdown')), **_scope(first, rate)}
    result['assertions'] = {key: request.get(key) for key in ('entities_disjoint', 'absence_means_zero_delivery')}
    if len({(r['account_id'], r['level']) for r in all_rows}) != 1:
        flags.append('mixed_account_or_hierarchy')
    if len({canonical(r.get('breakdown')) for r in all_rows}) != 1:
        flags.append('breakdown_differs')
    if len({canonical(_scope(r, rate)) for r in all_rows}) != 1:
        flags.append('metric_scope_differs')
    for r in all_rows:
        flags.extend(_scope_flags(r, rate, maturity_mode))
    for side, entries in selected.items():
        if len({r['entity_id'] for _, r in entries}) != len(entries):
            flags.append(f'duplicate_entity:{side}')
        if len({window(r['context']) for _, r in entries}) != 1:
            flags.append(f'mixed_windows:{side}')
    bw, aw = (window(selected[side][0][1]['context']) for side in ('before', 'after'))
    if bw is None or aw is None:
        flags.append('reporting_window_unknown')
    elif bw[1] >= aw[0] or bw[1] - bw[0] != aw[1] - aw[0]:
        flags.append('periods_overlap_out_of_order_or_different_length')
    before_ids = {r['entity_id'] for _, r in selected['before']}
    after_ids = {r['entity_id'] for _, r in selected['after']}
    if before_ids != after_ids and request.get('absence_means_zero_delivery') is not True:
        flags.append('absent_entities_not_verified_zero_delivery')
    # A positive numerator with no exposure has no identifiable entity rate.
    for side, entries in selected.items():
        for _, row in entries:
            n, d = row['metrics'].get(numerator), row['metrics'].get(denominator)
            if n is None or d is None:
                flags.append(f'metric_unavailable:{side}:{row["entity_id"]}')
            elif d == 0 and n != 0:
                flags.append(f'nonzero_numerator_zero_denominator:{side}:{row["entity_id"]}')
    flags[:] = list(dict.fromkeys(flags))
    if flags:
        return result
    try:
        totals = {}
        by_id = {side: {r['entity_id']: (i, r) for i, r in entries} for side, entries in selected.items()}
        for side, entries in selected.items():
            n = _sum(r['metrics'][numerator] for _, r in entries)
            d = _sum(r['metrics'][denominator] for _, r in entries)
            if d <= 0:
                flags.append(f'zero_total_denominator:{side}')
            totals[side] = (n, d)
        if flags:
            return result
        for side, (n, d) in totals.items():
            result['periods'][side].update(numerator_total=n, denominator_total=d, rate=n / d * multiplier)
        for identity in sorted(before_ids | after_ids):
            observations = {}
            for side in ('before', 'after'):
                pair = by_id[side].get(identity)
                n, d = (pair[1]['metrics'][numerator], pair[1]['metrics'][denominator]) if pair else (0, 0)
                observations[side] = {'row_index': pair[0] if pair else None, 'numerator': n, 'denominator': d,
                                      'weight': d / totals[side][1], 'rate': n / d * multiplier if d else None,
                                      'absence_asserted_zero_delivery': pair is None}
            b, a = observations['before'], observations['after']
            contributions = dict(within=0., mix=0., entrants=0., exits=0.)
            if b['denominator'] > 0 and a['denominator'] > 0:
                kind = 'continuing'
                contributions['within'] = (a['weight'] + b['weight']) / 2 * (a['rate'] - b['rate'])
                contributions['mix'] = (a['rate'] + b['rate']) / 2 * (a['weight'] - b['weight'])
            elif a['denominator'] > 0:
                kind = 'delivery_entry'
                contributions['entrants'] = a['weight'] * a['rate']
            elif b['denominator'] > 0:
                kind = 'delivery_exit'
                contributions['exits'] = -b['weight'] * b['rate']
            else:
                kind = 'zero_delivery_both'
            result['entities'].append({'account_id': first['account_id'], 'level': first['level'],
                                       'entity_id': identity, 'kind': kind, **observations,
                                       'contributions': contributions})
        components = {key: _sum(e['contributions'][key] for e in result['entities']) for key in ('within', 'mix', 'entrants', 'exits')}
        delta = result['periods']['after']['rate'] - result['periods']['before']['rate']
        result['components'] = {**components, 'sum': _sum(components.values()), 'observed_change': delta,
                                'floating_point_residual': delta - _sum(components.values())}
        for side, index in native_indices.items():
            if index is not None:
                result['native_residuals'][side] = _native_residual(rows[index], index, selected[side], rate, totals[side], maturity_mode)
        if set(result['native_residuals']) == {'before', 'after'} and all(r['status'] == 'computed' for r in result['native_residuals'].values()):
            b, a = result['native_residuals']['before'], result['native_residuals']['after']
            result['native_change'] = {'observed_change': a['native_rate'] - b['native_rate'],
                                       'child_change': delta, 'residual_change': a['rate_residual'] - b['rate_residual']}
        canonical(result)  # No nonfinite arithmetic can escape through direct callers.
        result['status'] = 'computed'
    except (OverflowError, ValueError):
        result.update(status='withheld', components=None, entities=[], native_residuals={})
        result.pop('native_change', None)
        for period in result['periods'].values():
            for key in ('rate', 'numerator_total', 'denominator_total'):
                period.pop(key, None)
        flags.append('nonfinite_arithmetic')
    return result


def _driver_evidence(analysis, indices, numerator, denominator):
    """Retain source context/coverage and analysis alerts without raw payload dumps."""
    pool_names = ('context', 'warnings', 'metric_alerts', 'derived_alerts')
    pools, lookup = {key: [] for key in pool_names}, {key: {} for key in pool_names}
    evidence = []
    for index in indices:
        row = analysis['rows'][index]
        pooled = {'context': row['context'], 'warnings': row['warnings'],
                  'metric_alerts': {key: state for key, state in row['metric_status'].items() if state != 'reported'},
                  'derived_alerts': {key: state for key, state in row['derived_status'].items() if state != 'computed'}}
        refs = {}
        for key, value in pooled.items():
            signature = canonical(value)
            if signature not in lookup[key]:
                lookup[key][signature] = len(pools[key])
                pools[key].append(copy.deepcopy(value))
            refs[key] = lookup[key][signature]
        provenance = {key: copy.deepcopy(value) for key, value in row.items()
                      if key.endswith('_id') or key in ('id', 'level', 'name', 'source', 'provenance', 'source_path',
                                                       'collected_at', 'created_time', 'updated_time', 'effective_status', 'flags')}
        evidence.append({'input_row_index': index, 'identity_and_provenance': provenance, 'refs': refs,
                         'source_metric_values': {metric: copy.deepcopy(row['source_metrics'].get(metric)) for metric in (numerator, denominator)},
                         'omitted_payload_fields': [key for key in ('source_record', 'media', 'raw_response', 'raw_payload') if key in row]})
    # Preserve relevant comparison/reconciliation evidence, including failed checks.
    selected = set(indices)
    comparisons = [c for c in analysis.get('period_comparisons', []) if {c['before_row'], c['after_row']} & selected]
    reconciliations = [r for r in analysis.get('reconciliations', []) if ({r['parent_row']} | set(r['child_rows'])) & selected]
    return {'pools': pools, 'rows': evidence, 'analyzer_flags': copy.deepcopy(analysis['flags']),
            'analyzer_limitations': copy.deepcopy(analysis['limitations']),
            'period_comparisons': copy.deepcopy(comparisons), 'reconciliations': copy.deepcopy(reconciliations),
            'omitted_analysis': {'unselected_rows': len(analysis['rows']) - len(indices),
                                 'unrelated_period_comparisons': len(analysis.get('period_comparisons', [])) - len(comparisons),
                                 'unrelated_reconciliations': len(analysis.get('reconciliations', [])) - len(reconciliations),
                                 'other_fields': 'Unselected metrics and raw/media payloads remain in source_input at input_row_index; context, coverage, warnings and unavailable statuses are retained here.'}}


def _native_residual(parent, index, children, rate, totals, maturity_mode):
    numerator, denominator, multiplier = RATES[rate]
    flags = _scope_flags(parent, rate, maturity_mode)
    first = children[0][1]
    parent_field = {'account': 'account_id', 'campaign': 'campaign_id', 'adset': 'adset_id', 'ad': 'ad_id'}[parent['level']]
    if (LEVELS.index(parent['level']) >= LEVELS.index(first['level'])
            or any(r.get(parent_field) != parent['entity_id'] for _, r in children)):
        flags.append('native_parent_membership_unverified')
    if parent['account_id'] != first['account_id'] or window(parent['context']) != window(first['context']):
        flags.append('native_account_or_window_differs')
    if canonical(parent.get('breakdown')) != canonical(first.get('breakdown')) or canonical(_scope(parent, rate)) != canonical(_scope(first, rate)):
        flags.append('native_metric_scope_differs')
    n, d = parent['metrics'].get(numerator), parent['metrics'].get(denominator)
    if n is None or d is None or d == 0:
        flags.append('native_metric_unavailable_or_zero_denominator')
    result = {'native_row': index, 'account_id': parent['account_id'], 'level': parent['level'],
              'entity_id': parent['entity_id'], 'collected_at': parent['context'].get('collected_at'),
              'status': 'withheld' if flags else 'computed',
              'flags': flags, 'numerator_residual': None, 'denominator_residual': None,
              'rate_residual': None, 'native_rate': None}
    if not flags:
        result.update(numerator_residual=n - totals[0], denominator_residual=d - totals[1],
                      native_rate=n / d * multiplier,
                      rate_residual=n / d * multiplier - totals[0] / totals[1] * multiplier)
    return result


def build_view(payload, view='compact', driver_request=None, fields=None, source_path=None, source_bytes=None):
    analysis = analyze(payload)
    if view == 'compact':
        return compact_analysis(analysis)
    if view == 'focus':
        return focus_analysis(analysis, payload, fields, source_path, source_bytes)
    if view == 'drivers':
        return driver_analysis(analysis, driver_request if driver_request is not None else payload.get('driver_request'),
                               source_reference(payload, source_path, source_bytes))
    raise ValueError('view must be compact, focus or drivers')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--view', choices=('compact', 'focus', 'drivers'), default='compact')
    parser.add_argument('--fields', help='Explicit comma-separated metrics.<key>/derived_metrics.<key> for focus')
    args = parser.parse_args()
    try:
        source_bytes = args.input.read_bytes()
        payload = json.loads(source_bytes)
        result = build_view(payload, args.view, fields=args.fields.split(',') if args.fields else None,
                            source_path=args.input.resolve(), source_bytes=source_bytes)
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    except (ValueError, TypeError, OSError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
