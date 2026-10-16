"""Regression checks for retrieval scope and explicitly reconciled child totals."""
import copy
import unittest

from scripts.analyze_meta import analyze
from tests.test_review_pack import fixture


def periods():
    p = fixture()
    after = copy.deepcopy(p['rows'][0])
    after['context'] = {'report_start': '2026-10-08', 'report_end': '2026-10-14'}
    p['rows'].append(after)
    return p


def reconciliation():
    p = fixture()
    p['rows'] = [
        {'level': 'campaign', 'entity_id': 'c1', 'metrics': {'spend': 30, 'purchases': 3}},
        {'level': 'adset', 'entity_id': 's1', 'campaign_id': 'c1', 'metrics': {'spend': 10, 'purchases': 1}},
        {'level': 'adset', 'entity_id': 's2', 'campaign_id': 'c1', 'metrics': {'spend': 20, 'purchases': 2}},
    ]
    p['reconciliations'] = [{'parent_row': 0, 'child_rows': [1, 2],
                             'metrics': ['spend', 'purchases'],
                             'children_disjoint': True, 'coverage_complete': True}]
    return p


class ScopeTests(unittest.TestCase):
    def test_different_filters_withhold_period_delta(self):
        p = periods()
        p['rows'][1]['context']['filters'] = {'publisher_platform': 'instagram'}
        self.assertEqual(analyze(p, compare_periods=True)['period_comparisons'], [])

    def test_coverage_unknown_incomplete_or_pending_withholds_delta(self):
        for coverage in (None, {}, {'complete': False}, {'complete': True, 'has_next_page': True}):
            p = periods()
            p['rows'][1]['context']['coverage'] = coverage
            c = analyze(p, compare_periods=True)['period_comparisons'][0]
            self.assertFalse(c['eligible'], coverage)
            self.assertEqual(c['deltas'], {})
        p = periods()
        del p['context']['coverage']
        self.assertFalse(analyze(p, compare_periods=True)['period_comparisons'][0]['eligible'])
        # Missing retrieval evidence does not suppress arithmetic on a single source row.
        self.assertEqual(analyze(p)['rows'][0]['derived_metrics']['purchase_roas'], 2.4)

    def test_interleaved_breakdowns_pair_same_slice(self):
        p = periods()
        p['rows'] = [dict(copy.deepcopy(r), breakdown={'placement': placement})
                     for r in p['rows'] for placement in ('feed', 'reels')]
        comparisons = analyze(p, compare_periods=True)['period_comparisons']
        self.assertEqual([(c['before_row'], c['after_row']) for c in comparisons], [(0, 2), (1, 3)])
        self.assertTrue(all(c['eligible'] for c in comparisons))

    def test_interleaved_filter_scopes_pair_corresponding_periods(self):
        p = periods()
        p['rows'] = [copy.deepcopy(row) for row in p['rows'] for _ in range(2)]
        for index, row in enumerate(p['rows']):
            row.setdefault('context', {})['filters'] = {'publisher_platform': 'facebook' if index % 2 == 0 else 'instagram'}
        comparisons = analyze(p, compare_periods=True)['period_comparisons']
        self.assertEqual([(c['before_row'], c['after_row']) for c in comparisons], [(0, 2), (1, 3)])
        self.assertTrue(all(c['eligible'] for c in comparisons))

    def test_filters_are_distinct_slices_for_duplicate_detection(self):
        p = fixture()
        other = copy.deepcopy(p['rows'][0])
        other['context'] = {'filters': {'publisher_platform': 'instagram'}}
        p['rows'].append(other)
        self.assertEqual(len(analyze(p)['rows']), 2)


