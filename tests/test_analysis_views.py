import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from scripts.analyze_meta import analyze
from scripts.analysis_views import build_view, compact_analysis, expand_compact
from tests.test_review_pack import fixture


def drivers():
    p = fixture()
    p['rows'] = []
    # A/B continue; C exits; D enters. Rates and weights both change.
    for start, end, entities in [
        ('2026-10-01', '2026-10-07', [('a', 10, 100), ('b', 40, 200), ('c', 15, 300)]),
        ('2026-10-08', '2026-10-14', [('a', 20, 100), ('b', 20, 400), ('d', 90, 300)]),
    ]:
        for identity, spend, impressions in entities:
            p['rows'].append({'level': 'ad', 'entity_id': identity, 'campaign_id': 'c1',
                              'context': {'report_start': start, 'report_end': end},
                              'metrics': {'spend': spend, 'impressions': impressions,
                                          'link_clicks': spend, 'purchase_value': impressions}})
    p['driver_request'] = {'rate': 'cpm', 'entities_disjoint': True, 'absence_means_zero_delivery': True,
                           'before': {'label': 'Earlier', 'row_indices': [0, 1, 2]},
                           'after': {'label': 'Later', 'row_indices': [3, 4, 5]}}
    return p


class CompactTests(unittest.TestCase):
    def test_exact_roundtrip_with_missing_status_media_source_and_custom_fields(self):
        p = fixture()
        p['rows'][0]['media'] = [{'asset_id': '90071992547409931', 'path': '/tmp/asset.png', 'raw': [1, None, 3]}]
        p['rows'][0]['metric_status'] = {'purchase_value': 'unsupported'}
        p['rows'][0]['metrics']['actions'] = [{'action_type': 'test', 'value': '1'}]
        p['rows'][0]['context_ref'] = 'original custom field retained'
        p['source_metadata'] = {'original_source': '/tmp/raw.json', 'null_field': None}
        a = analyze(p)
        v = build_view(p)
        self.assertEqual(expand_compact(v), a)
        self.assertEqual(v['omitted_payloads'], [])
        self.assertFalse(v['coverage']['sampled'])

    def test_shared_warnings_and_context_interned_not_truncated(self):
        p = fixture()
        p['rows'] = [dict(copy.deepcopy(p['rows'][0]), entity_id=str(i)) for i in range(50)]
        a = analyze(p)
        v = compact_analysis(a)
        self.assertEqual(len(v['pools']['context']), 1)
        self.assertEqual(len(v['rows']), 50)
        self.assertEqual(expand_compact(v), a)
        self.assertLess(len(json.dumps(v)), len(json.dumps(a)) * .75)

    def test_v1_alias_and_input_not_mutated(self):
        p = fixture()
        p['schema_version'] = 1
        p['ads'] = p.pop('rows')
        p['ads'][0]['ad_id'] = p['ads'][0].pop('entity_id')
        original = copy.deepcopy(p)
        v = build_view(p)
        self.assertEqual(v['aliases'], {'ads': 'rows'})
        self.assertEqual(expand_compact(v), analyze(p))
        self.assertEqual(p, original)

    def test_cli_json_and_invalid_source_still_validated(self):
        p = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text(json.dumps(p))
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts' / 'analysis_views.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['view'], 'compact')
        p['rows'][0]['entity_id'] = 123
        with self.assertRaises(ValueError):
            build_view(p)


