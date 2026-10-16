#!/usr/bin/env python3
"""Per-ad verdicts (wait/kill/scale/iterate), fatigue, angle rollups and creative-review priority.

Rules use the client's own targets from a small config JSON. Arithmetic only: no statistics,
no API writes. Input is a normalized v1/v2 packet as accepted by analyze_meta.py.
"""
import argparse
import datetime as dt
import json
import re
import statistics
from pathlib import Path

if __package__:
    from .analyze_meta import analyze, window
else:
    from analyze_meta import analyze, window

DEFAULTS = {'conversion_lag_days': 3, 'kill_spend_multiple': 2, 'kill_cpa_multiple': 1.5,
            'kill_min_purchases': 5, 'scale_min_purchases': 10}
NAME = re.compile(r'^(?P<client>[^_]+)_(?P<concept>[^_]+)_(?P<angle>[^_]+)_(?P<hook>[^_]+)_v(?P<version>\d+)$', re.I)
FIXES = {'hook': 'new first frame / hook; keep the angle',
         'hold': 'new body or angle; keep the hook',
         'post_click': 'fix landing page or offer congruence; do not make a new ad',
         'offer': 'test offer, price framing or bundle; creative is not the bottleneck'}


def load_config(config):
    config = {**DEFAULTS, **config}
    if not isinstance(config.get('target_cpa'), (int, float)) or config['target_cpa'] <= 0:
        raise ValueError('config.target_cpa must be a positive number')
    config.setdefault('min_spend', config['target_cpa'])
    return config


def parse_name(name):
    """CLIENT_concept_angle_hook_vN -> parts, or None when the name does not follow the convention."""
    match = NAME.match(name.strip()) if isinstance(name, str) else None
    return {**match.groupdict(), 'version': int(match['version'])} if match else None


def ratio(a, b):
    return a / b if a is not None and b else None


def video_rates(metrics):
    """hook = 3s views / impressions; hold = thruplays / 3s views."""
    return {'hook_rate': ratio(metrics.get('video_3s_views'), metrics.get('impressions')),
            'hold_rate': ratio(metrics.get('video_thruplays'), metrics.get('video_3s_views'))}


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if len(values) >= 2 else None


def inside_lag(row, config, as_of):
    span = window(row['context'])
    return span is None or span[1] > as_of - dt.timedelta(days=config['conversion_lag_days'])


def verdict(row, config, as_of, peers):
    """One call per ad. peers holds ad-set medians for ctr/hook_rate/hold_rate (None when <2 ads)."""
    m, target = row['metrics'], config['target_cpa']
    spend, purchases = m.get('spend') or 0, m.get('purchases') or 0
    cpa = spend / purchases if purchases else None
    if row.get('attribution_mixed'):
        return 'none', 'mixed_attribution'
    if row.get('context', {}).get('provisional') is True or row.get('context', {}).get('is_final') is False:
        return 'wait', 'provisional_window'
    lagging = inside_lag(row, config, as_of)
    if spend < config['min_spend']:
        return 'wait', 'below_spend_floor'
    if purchases == 0 and spend >= config['kill_spend_multiple'] * target and not lagging:
        return 'kill', 'no_purchases_at_spend_cap'
    if purchases >= config['kill_min_purchases'] and cpa > config['kill_cpa_multiple'] * target and not lagging:
        return 'kill', 'cpa_far_above_target'
    if purchases >= config['scale_min_purchases'] and cpa <= target and not lagging:
        return 'scale', 'cpa_at_or_under_target'
    if lagging:
        return 'wait', 'inside_conversion_lag'
    return 'iterate', iterate_reason(row, peers)


def iterate_reason(row, peers):
    ctr = row['derived_metrics'].get('ctr_link_pct')
    rates = video_rates(row['metrics'])
    if rates['hook_rate'] is not None and peers.get('hook_rate') and rates['hook_rate'] < peers['hook_rate']:
        return 'hook'
    if ctr is not None and peers.get('ctr') and ctr < peers['ctr']:
        return 'hook'
    if rates['hold_rate'] is not None and peers.get('hold_rate') and rates['hold_rate'] < peers['hold_rate']:
        return 'hold'
    cvr = row['derived_metrics'].get('purchases_per_lpv_pct')
    if cvr is not None and peers.get('cvr') and cvr < peers['cvr']:
        return 'post_click'
    return 'post_click' if not row['metrics'].get('purchases') else 'offer'


