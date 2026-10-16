import datetime as dt
import unittest

from scripts import decisions as d

CONTEXT = {'account_id': 'act_1', 'currency': 'EUR', 'timezone': 'UTC', 'report_start': '2026-09-01',
           'report_end': '2026-09-30', 'attribution': '7d_click', 'counting_mode': 'all',
           'report_time_basis': 'impression', 'purchase_event': 'purchase', 'purchase_value_event': 'purchase'}
AS_OF = dt.date(2026, 10, 16)
CONFIG = {'target_cpa': 20}


def ad(entity, spend, purchases, clicks=150, name=None, adset='as_1', context=None, **metrics):
    return {'level': 'ad', 'entity_id': entity, 'adset_id': adset, 'name': name or entity, 'context': context or {},
            'metrics': {'spend': spend, 'impressions': 10000, 'link_clicks': clicks, 'landing_page_views': 100,
                        'purchases': purchases, 'purchase_value': purchases * 40, **metrics}}


def decide(*rows, as_of=AS_OF):
    result = d.decide({'schema_version': 2, 'context': CONTEXT, 'rows': list(rows)}, CONFIG, as_of)
    return {a['entity_id']: a for a in result['ads']}, result


class VerdictTests(unittest.TestCase):
    def test_rules(self):
        ads, _ = decide(ad('early', 15, 0), ad('dead', 40, 0), ad('pricey', 200, 6),
                        ad('winner', 180, 12), ad('meh', 100, 4))
        self.assertEqual((ads['early']['verdict'], ads['early']['reason']), ('wait', 'below_spend_floor'))
        self.assertEqual((ads['dead']['verdict'], ads['dead']['reason']), ('kill', 'no_purchases_at_spend_cap'))
        self.assertEqual((ads['pricey']['verdict'], ads['pricey']['reason']), ('kill', 'cpa_far_above_target'))
        self.assertEqual(ads['winner']['verdict'], 'scale')
        self.assertEqual(ads['meh']['verdict'], 'iterate')
        self.assertIsNotNone(ads['meh']['next_step'])

    def test_no_kill_or_scale_inside_conversion_lag(self):
        ads, _ = decide(ad('dead', 40, 0), ad('winner', 180, 12), as_of=dt.date(2026, 10, 2))
        self.assertEqual({a['verdict'] for a in ads.values()}, {'wait'})
        self.assertEqual(ads['dead']['reason'], 'inside_conversion_lag')

    def test_mixed_attribution_gets_no_verdict(self):
        ads, _ = decide(ad('a', 40, 0), ad('b', 40, 0), ad('c', 40, 0, context={'attribution': '1d_click'}))
        self.assertEqual((ads['c']['verdict'], ads['c']['reason']), ('none', 'mixed_attribution'))
        self.assertEqual(ads['a']['verdict'], 'kill')

    def test_iterate_reasons(self):
        ads, _ = decide(ad('low_ctr', 100, 4, clicks=50), ad('ok_ctr', 100, 4, clicks=200),
                        ad('ok_ctr_no_buy', 30, 0, clicks=200, landing_page_views=300))
        self.assertEqual(ads['low_ctr']['reason'], 'hook')
        self.assertEqual(ads['ok_ctr_no_buy']['reason'], 'post_click')
        self.assertIn('landing page', ads['ok_ctr_no_buy']['next_step'])

    def test_video_hook_and_hold(self):
        ads, _ = decide(ad('weak_hook', 100, 4, video_3s_views=1000, video_thruplays=500),
                        ad('weak_hold', 100, 4, video_3s_views=3000, video_thruplays=300))
        self.assertEqual(ads['weak_hook']['hook_rate'], 0.1)
        self.assertEqual(ads['weak_hook']['reason'], 'hook')
        self.assertEqual(ads['weak_hold']['hold_rate'], 0.1)
        self.assertEqual(ads['weak_hold']['reason'], 'hold')

    def test_low_spend_creatives_skip_deep_review_and_sort_by_spend(self):
        ads, result = decide(ad('small', 5, 0), ad('big', 300, 10))
        self.assertEqual(ads['small']['creative_review'], 'skip_low_spend')
        self.assertEqual(ads['big']['creative_review'], 'deep')
        self.assertEqual(result['ads'][0]['entity_id'], 'big')

    def test_config_requires_target_cpa(self):
        with self.assertRaises(ValueError):
            d.load_config({})


class FatigueTests(unittest.TestCase):
    def test_textbook_case_without_finality_fields(self):
        rows = []
        for start, end, freq, ctr, purchases in (('2026-09-07', '2026-09-13', 2, 1.5, 20),
                                                  ('2026-09-14', '2026-09-20', 3.5, 1.1, 14),
                                                  ('2026-09-21', '2026-09-27', 5, 0.7, 8)):
            rows.append(ad('tired', 500, purchases, clicks=int(100000 * ctr / 100),
                           context={'report_start': start, 'report_end': end},
                           impressions=100000, reach=int(100000 / freq)))
        ads, _ = decide(*rows)
        f = ads['tired']['fatigue']
        self.assertTrue(f['eligible'])
        self.assertTrue(f['fatigued'])
        self.assertGreaterEqual(f['ctr_drop_pct'], 20)

    def test_two_periods_not_enough(self):
        rows = [ad('x', 500, 10, context={'report_start': s, 'report_end': e}, reach=5000)
                for s, e in (('2026-09-07', '2026-09-13'), ('2026-09-14', '2026-09-20'))]
        self.assertFalse(decide(*rows)[0]['x']['fatigue']['eligible'])


class NamingTests(unittest.TestCase):
    def test_parse_name(self):
        self.assertEqual(d.parse_name('NANOX_relief_mechanism_ugc_v2'),
                         {'client': 'NANOX', 'concept': 'relief', 'angle': 'mechanism', 'hook': 'ugc', 'version': 2})
        self.assertIsNone(d.parse_name('Ad 3 copy'))

    def test_angle_rollups_need_two_ads_same_adset(self):
        _, result = decide(ad('1', 100, 5, name='N_c_pain_h1_v1'), ad('2', 100, 5, name='N_c_pain_h2_v1'),
                           ad('3', 100, 5, name='N_c_price_h1_v1'),
                           ad('4', 100, 5, name='N_c_price_h2_v1', adset='as_2'))
        self.assertEqual([(r['angle'], r['ads'], r['label']) for r in result['angle_rollups']],
                         [('pain', 2, 'directional')])
        self.assertEqual(result['angle_rollups'][0]['cpa'], 20)


if __name__ == '__main__':
    unittest.main()
