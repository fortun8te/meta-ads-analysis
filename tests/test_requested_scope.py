import copy
import unittest
from unittest.mock import patch

from scripts import analyze_meta as am
from scripts.analysis_views import build_view
from tests.test_review_pack import fixture

TARGET_CAMPAIGN = 'synthetic-campaign-target'


def scoped():
    p = fixture()
    p['requested_scope'] = {'level': 'campaign', 'entity_id': TARGET_CAMPAIGN}
    p['rows'] = [
        {'level': 'campaign', 'entity_id': TARGET_CAMPAIGN, 'metrics': {'spend': 30}},
        {'level': 'adset', 'entity_id': 's1', 'campaign_id': TARGET_CAMPAIGN, 'metrics': {'spend': 30}},
        {'level': 'ad', 'entity_id': 'ad1', 'adset_id': 's1', 'campaign_id': TARGET_CAMPAIGN, 'metrics': {'spend': 30}},
    ]
    return p


class RequestedScopeTests(unittest.TestCase):
    def test_target_campaign_plus_other_campaign_rejected_before_any_calculation(self):
        for row in ({'level': 'campaign', 'entity_id': 'synthetic-other-campaign', 'metrics': {'spend': 99}},
                    {'level': 'ad', 'entity_id': 'synthetic-other-ad', 'campaign_id': 'synthetic-third-campaign', 'metrics': {'spend': 99}},
                    {'level': 'account', 'entity_id': 'acct', 'metrics': {'spend': 99}}):
            p = scoped()
            p['rows'].append(row)
            with patch.object(am, 'derived', side_effect=AssertionError('No arithmetic before scope validation')):
                with self.assertRaisesRegex(ValueError, 'rows\\[3\\].*outside requested_scope'):
                    am.analyze(p)

    def test_missing_descendant_membership_rejected(self):
        p = scoped()
        del p['rows'][2]['campaign_id']
        with self.assertRaisesRegex(ValueError, 'lacks matching campaign_id'):
            am.analyze(p)

    def test_valid_mixed_target_campaign_levels_and_legacy_no_scope(self):
        p = scoped()
        result = am.analyze(p)
        self.assertEqual(len(result['rows']), 3)
        self.assertEqual(result['requested_scope'], p['requested_scope'])
        del p['requested_scope']
        p['rows'].append({'level': 'campaign', 'entity_id': 'synthetic-other-campaign', 'metrics': {'spend': 99}})
        self.assertEqual(len(am.analyze(p)['rows']), 4)
        self.assertNotIn('requested_scope', am.analyze(p))

    def test_other_hierarchy_levels_and_bad_scope(self):
        p = scoped()
        p['requested_scope'] = {'level': 'account', 'entity_id': 'acct'}
        self.assertEqual(len(am.analyze(p)['rows']), 3)
        p['requested_scope'] = {'level': 'adset', 'entity_id': 's1'}
        p['rows'] = p['rows'][1:]
        self.assertEqual(len(am.analyze(p)['rows']), 2)
        p['requested_scope'] = {'level': 'ad', 'entity_id': 'ad1'}
        p['rows'] = p['rows'][1:]
        self.assertEqual(len(am.analyze(p)['rows']), 1)
        for scope in (None, {}, {'level': 'campaign', 'entity_id': ''}, {'level': 'store', 'entity_id': TARGET_CAMPAIGN}):
            p = scoped()
            p['requested_scope'] = scope
            with self.assertRaises(ValueError):
                am.analyze(p)

    def test_all_views_enforce_scope_and_preserve_echo(self):
        p = scoped()
        for view in ('compact', 'focus'):
            output = build_view(p, view, fields=['metrics.spend'])
            self.assertEqual(output['metadata']['requested_scope'], p['requested_scope'])
        p['rows'].append({'level': 'ad', 'entity_id': 'external', 'campaign_id': 'synthetic-other-campaign', 'metrics': {}})
        for view in ('compact', 'focus', 'drivers'):
            with self.assertRaisesRegex(ValueError, 'outside requested_scope'):
                build_view(p, view, fields=['metrics.spend'])
        from tests.test_analysis_views import drivers
        p = drivers()
        p['requested_scope'] = {'level': 'campaign', 'entity_id': 'c1'}
        self.assertEqual(build_view(p, 'drivers')['requested_scope'], p['requested_scope'])

    def test_v1_adapter_scope_membership(self):
        p = fixture()
        p['requested_scope'] = {'level': 'campaign', 'entity_id': 'campaign1'}
        p['schema_version'] = 1
        p['ads'] = p.pop('rows')
        p['ads'][0]['ad_id'] = p['ads'][0].pop('entity_id')
        self.assertEqual(am.analyze(p)['requested_scope'], p['requested_scope'])
        p['ads'][0]['campaign_id'] = 'other'
        with self.assertRaises(ValueError):
            am.analyze(p)


if __name__ == '__main__':
    unittest.main()