def fatigue(history):
    """Own-history check over 3+ chronological periods (2+ complete changes): frequency up,
    CTR down >=20% from first to last, CPA up. CPM is reported only as context."""
    points = [r for r in history if r['derived_metrics'].get('frequency') is not None
              and r['derived_metrics'].get('ctr_link_pct') is not None]
    if len(points) < 3 or any(r.get('attribution_mixed') or r['context'].get('provisional') is True for r in points):
        return {'eligible': False, 'fatigued': False, 'reason': 'needs_3_clean_periods'}
    freq = [r['derived_metrics']['frequency'] for r in points]
    ctr = [r['derived_metrics']['ctr_link_pct'] for r in points]
    cpa = [r['derived_metrics'].get('purchase_cpa') for r in points]
    rising = all(b >= a for a, b in zip(freq, freq[1:])) and freq[-1] > freq[0]
    ctr_drop = (ctr[0] - ctr[-1]) / ctr[0] if ctr[0] else 0
    cpa_up = None not in (cpa[0], cpa[-1]) and cpa[-1] > cpa[0]
    return {'eligible': True, 'fatigued': rising and ctr_drop >= 0.2 and cpa_up,
            'frequency': [freq[0], freq[-1]], 'ctr_link_pct': [ctr[0], ctr[-1]],
            'ctr_drop_pct': round(ctr_drop * 100, 1), 'cpa': [cpa[0], cpa[-1]],
            'cpm': [points[0]['derived_metrics'].get('cpm'), points[-1]['derived_metrics'].get('cpm')]}


def decide(payload, config, as_of=None):
    config = load_config(config)
    as_of = as_of or dt.date.today()
    rows = [r for r in analyze(payload)['rows'] if r['level'] == 'ad']
    history, latest = {}, {}
    for row in rows:
        history.setdefault(row['entity_id'], []).append(row)
    for entity, entries in history.items():
        entries.sort(key=lambda r: r['context'].get('report_start') or '')
        latest[entity] = entries[-1]
    groups = {}
    for row in latest.values():
        groups.setdefault((row.get('adset_id'), window(row['context'])), []).append(row)
    ads, rollups = [], []
    for (adset, span), members in groups.items():
        clean = [r for r in members if not r.get('attribution_mixed')]
        peers = {'ctr': _median(r['derived_metrics'].get('ctr_link_pct') for r in clean),
                 'cvr': _median(r['derived_metrics'].get('purchases_per_lpv_pct') for r in clean),
                 'hook_rate': _median(video_rates(r['metrics'])['hook_rate'] for r in clean),
                 'hold_rate': _median(video_rates(r['metrics'])['hold_rate'] for r in clean)}
        for row in members:
            call, reason = verdict(row, config, as_of, peers)
            spend = row['metrics'].get('spend') or 0
            ads.append({'entity_id': row['entity_id'], 'name': row.get('name'), 'adset_id': adset,
                        'name_parts': parse_name(row.get('name')), 'verdict': call, 'reason': reason,
                        'next_step': FIXES.get(reason) if call == 'iterate' else None,
                        'counts': row['counts'], 'low_volume': row['low_volume'],
                        'cpa': row['derived_metrics'].get('purchase_cpa'),
                        'roas': row['derived_metrics'].get('purchase_roas'),
                        'ctr_link_pct': row['derived_metrics'].get('ctr_link_pct'),
                        **video_rates(row['metrics']),
                        'creative_review': 'deep' if spend >= config['min_spend'] else 'skip_low_spend',
                        'fatigue': fatigue(history[row['entity_id']]),
                        'warnings': row['warnings']})
        rollups.extend(angle_rollups(clean, adset, span))
    ads.sort(key=lambda a: -(a['counts']['spend'] or 0))
    return {'as_of': as_of.isoformat(), 'config': config, 'ads': ads, 'angle_rollups': rollups}


def angle_rollups(rows, adset, span):
    """Directional only: same ad set and window, angles with 2+ named ads."""
    angles = {}
    for row in rows:
        parts = parse_name(row.get('name'))
        if parts:
            angles.setdefault(parts['angle'].lower(), []).append(row)
    result = []
    for angle, members in sorted(angles.items()):
        if len(members) < 2:
            continue
        spend = sum(r['metrics'].get('spend') or 0 for r in members)
        purchases = sum(r['metrics'].get('purchases') or 0 for r in members)
        result.append({'adset_id': adset, 'window': [d.isoformat() for d in span] if span else None,
                       'angle': angle, 'ads': len(members), 'spend': spend, 'purchases': purchases,
                       'cpa': spend / purchases if purchases else None, 'label': 'directional'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--config', type=Path, required=True, help='Client JSON: target_cpa, optional conversion_lag_days, min_spend')
    parser.add_argument('--as-of', type=dt.date.fromisoformat, help='Decision date (default today)')
    args = parser.parse_args()
    try:
        result = decide(json.loads(args.input.read_text(encoding='utf-8')),
                        json.loads(args.config.read_text(encoding='utf-8')), args.as_of)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