class FocusTests(unittest.TestCase):
    def test_explicit_selection_every_row_status_and_omissions(self):
        p = fixture()
        p['rows'] = [dict(copy.deepcopy(p['rows'][0]), entity_id=str(i)) for i in range(80)]
        p['rows'][0]['metric_status'] = {'purchase_value': 'suppressed'}
        p['rows'][0]['metrics']['purchase_value'] = 0
        p['rows'][1]['metrics']['purchases'] = None
        p['rows'][0]['media'] = [{'asset_id': 'img1', 'path': '/tmp/image.png'}]
        p['rows'][0]['source_record'] = {'original': 'full source'}
        p['rows'][0]['effective_status'] = 'PAUSED'
        fields = ['metrics.spend', 'metrics.purchases', 'metrics.purchase_value', 'metrics.leads', 'derived_metrics.cpm']
        v = build_view(p, 'focus', fields=fields)
        self.assertEqual(len(v['rows']), 80)
        self.assertEqual(v['rows'][0]['identity_and_provenance']['effective_status'], 'PAUSED')
        self.assertEqual([r['identity_and_provenance']['entity_id'] for r in v['rows']], [str(i) for i in range(80)])
        self.assertEqual(v['rows'][0]['values']['metrics.purchase_value'], {'value': None, 'status': 'suppressed', 'source_value': 0})
        self.assertEqual(v['rows'][0]['values']['metrics.leads'], {'value': None, 'status': 'unknown'})
        self.assertIsNone(v['rows'][1]['values']['metrics.purchases']['value'])
        self.assertEqual(set(v['rows'][0]['values']), set(fields))
        omitted = v['pools']['omissions'][v['rows'][0]['refs']['omissions']]
        self.assertIn('media', omitted['payload_fields'])
        self.assertIn('source_record', omitted['payload_fields'])
        self.assertIn('impressions', omitted['metric_fields'])
        self.assertEqual(v['omissions']['counts']['payload_fields'], 2)
        self.assertFalse(v['omissions']['lossless'])
        self.assertFalse(v['coverage']['sampled'])

    def test_source_exact_bytes_hash_and_original_indices(self):
        p = fixture()
        encoded = json.dumps(p, indent=3).encode()
        v = build_view(p, 'focus', fields=['metrics.spend'], source_bytes=encoded, source_path='/tmp/full.json')
        self.assertEqual(v['source_input']['sha256'], hashlib.sha256(encoded).hexdigest())
        self.assertEqual(v['source_input']['hash_basis'], 'exact_input_bytes')
        self.assertEqual(v['source_input']['path'], '/tmp/full.json')
        self.assertEqual(v['rows'][0]['input_row_index'], 0)
        self.assertEqual(build_view(p, 'focus', fields=['metrics.spend'])['source_input']['hash_basis'], 'canonical_json_utf8')
        with self.assertRaises(ValueError):
            build_view(p, 'focus', fields=['metrics.spend'], source_bytes=b'{}')

    def test_safety_evidence_comparisons_reconciliation_and_warnings_preserved(self):
        from tests.test_reconciliation import reconciliation
        p = reconciliation()
        p['rows'][2]['metrics']['spend'] = 21
        p['rows'][1]['metric_status'] = {'purchases': 'failed'}
        a = analyze(p)
        v = build_view(p, 'focus', fields=['metrics.spend'])
        self.assertEqual(v['metadata']['reconciliations'], a['reconciliations'])
        self.assertEqual(v['metadata']['flags'], a['flags'])
        row = v['rows'][1]
        self.assertEqual(v['pools']['warnings'][row['refs']['warnings']], a['rows'][1]['warnings'])
        self.assertEqual(v['pools']['metric_alerts'][row['refs']['metric_alerts']]['purchases'], 'failed')
        p = drivers()
        p['compare_periods'] = True
        v = build_view(p, 'focus', fields=['metrics.spend'])
        self.assertEqual(v['metadata']['period_comparisons'], analyze(p)['period_comparisons'])

    def test_no_implicit_fields_and_unknown_field_rejected(self):
        for fields in (None, [], ['metrics.typo'], ['spend'], ['metrics.spend', 'metrics.spend']):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                build_view(fixture(), 'focus', fields=fields)

    def test_focus_cli_source_locator_and_selected_fields(self):
        p = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text(json.dumps(p))
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts' / 'analysis_views.py'), str(path),
                                     '--view', 'focus', '--fields', 'metrics.spend,derived_metrics.cpm'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            v = json.loads(result.stdout)
            self.assertEqual(v['source_input']['path'], str(path.resolve()))
            self.assertEqual(v['source_input']['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(v['fields'], ['metrics.spend', 'derived_metrics.cpm'])


class DriverTests(unittest.TestCase):
    def test_exact_components_entry_exit_and_no_causal_label(self):
        r = build_view(drivers(), 'drivers')
        self.assertEqual(r['status'], 'computed')
        c = r['components']
        self.assertAlmostEqual(c['sum'], c['observed_change'])
        self.assertAlmostEqual(c['entrants'], 90 / 800 * 1000)
        self.assertAlmostEqual(c['exits'], -15 / 600 * 1000)
        self.assertEqual({e['entity_id']: e['kind'] for e in r['entities']}, {'a': 'continuing', 'b': 'continuing', 'c': 'delivery_exit', 'd': 'delivery_entry'})
        self.assertEqual(r['scope']['currency'], 'USD')

    def test_permutation_invariance_and_all_supported_rates(self):
        for rate in ('cpm', 'ctr_link_pct', 'purchase_roas'):
            p = drivers()
            p['driver_request']['rate'] = rate
            a = build_view(p, 'drivers')
            permutation = [5, 0, 3, 2, 1, 4]
            p['rows'] = [p['rows'][i] for i in permutation]
            for side in ('before', 'after'):
                p['driver_request'][side]['row_indices'] = [permutation.index(i) for i in p['driver_request'][side]['row_indices']]
            b = build_view(p, 'drivers')
            self.assertEqual(a['components'], b['components'])
            self.assertAlmostEqual(b['components']['sum'], b['components']['observed_change'])

    def test_randomized_exact_reconstruction(self):
        rng = random.Random(42)
        for _ in range(40):
            p = drivers()
            for row in p['rows']:
                row['metrics']['spend'] = rng.uniform(0, 2000)
                row['metrics']['impressions'] = rng.randint(1, 10000)
            r = build_view(p, 'drivers')
            self.assertEqual(r['status'], 'computed')
            self.assertAlmostEqual(r['components']['sum'], r['components']['observed_change'], places=9)

    def test_no_change_yields_zero_within_mix_entry_exit(self):
        p = drivers()
        for before, after in zip(p['rows'][:3], p['rows'][3:]):
            after['entity_id'] = before['entity_id']
            after['metrics'] = copy.deepcopy(before['metrics'])
        r = build_view(p, 'drivers')
        self.assertEqual(r['status'], 'computed')
        for key in ('within', 'mix', 'entrants', 'exits', 'observed_change'):
            self.assertEqual(r['components'][key], 0)

    def test_zero_zero_rows_inactive_and_zero_positive_withheld(self):
        p = drivers()
        p['rows'][0]['metrics'].update(spend=0, impressions=0)
        r = build_view(p, 'drivers')
        self.assertEqual(r['status'], 'computed')
        self.assertEqual(r['entities'][0]['kind'], 'delivery_entry')
        p['rows'][3]['metrics'].update(spend=0, impressions=0)
        r = build_view(p, 'drivers')
        self.assertEqual(r['entities'][0]['kind'], 'zero_delivery_both')
        p['rows'][0]['metrics']['spend'] = 1
        self.assertEqual(build_view(p, 'drivers')['status'], 'withheld')

    def test_missing_metrics_and_coverage_never_invent_zero(self):
        for mutation in ('missing_metric', 'missing_coverage', 'pending_page', 'missing_absence', 'missing_disjoint'):
            p = drivers()
            if mutation == 'missing_metric':
                p['rows'][0]['metrics']['spend'] = None
            elif mutation == 'missing_coverage':
                del p['context']['coverage']
            elif mutation == 'pending_page':
                p['context']['coverage']['has_next_page'] = True
            elif mutation == 'missing_absence':
                del p['driver_request']['absence_means_zero_delivery']
            else:
                del p['driver_request']['entities_disjoint']
            r = build_view(p, 'drivers')
            self.assertEqual(r['status'], 'withheld', mutation)
            self.assertIsNone(r['components'])

    def test_mixed_levels_filters_periods_and_missing_scope_withheld(self):
        for mutation in ({'level': 'adset'}, {'context': {'filters': None}},
                         {'context': {'filters': {'publisher_platform': 'instagram'}}},
                         {'context': {'report_end': '2026-10-06'}},
                         {'context': {'timezone': None}}, {'context': {'is_final': False}}):
            p = drivers()
            p['rows'][0].update(mutation)
            self.assertEqual(build_view(p, 'drivers')['status'], 'withheld', mutation)

    def test_native_residual_preserved_not_forced_to_zero(self):
        p = drivers()
        for side, start, end, spend, impressions in [('before', '2026-10-01', '2026-10-07', 70, 602), ('after', '2026-10-08', '2026-10-14', 140, 803)]:
            p['driver_request'][side]['native_row'] = len(p['rows'])
            p['rows'].append({'level': 'campaign', 'entity_id': 'c1',
                              'context': {'report_start': start, 'report_end': end},
                              'metrics': {'spend': spend, 'impressions': impressions}})
        r = build_view(p, 'drivers')
        self.assertEqual(r['status'], 'computed')
        self.assertEqual(r['native_residuals']['before']['numerator_residual'], 5)
        self.assertEqual(r['native_residuals']['after']['denominator_residual'], 3)
        change = r['native_change']
        self.assertAlmostEqual(change['observed_change'], change['child_change'] + change['residual_change'])
        p['rows'][-1]['entity_id'] = 'wrong'
        r = build_view(p, 'drivers')
        self.assertEqual(r['native_residuals']['after']['status'], 'withheld')
        self.assertNotIn('native_change', r)

    def test_conversion_scope_unknown_blocks_roas_but_not_cpm(self):
        p = drivers()
        p['context']['attribution'] = None
        self.assertEqual(build_view(p, 'drivers')['status'], 'computed')
        p['driver_request']['rate'] = 'purchase_roas'
        self.assertEqual(build_view(p, 'drivers')['status'], 'withheld')

    def test_withheld_finality_never_claims_final_source(self):
        p = drivers()
        del p['context']['is_final']
        r = build_view(p, 'drivers')
        self.assertEqual(r['status'], 'withheld')
        self.assertFalse(r['reporting_maturity']['finality_verified'])
        self.assertIsNone(r['reporting_maturity']['provisional'])
        self.assertIn('unverified', r['reporting_maturity']['label'])
        p['context']['is_final'] = False
        self.assertTrue(build_view(p, 'drivers')['reporting_maturity']['provisional'])
        p['context']['is_final'] = True
        r = build_view(p, 'drivers')
        self.assertTrue(r['reporting_maturity']['finality_verified'])
        self.assertFalse(r['reporting_maturity']['provisional'])

    def test_driver_input_hash_provenance_coverage_and_alerts_preserved(self):
        p = drivers()
        p['context']['source_path'] = '/tmp/raw-weekly.json'
        p['rows'][0]['source'] = {'file': '/tmp/raw-page-1.json', 'row_index': 9}
        p['rows'][0]['source_record'] = {'raw': 'not copied'}
        p['rows'][0]['metric_status'] = {'purchases': 'failed'}
        p['compare_periods'] = True
        original = json.dumps(p, indent=2).encode()
        r = build_view(p, 'drivers', source_bytes=original, source_path='/tmp/normalized.json')
        self.assertEqual(r['source_input']['sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(r['source_input']['path'], '/tmp/normalized.json')
        self.assertEqual(r['source_input']['row_container'], 'rows')
        evidence = r['evidence']
        first = evidence['rows'][0]
        self.assertEqual(first['input_row_index'], 0)
        self.assertEqual(first['identity_and_provenance']['source'], p['rows'][0]['source'])
        context = evidence['pools']['context'][first['refs']['context']]
        self.assertEqual(context['coverage'], {'complete': True})
        self.assertEqual(context['source_path'], '/tmp/raw-weekly.json')
        self.assertEqual(evidence['pools']['metric_alerts'][first['refs']['metric_alerts']]['purchases'], 'failed')
        self.assertEqual(first['omitted_payload_fields'], ['source_record'])
        a = analyze(p)
        self.assertEqual(evidence['analyzer_flags'], a['flags'])
        self.assertEqual(evidence['pools']['warnings'][first['refs']['warnings']], a['rows'][0]['warnings'])
        self.assertEqual(evidence['period_comparisons'], a['period_comparisons'])
        with self.assertRaises(ValueError):
            build_view(p, 'drivers', source_bytes=b'{}')

    def test_driver_as_reported_keeps_per_row_collection_times_and_native_evidence(self):
        p = drivers()
        p['driver_request']['maturity_mode'] = 'as_reported'
        del p['context']['is_final']
        p['context']['collected_at'] = '2026-10-15T02:05:00Z'
        p['rows'][0]['context']['collected_at'] = '2026-10-15T02:06:00Z'
        p['rows'].append({'level': 'campaign', 'entity_id': 'c1', 'metrics': {'spend': 65, 'impressions': 600}})
        p['driver_request']['before']['native_row'] = 6
        r = build_view(p, 'drivers')
        self.assertEqual(len(r['evidence']['rows']), 7)
        self.assertEqual(r['evidence']['pools']['context'][r['evidence']['rows'][0]['refs']['context']]['collected_at'], '2026-10-15T02:06:00Z')
        self.assertEqual(r['native_residuals']['before']['collected_at'], '2026-10-15T02:05:00Z')
        self.assertFalse(r['reporting_maturity']['finality_verified'])

    def test_as_reported_is_explicit_provisional_and_preserves_collection_times(self):
        p = drivers()
        del p['context']['is_final']
        p['context']['collected_at'] = '2026-10-15T02:05:00Z'
        self.assertEqual(build_view(p, 'drivers')['status'], 'withheld')
        p['driver_request']['maturity_mode'] = 'as_reported'
        r = build_view(p, 'drivers')
        self.assertEqual(r['status'], 'computed')
        self.assertTrue(r['reporting_maturity']['provisional'])
        self.assertIn('AS REPORTED', r['reporting_maturity']['label'])
        self.assertEqual(r['periods']['before']['collection_times'], ['2026-10-15T02:05:00Z'])
        self.assertNotIn('is_final', p['context'])

    def test_as_reported_does_not_bypass_other_evidence_guards(self):
        for change in ('timestamp', 'naive', 'coverage', 'missing_metric', 'different_scope'):
            p = drivers()
            p['driver_request']['maturity_mode'] = 'as_reported'
            p['context']['is_final'] = False
            p['context']['collected_at'] = '2026-10-15T02:05:00Z'
            if change == 'timestamp':
                p['rows'][0]['context']['collected_at'] = None
            elif change == 'naive':
                p['rows'][0]['context']['collected_at'] = '2026-10-15'
            elif change == 'coverage':
                p['context']['coverage']['complete'] = False
            elif change == 'missing_metric':
                p['rows'][0]['metrics']['spend'] = None
            else:
                p['rows'][0]['context']['currency'] = 'EUR'
            self.assertEqual(build_view(p, 'drivers')['status'], 'withheld', change)

    def test_preserves_analyzer_event_value_mismatch_guard(self):
        p = drivers()
        p['driver_request']['rate'] = 'purchase_roas'
        p['context']['purchase_event'] = 'other_purchase_scope'
        r = build_view(p, 'drivers')
        self.assertEqual(r['status'], 'withheld')
        self.assertIn('purchase_event_value_scope_mismatch', r['flags'])

    def test_common_scale_leaves_components_unchanged(self):
        p = drivers()
        before = build_view(p, 'drivers')
        for row in p['rows']:
            for metric in ('spend', 'impressions'):
                row['metrics'][metric] *= 7
        after = build_view(p, 'drivers')
        for key, value in before['components'].items():
            self.assertAlmostEqual(after['components'][key], value)

    def test_nonfinite_output_withheld_and_json_safe(self):
        p = drivers()
        for row in p['rows']:
            row['metrics'].update(spend=1e308, impressions=1e-308)
        r = build_view(p, 'drivers')
        self.assertEqual(r['status'], 'withheld')
        json.dumps(r, allow_nan=False)

    def test_duplicate_entity_slices_zero_period_and_reach_rejected(self):
        p = drivers()
        p['rows'][1]['entity_id'] = 'a'
        p['rows'][1]['context']['filters'] = {'placement': 'feed'}
        self.assertEqual(build_view(p, 'drivers')['status'], 'withheld')
        p = drivers()
        for row in p['rows'][:3]:
            row['metrics'].update(spend=0, impressions=0)
        self.assertEqual(build_view(p, 'drivers')['status'], 'withheld')
        p['driver_request']['rate'] = 'frequency'
        with self.assertRaises(ValueError):
            build_view(p, 'drivers')


if __name__ == '__main__':
    unittest.main()
