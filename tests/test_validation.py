import unittest

from scripts import analyze_meta as am

CONTEXT = {'account_id': 'act_1', 'currency': 'EUR', 'timezone': 'UTC', 'report_start': '2026-10-01',
           'report_end': '2026-10-07', 'attribution': '7d_click', 'counting_mode': 'all',
           'report_time_basis': 'impression', 'purchase_event': 'purchase', 'purchase_value_event': 'purchase'}


def run(*rows):
    return am.analyze({'schema_version': 2, 'context': CONTEXT,
                       'rows': [{'level': 'ad', 'entity_id': str(i), **row} for i, row in enumerate(rows)]})['rows']


def has(row, prefix):
    return any(w.startswith(prefix) for w in row['warnings'])


class ValidationTests(unittest.TestCase):
    def test_tiny_sample_roas_is_flagged_with_counts(self):
        row = run({'metrics': {'spend': 4, 'impressions': 500, 'purchases': 1, 'purchase_value': 120}})[0]
        self.assertEqual(row['derived_metrics']['purchase_roas'], 30)
        self.assertTrue(row['low_volume'])
        self.assertTrue(has(row, 'Low volume: 1 purchases on 4 spend'))
        self.assertEqual(row['counts'], {'spend': 4, 'impressions': 500, 'purchases': 1, 'purchase_value': 120})
        big = run({'metrics': {'spend': 400, 'impressions': 9000, 'purchases': 12, 'purchase_value': 900}})[0]
        self.assertFalse(big['low_volume'])

    def test_broken_rows_are_flagged(self):
        zero, spend_only, fine = run({'metrics': {'spend': 200, 'impressions': 0}}, {'metrics': {'spend': 50}},
                                     {'metrics': {'spend': 50, 'impressions': 1000}})
        self.assertTrue(has(zero, 'Broken row: spend with zero impressions'))
        self.assertTrue(has(spend_only, 'Broken row: only spend supplied'))
        self.assertFalse(has(fine, 'Broken row'))

    def test_numeric_strings_are_coerced_not_fatal(self):
        clean, bad = run({'metrics': {'spend': '12', 'impressions': '1,000'}}, {'metrics': {'spend': 'n/a'}})
        self.assertEqual(clean['metrics']['spend'], 12)
        self.assertEqual(clean['derived_metrics']['cpm'], 12)
        self.assertFalse(has(clean, 'Unparseable'))
        self.assertIsNone(bad['metrics']['spend'])
        self.assertTrue(has(bad, "Unparseable metric: spend='n/a'"))

    def test_mixed_attribution_flags_minority_rows(self):
        rows = run({'metrics': {'spend': 1}}, {'metrics': {'spend': 1}},
                   {'context': {'attribution': '1d_click'}, 'metrics': {'spend': 1}})
        self.assertEqual([r['attribution_mixed'] for r in rows], [False, False, True])
        self.assertTrue(has(rows[2], 'Mixed attribution'))
        tie = run({'metrics': {'spend': 1}}, {'context': {'attribution': '1d_click'}, 'metrics': {'spend': 1}})
        self.assertEqual([r['attribution_mixed'] for r in tie], [True, True])

    def test_missing_purchase_value_is_flagged(self):
        row = run({'metrics': {'spend': 10, 'impressions': 100, 'purchases': 3}})[0]
        self.assertTrue(has(row, 'Purchase value missing'))
        self.assertIsNone(row['derived_metrics']['purchase_roas'])


if __name__ == '__main__':
    unittest.main()