class ReconciliationTests(unittest.TestCase):
    def test_complete_disjoint_children_match_without_aggregating_ratios(self):
        p = reconciliation()
        result = analyze(p)
        r = result['reconciliations'][0]
        self.assertEqual(r['status'], 'matched')
        self.assertEqual(r['metrics']['spend']['child_total'], 30)
        self.assertEqual(r['metrics']['purchases']['difference'], 0)
        self.assertNotIn('totals', result)
        self.assertEqual(len(result['rows']), 3)

    def test_no_implicit_reconciliation(self):
        p = reconciliation()
        del p['reconciliations']
        self.assertNotIn('reconciliations', analyze(p))

    def test_explicit_assertions_required(self):
        for key in ('children_disjoint', 'coverage_complete'):
            p = reconciliation()
            del p['reconciliations'][0][key]
            r = analyze(p)['reconciliations'][0]
            self.assertEqual(r['status'], 'withheld')
            self.assertIsNone(r['metrics']['spend']['child_total'])

    def test_incomplete_rows_override_complete_request(self):
        p = reconciliation()
        p['rows'][1]['context'] = {'coverage': {'complete': False}}
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'withheld')

    def test_missing_metrics_unknown_not_zero(self):
        p = reconciliation()
        del p['rows'][2]['metrics']['purchases']
        r = analyze(p)['reconciliations'][0]
        self.assertEqual(r['metrics']['spend']['status'], 'matched')
        self.assertEqual(r['metrics']['purchases']['status'], 'withheld')
        self.assertIsNone(r['metrics']['purchases']['child_total'])
        self.assertNotEqual(r['status'], 'matched')

    def test_mismatch_retained_and_only_explicit_tolerance_applied(self):
        p = reconciliation()
        p['rows'][2]['metrics']['spend'] = 20.01
        r = analyze(p)['reconciliations'][0]
        self.assertEqual(r['status'], 'mismatch')
        self.assertAlmostEqual(r['metrics']['spend']['difference'], .01)
        p['reconciliations'][0]['absolute_tolerances'] = {'spend': .02}
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'matched')

    def test_membership_window_breakdown_hierarchy_scope_guard(self):
        mutations = [
            {'campaign_id': 'wrong'}, {'context': {'report_end': '2026-10-06'}},
            {'context': {'currency': 'EUR'}}, {'context': {'attribution': None}},
            {'context': {'filters': {'status': 'ACTIVE'}}}, {'breakdown': {'placement': 'feed'}},
        ]
        for change in mutations:
            p = reconciliation()
            p['rows'][1].update(change)
            r = analyze(p)['reconciliations'][0]
            self.assertEqual(r['status'], 'withheld', change)

    def test_homogeneous_descendants_with_verified_parent_membership(self):
        p = reconciliation()
        for row in p['rows'][1:]:
            row['level'] = 'ad'
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'matched')
        p['rows'][1]['level'] = 'adset'
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'withheld')
        p['rows'][1]['level'] = 'ad'
        p['rows'][0] = {'level': 'account', 'entity_id': 'acct', 'metrics': {'spend': 30, 'purchases': 3}}
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'matched')
        for row in p['rows'][1:]:
            row['level'] = 'adset'
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'matched')
        p['rows'][0] = {'level': 'campaign', 'entity_id': 'c1', 'metrics': {'spend': 30, 'purchases': 3}}
        del p['rows'][1]['campaign_id']
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'withheld')

    def test_unknown_filters_withhold_comparison_and_reconciliation(self):
        for absent in (True, False):
            p = periods()
            r = reconciliation()
            for data in (p, r):
                if absent:
                    del data['context']['filters']
                else:
                    data['context']['filters'] = None
            self.assertFalse(analyze(p, compare_periods=True)['period_comparisons'][0]['eligible'])
            self.assertEqual(analyze(r)['reconciliations'][0]['status'], 'withheld')
        for empty in ({}, []):
            p = periods()
            r = reconciliation()
            for data in (p, r):
                data['context']['filters'] = empty
            self.assertTrue(analyze(p, compare_periods=True)['period_comparisons'][0]['eligible'])
            self.assertEqual(analyze(r)['reconciliations'][0]['status'], 'matched')

    def test_coverage_flags_must_be_boolean_when_present(self):
        for key in ('complete', 'has_next_page'):
            for value in (None, 'false', 'true', 0, 1, [], {}):
                p = fixture()
                p['context']['coverage'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    analyze(p)
        p = periods()
        self.assertTrue(analyze(p, compare_periods=True)['period_comparisons'][0]['eligible'])

    def test_unique_ratios_arbitrary_metrics_and_duplicate_indices_rejected(self):
        for metric in ('reach', 'frequency', 'purchase_roas', 'arbitrary'):
            p = reconciliation()
            p['reconciliations'][0]['metrics'] = [metric]
            with self.assertRaises(ValueError):
                analyze(p)
        p = reconciliation()
        p['reconciliations'][0]['child_rows'] = [1, 1]
        with self.assertRaises(ValueError):
            analyze(p)

    def test_same_entity_multiple_slices_not_summed(self):
        p = reconciliation()
        p['rows'][2]['entity_id'] = 's1'
        p['rows'][2]['context'] = {'report_start': '2026-10-02'}
        r = analyze(p)['reconciliations'][0]
        self.assertEqual(r['status'], 'withheld')
        self.assertIn('repeated_child_entity', r['metrics']['spend']['flags'])

    def test_optional_event_scope_required(self):
        p = reconciliation()
        p['reconciliations'][0]['metrics'] = ['leads']
        for r, count in zip(p['rows'], (3, 1, 2)):
            r['metrics']['leads'] = count
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'withheld')
        p['context']['metric_scopes'] = {'leads': 'website_lead_all'}
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'matched')

    def test_delivery_reconciliation_ignores_unrelated_conversion_context(self):
        p = reconciliation()
        p['rows'][0] = {'level': 'account', 'entity_id': 'acct', 'metrics': {'spend': 30, 'impressions': 300, 'purchases': 3}}
        for row, count in zip(p['rows'][1:], (100, 200)):
            row['metrics']['impressions'] = count
        p['rows'][0]['context'] = {'objective': None, 'funnel': None, 'attribution': None,
                                  'purchase_event': None, 'purchase_value_event': None,
                                  'counting_mode': None, 'report_time_basis': None,
                                  'metric_scopes': {'leads': 'unknown'}}
        p['rows'][1]['context'] = {'objective': 'leads', 'metric_scopes': {'leads': 'website'}}
        p['reconciliations'][0]['metrics'] = ['spend', 'impressions', 'purchases']
        r = analyze(p)['reconciliations'][0]
        self.assertEqual(r['metrics']['spend']['status'], 'matched')
        self.assertEqual(r['metrics']['impressions']['status'], 'matched')
        self.assertEqual(r['metrics']['purchases']['status'], 'withheld')
        self.assertIn('context_unknown:purchase_event', r['metrics']['purchases']['flags'])

    def test_reconciliation_scope_is_per_requested_metric(self):
        p = reconciliation()
        p['rows'][1]['context'] = {'purchase_value_event': 'omni_purchase',
                                  'metric_scopes': {'leads': 'unique'}}
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'matched')
        p['rows'][1]['context']['purchase_event'] = 'omni_purchase'
        r = analyze(p)['reconciliations'][0]
        self.assertEqual(r['metrics']['spend']['status'], 'matched')
        self.assertEqual(r['metrics']['purchases']['status'], 'withheld')
        p = reconciliation()
        p['reconciliations'][0]['metrics'] = ['leads']
        p['context']['metric_scopes'] = {'leads': 'website_all', 'checkout_initiated': 'website'}
        for row, count in zip(p['rows'], (3, 1, 2)):
            row['metrics']['leads'] = count
        p['rows'][1]['context'] = {'metric_scopes': {'leads': 'website_all', 'checkout_initiated': 'other'}}
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'matched')
        p['rows'][1]['context']['metric_scopes']['leads'] = 'unique'
        self.assertEqual(analyze(p)['reconciliations'][0]['status'], 'withheld')

    def test_nonfinite_sum_is_withheld(self):
        p = reconciliation()
        for r in p['rows']:
            r['metrics']['spend'] = 1e308
        r = analyze(p)['reconciliations'][0]
        self.assertEqual(r['metrics']['spend']['status'], 'withheld')
        self.assertIsNone(r['metrics']['spend']['child_total'])


if __name__ == '__main__':
    unittest.main()
