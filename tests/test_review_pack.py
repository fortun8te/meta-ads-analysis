import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import analyze_meta as am
from scripts import review_pack as rp


def fixture():
    return {'schema_version': 2, 'mode': 'metrics', 'context': {
        'account_id': 'acct', 'currency': 'USD', 'timezone': 'Europe/Amsterdam',
        'report_start': '2026-10-01', 'report_end': '2026-10-07',
        'attribution': {'click': 7, 'view': 1}, 'purchase_event': 'website_purchase',
        'purchase_value_event': 'website_purchase', 'objective': 'sales',
        'funnel': 'prospecting', 'counting_mode': 'all', 'report_time_basis': 'impression',
        'source_path': 'raw.json', 'collected_at': '2026-10-08', 'is_final': True, 'coverage': {'complete': True}, 'filters': {}},
        'rows': [{'level': 'ad', 'entity_id': 'ad1', 'campaign_id': 'campaign1',
                  'adset_id': 'adset1', 'metrics': {'spend': 50, 'impressions': 1000,
                   'reach': 500, 'clicks_all': 100, 'link_clicks': 40, 'outbound_clicks': 25,
                   'landing_page_views': 20, 'purchases': 2, 'purchase_value': 120}}]}


class AnalysisTests(unittest.TestCase):
    def test_all_levels_preserved_no_totals_or_ratio_average(self):
        p = fixture()
        for level, id_ in [('account', 'acct'), ('campaign', 'campaign1'), ('adset', 'adset1')]:
            p['rows'].append({'level': level, 'entity_id': id_, 'metrics': {
                'spend': 200, 'impressions': 3000, 'reach': 900, 'purchases': 20,
                'purchase_value': 700}})
        result = am.analyze(p)
        self.assertEqual([r['level'] for r in result['rows']], ['ad', 'account', 'campaign', 'adset'])
        self.assertEqual(result['rows'][1]['derived_metrics']['purchase_cpa'], 10)
        self.assertAlmostEqual(result['rows'][1]['derived_metrics']['frequency'], 3000/900)
        self.assertNotIn('totals', result)
        self.assertNotIn('summary', result)
        self.assertTrue(any('Mixed hierarchy' in flag for flag in result['flags']))

    def test_core_formulas_source_totals_and_denominators(self):
        row = am.analyze(fixture())['rows'][0]
        expected = {'frequency': 2, 'ctr_all_pct': 10, 'ctr_link_pct': 4,
                    'ctr_outbound_pct': 2.5, 'cpc_all': .5, 'cpc_link': 1.25,
                    'cpc_outbound': 2, 'cpm': 50, 'purchase_cpa': 25,
                    'purchase_roas': 2.4, 'purchases_per_lpv_pct': 10,
                    'lpv_per_outbound_pct': 80}
        for key, value in expected.items():
            self.assertAlmostEqual(row['derived_metrics'][key], value)
            self.assertEqual(row['derived_status'][key], 'computed')
        self.assertEqual(am.FORMULAS['ctr_link_pct'][:3], ('link_clicks', 'impressions', 100))

    def test_unknown_reporting_basis_is_visible_without_blocking_native_arithmetic(self):
        p = fixture()
        p['context']['counting_mode'] = None
        p['context']['report_time_basis'] = None
        row = am.analyze(p)['rows'][0]
        self.assertEqual(row['derived_metrics']['purchase_cpa'], 25)
        self.assertIn('Missing context: counting_mode', row['warnings'])
        self.assertIn('Missing context: report_time_basis', row['warnings'])

    def test_ids_level_and_account_validation(self):
        mutations = [('entity_id', 9007199254740993), ('level', 'advertisement'),
                     ('account_id', 'other'), ('entity_id', ''), ('ad_id', 'wrong')]
        for key, value in mutations:
            p = fixture()
            p['rows'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                am.analyze(p)
        p = fixture()
        p['rows'][0]['context'] = {'account_id': 'other'}
        with self.assertRaises(ValueError):
            am.analyze(p)
        p = fixture()
        p['rows'][0] = {'level': 'account', 'entity_id': 'wrong', 'metrics': {}}
        with self.assertRaises(ValueError):
            am.analyze(p)

    def test_parent_row_child_id_rejected(self):
        p = fixture()
        p['rows'][0] = {'level': 'campaign', 'entity_id': 'c1', 'adset_id': 's1', 'metrics': {}}
        with self.assertRaisesRegex(ValueError, 'child entity ID'):
            am.analyze(p)

    def test_v1_adapter_and_alias(self):
        p = fixture()
        p['schema_version'] = 1
        p['ads'] = p.pop('rows')
        p['ads'][0]['ad_id'] = p['ads'][0].pop('entity_id')
        p['ads'][0].pop('level')
        result = rp.analyze(p)
        self.assertEqual(result['input_schema_version'], 1)
        self.assertEqual(result['ads'], result['rows'])
        self.assertEqual(result['rows'][0]['entity_id'], 'ad1')

    def test_metrics_mode_no_media_reads_or_creative_requirements(self):
        p = fixture()
        p['rows'][0]['media'] = [{'path': '/definitely/not/a/file'}]
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No media IO')), patch.object(Path, 'read_text', side_effect=AssertionError('No media IO')):
            result = am.analyze(p)
        self.assertFalse(result['rows'][0]['creative_review_requested'])
        self.assertFalse(any('copy' in w.lower() or 'media' in w.lower() or 'creative' in w.lower()
                             for w in result['rows'][0]['warnings']))
        self.assertNotIn('period_comparisons', result)

    def test_auto_creative_requires_evidence_and_explicit_metrics_overrides(self):
        p = fixture()
        p.pop('mode')
        self.assertFalse(am.analyze(p)['rows'][0]['creative_review_requested'])
        p['rows'][0]['creative_id'] = 'c1'
        row = am.analyze(p)['rows'][0]
        self.assertTrue(row['creative_review_requested'])
        self.assertTrue(any('No media' in w for w in row['warnings']))
        self.assertFalse(am.analyze(p, mode='metrics')['rows'][0]['creative_review_requested'])
        p['rows'][0] = {'level': 'campaign', 'entity_id': 'c1', 'metrics': {}}
        self.assertFalse(am.analyze(p, mode='creative')['rows'][0]['creative_review_requested'])

    def test_zero_unknown_and_status_distinction(self):
        p = fixture()
        row = p['rows'][0]
        row['metrics'] = {'spend': 0, 'impressions': 100, 'reach': 0, 'purchases': 0, 'purchase_value': 0}
        row['metric_status'] = {'purchase_value': 'unsupported'}
        r = am.analyze(p)['rows'][0]
        self.assertEqual(r['metrics']['spend'], 0)
        self.assertIsNone(r['metrics']['clicks_all'])
        self.assertIsNone(r['metrics']['purchase_value'])
        self.assertEqual(r['source_metrics']['purchase_value'], 0)
        self.assertEqual(r['derived_metrics']['cpm'], 0)
        self.assertEqual(r['derived_status']['purchase_cpa'], 'undefined_zero_denominator')
        self.assertEqual(r['derived_status']['frequency'], 'undefined_zero_denominator')
        self.assertEqual(r['derived_status']['purchase_roas'], 'unknown')

    def test_invalid_core_values(self):
        for invalid in (True, -1, '50', float('inf'), float('nan'), [], {}, 10**1000):
            p = fixture()
            p['rows'][0]['metrics']['spend'] = invalid
            with self.subTest(value=str(invalid)[:30]), self.assertRaises(ValueError):
                am.analyze(p)

    def test_status_validation_and_optional_unsupported(self):
        for status in ('unknown', 'suppressed', 'unsupported', 'failed'):
            p = fixture()
            p['rows'][0]['metric_status'] = {'leads': status}
            r = am.analyze(p)['rows'][0]
            self.assertIsNone(r['metrics']['leads'])
            self.assertEqual(r['metric_status']['leads'], status)
        for bad in ({'spend': 'bogus'}, {'missing': 'reported'}, {'leads': 'reported'}, []):
            p = fixture()
            p['rows'][0]['metric_status'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                am.analyze(p)

    def test_event_value_scope_mismatch_and_unknown_scope(self):
        p = fixture()
        p['context']['purchase_value_event'] = 'omni_purchase'
        r = am.analyze(p)['rows'][0]
        self.assertIsNone(r['derived_metrics']['purchase_roas'])
        self.assertEqual(r['derived_status']['purchase_roas'], 'withheld_event_value_scope_mismatch')
        self.assertEqual(r['derived_metrics']['purchase_cpa'], 25)
        del p['context']['purchase_value_event']
        r = am.analyze(p)['rows'][0]
        self.assertEqual(r['derived_metrics']['purchase_roas'], 2.4)
        self.assertEqual(r['derived_status']['purchase_roas'], 'computed_scope_unverified')

    def test_extra_metrics_and_source_metadata_preserved(self):
        p = fixture()
        p['request_id'] = 'r1'
        p['source'] = {'tool': 'official', 'raw': ['a', 'b']}
        p['rows'][0]['source'] = {'request': 'r1'}
        p['rows'][0]['metrics'].update(add_to_cart=10, checkout_initiated=4, leads=5,
            video_plays=100, video_3s_views=40, video_thruplays=20,
            video_100_views=10, custom_conversion=3, frequency=99,
            actions=[{'action_type': 'purchase', 'value': '2'}])
        r = am.analyze(p)
        row = r['rows'][0]
        self.assertEqual(row['derived_metrics']['frequency'], 2)
        self.assertEqual(row['metrics']['frequency'], 99)
        self.assertEqual(row['derived_metrics']['lead_cpa'], 10)
        self.assertEqual(row['derived_metrics']['add_to_cart_cpa'], 5)
        self.assertEqual(row['derived_metrics']['checkout_cpa'], 12.5)
        self.assertEqual(row['derived_metrics']['thruplays_per_video_play_pct'], 20)
        self.assertEqual(row['source_metrics']['actions'], p['rows'][0]['metrics']['actions'])
        self.assertEqual(row['source']['request'], 'r1')
        self.assertEqual(r['source_metadata']['source'], p['source'])
        self.assertNotIn('actions', row['metrics'])

    def test_duplicates_include_levels_and_account(self):
        p = fixture()
        p['rows'].append(copy.deepcopy(p['rows'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            am.analyze(p)
        p['rows'][1] = {'level': 'campaign', 'entity_id': 'ad1', 'metrics': {}}
        self.assertEqual(len(am.analyze(p)['rows']), 2)
        p['context'].pop('account_id')
        p['rows'][0]['account_id'] = 'one'
        p['rows'][1] = copy.deepcopy(p['rows'][0])
        p['rows'][1]['account_id'] = 'two'
        self.assertEqual(len(am.analyze(p)['rows']), 2)

    def test_semantic_slices_retained_overlap_warns(self):
        for key, value in [('attribution', '1d click'), ('purchase_event', 'omni'),
                           ('counting_mode', 'unique'), ('report_time_basis', 'conversion')]:
            p = fixture()
            second = copy.deepcopy(p['rows'][0])
            second['context'] = {key: value}
            p['rows'].append(second)
            rows = am.analyze(p)['rows']
            self.assertTrue(all(any('overlap' in w for w in row['warnings']) for row in rows))
        p = fixture()
        second = copy.deepcopy(p['rows'][0])
        second['breakdown'] = {'placement': 'feed'}
        p['rows'].append(second)
        self.assertEqual(len(am.analyze(p)['rows']), 2)

    def test_matched_period_delta_correct_no_averaging(self):
        p = fixture()
        second = copy.deepcopy(p['rows'][0])
        second['context'] = {'report_start': '2026-10-08', 'report_end': '2026-10-14'}
        second['metrics'].update(spend=100, purchases=8, purchase_value=400, impressions=3000, reach=1000)
        p['rows'].append(second)
        r = am.analyze(p, compare_periods=True)
        comparison = r['period_comparisons'][0]
        self.assertTrue(comparison['eligible'])
        self.assertEqual(comparison['deltas']['metrics.spend']['percent'], 100)
        self.assertEqual(comparison['deltas']['derived_metrics.purchase_cpa']['absolute'], -12.5)
        self.assertEqual(r['rows'][1]['derived_metrics']['frequency'], 3)

    def test_period_comparisons_block_incompatible_unknown_provisional_overlap(self):
        cases = [{'attribution': '1d click'}, {'currency': 'EUR'}, {'timezone': None},
                 {'purchase_event': None}, {'purchase_value_event': None},
                 {'is_final': False}, {'provisional': True}, {'report_start': '2026-10-07'},
                 {'report_end': '2026-10-15'}, {'metric_scopes': {'leads': 'unique'}}]
        for changes in cases:
            p = fixture()
            second = copy.deepcopy(p['rows'][0])
            second['context'] = {'report_start': '2026-10-08', 'report_end': '2026-10-14', **changes}
            p['rows'].append(second)
            c = am.analyze(p, compare_periods=True)['period_comparisons'][0]
            self.assertFalse(c['eligible'], changes)
            self.assertEqual(c['deltas'], {})

    def test_period_unknown_and_zero_baseline(self):
        p = fixture()
        p['rows'][0]['metrics']['purchases'] = 0
        second = copy.deepcopy(p['rows'][0])
        second['metrics']['purchases'] = 2
        second['context'] = {'report_start': '2026-10-08', 'report_end': '2026-10-14'}
        p['rows'].append(second)
        d = am.analyze(p, compare_periods=True)['period_comparisons'][0]['deltas']
        self.assertEqual(d['metrics.purchases'], {'absolute': 2, 'percent': None, 'status': 'percent_undefined_zero_baseline'})
        self.assertIsNone(d['derived_metrics.purchase_cpa']['absolute'])

    def test_invalid_reporting_windows(self):
        for dates in ({'report_start': 'bad'}, {'report_end': '2026-09-01'}):
            p = fixture()
            p['context'].update(dates)
            with self.assertRaises(ValueError):
                am.analyze(p)

    def test_input_not_mutated(self):
        p = fixture()
        before = copy.deepcopy(p)
        am.analyze(p)
        self.assertEqual(p, before)

    def test_cli_json_stdout_only_and_optional_json_file(self):
        for script in ('analyze_meta.py', 'review_pack.py'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                input_path = root / 'input.json'
                input_path.write_text(json.dumps(fixture()))
                base = [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts' / script), str(input_path)]
                proc = subprocess.run(base, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(json.loads(proc.stdout)['rows'][0]['level'], 'ad')
                self.assertEqual(sorted(p.name for p in root.iterdir()), ['input.json'])
                proc = subprocess.run(base + ['--out', str(root / 'out')], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(sorted(p.name for p in (root / 'out').iterdir()), ['analysis.json'])
                self.assertEqual(json.loads(proc.stdout), json.loads((root/'out'/'analysis.json').read_text()))
                self.assertFalse(list(root.rglob('*.html')))

    def test_output_source_symlink_hardlink_and_media_safety(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = root / 'analysis.json'
            input_path.write_text(json.dumps(fixture()))
            original = input_path.read_bytes()
            a = am.analyze(fixture())
            with self.assertRaises(ValueError):
                am.persist(a, input_path, root, force=True)
            out = root / 'out'
            out.mkdir()
            target = out / 'analysis.json'
            target.symlink_to(input_path)
            with self.assertRaises(ValueError):
                am.persist(a, input_path, out, force=True)
            target.unlink()
            import os
            os.link(input_path, target)
            with self.assertRaises(ValueError):
                am.persist(a, input_path, out, force=True)
            target.unlink()
            a['rows'][0]['media'] = [{'path': str(target)}]
            with self.assertRaises(ValueError):
                am.persist(a, input_path, out, force=True)
            self.assertEqual(input_path.read_bytes(), original)
            link = root / 'alias'
            link.symlink_to(out, target_is_directory=True)
            with self.assertRaises(ValueError):
                am.persist(a, input_path, link, force=True)

    def test_force_replaces_only_generated_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = root / 'input.json'
            input_path.write_text('{}')
            out = root / 'out'
            out.mkdir()
            (out/'unrelated.txt').write_text('retain')
            am.persist(am.analyze(fixture()), input_path, out, force=True)
            self.assertEqual((out/'unrelated.txt').read_text(), 'retain')
            self.assertFalse((out/'review.html').exists())


if __name__ == '__main__':
    unittest.main()
