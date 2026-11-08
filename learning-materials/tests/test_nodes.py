"""测试真实 Coze main；模型候选为手工夹具，不代表模型实测。"""
import asyncio
import copy
import json
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

def node(name, **params):
    path = ROOT / 'nodes' / (name + '.py')
    if not path.exists():
        raise AssertionError('待实现节点: ' + name)
    ns = runpy.run_path(str(path), init_globals={'Args': object, 'Output': dict})
    return asyncio.run(ns['main'](SimpleNamespace(params=params)))

def record(ticket_id='T001'):
    return {'ticket_id': ticket_id, 'messages': [
        {'role': 'customer', 'text': '我的包裹三天没更新了。'},
        {'role': 'agent', 'text': '您好，我帮您联系物流核实。'}]}

def prepared(rec=None):
    return node('01_prepare', record_json=json.dumps(rec or record(), ensure_ascii=False))['prepared_json']

def rules():
    return [{'rule_id': 'R01', 'version': '1.0', 'policy': '客服不得辱骂、嘲讽或贬低客户。'},
            {'rule_id': 'R02', 'version': '1.0', 'policy': '客服不得索取客户的账户密码、支付密码或支付验证码。'},
            {'rule_id': 'R03', 'version': '1.0', 'policy': '退款须经售后审核；审核通过后预计1至3个工作日原路退回，客服不得保证具体到账时点。'}]

def candidate():
    return {'category': '物流配送', 'category_confidence': 0.96,
            'category_evidence': [{'message_index': 0, 'quote': '我的包裹三天没更新了。'}],
            'summary': '客户查询物流停滞。', 'needs_review': False, 'review_reasons': [],
            'checks': [{'rule_id': r['rule_id'], 'status': 'pass', 'rule_quote': r['policy'],
                        'reason': '当前客服回复未显示该项违规。',
                        'evidence': [{'message_index': 1, 'quote': '您好，我帮您联系物流核实。'}]}
                       for r in rules()]}

def validate(c=None, rec=None, rs=None):
    return node('03_validate', prepared_json=prepared(rec),
                rules_json=json.dumps(rules() if rs is None else rs, ensure_ascii=False),
                analysis_json=json.dumps(candidate() if c is None else c, ensure_ascii=False))

def result(*args, **kwargs):
    return json.loads(validate(*args, **kwargs)['result_json'])

class PrepareTests(unittest.TestCase):
    def test_valid_input(self):
        self.assertTrue(node('01_prepare', record_json=json.dumps(record()))['valid'])

    def test_invalid_json_routes_review(self):
        p = node('01_prepare', record_json='{')
        self.assertFalse(p['valid'])
        self.assertIn('invalid_json', json.loads(p['prepared_json'])['errors'])

    def test_role_is_not_inferred(self):
        r = record(); r['messages'][1]['role'] = 'assistant'
        self.assertFalse(node('01_prepare', record_json=json.dumps(r))['valid'])

    def test_only_customer_routes_review(self):
        r = record(); r['messages'] = r['messages'][:1]
        self.assertFalse(node('01_prepare', record_json=json.dumps(r))['valid'])

    def test_long_input_is_not_silently_truncated(self):
        r = record(); r['messages'][0]['text'] = '字' * 20001
        p = node('01_prepare', record_json=json.dumps(r))
        self.assertFalse(p['valid'])
        self.assertEqual(json.loads(p['prepared_json'])['messages'], [])

class RulesTests(unittest.TestCase):
    def hits(self):
        return [{'content': 'RULE_ID: '+r['rule_id']+'\nRULE_VERSION: 1.0\nPOLICY: '+r['policy']+'\nNOTES: 测试。'} for r in rules()]

    def test_all_rules_are_loaded(self):
        out = node('02_rules', hits=self.hits())
        self.assertTrue(out['rules_ok'])
        self.assertEqual(len(json.loads(out['rules_json'])), 3)

    def test_missing_rule_is_not_filled_from_memory(self):
        out = node('02_rules', hits=self.hits()[:2])
        self.assertFalse(out['rules_ok'])
        self.assertEqual(len(json.loads(out['rules_json'])), 2)

    def test_conflicting_rule_is_rejected(self):
        h = self.hits(); h.append({'content': 'RULE_ID: R01\nRULE_VERSION: 1.0\nPOLICY: 随意承诺。'})
        self.assertFalse(node('02_rules', hits=h)['rules_ok'])

    def test_metadata_is_not_treated_as_retrieved_policy(self):
        self.assertFalse(node('02_rules', hits=[{'title': self.hits()[0]['content']}])['rules_ok'])

class ValidateTests(unittest.TestCase):
    def test_valid_pass_routes_logistics(self):
        out = result()
        self.assertFalse(out['needs_review'])
        self.assertEqual(out['route'], '物流客服')
        self.assertEqual(out['qc_status'], 'pass')

    def test_fabricated_quote_cannot_pass(self):
        c = candidate(); c['checks'][0]['evidence'][0]['quote'] = '不存在的原文'
        out = result(c)
        self.assertTrue(out['needs_review'])
        self.assertEqual(out['qc_status'], 'undetermined')

    def test_customer_words_are_not_agent_evidence(self):
        c = candidate(); c['checks'][0]['status'] = 'fail'
        c['checks'][0]['evidence'] = [{'message_index': 0, 'quote': '我的包裹三天没更新了。'}]
        self.assertTrue(result(c)['needs_review'])
        self.assertNotEqual(result(c)['qc_status'], 'violation')

    def test_boolean_index_is_not_integer_index(self):
        c = candidate(); c['checks'][0]['evidence'][0]['message_index'] = True
        self.assertTrue(result(c)['needs_review'])

    def test_unknown_is_not_pass(self):
        c = candidate(); c['checks'][2].update(status='unknown', evidence=[], reason='规则解释不足')
        out = result(c)
        self.assertTrue(out['needs_review'])
        self.assertEqual(out['qc_status'], 'undetermined')

    def test_verified_violation_is_separate_from_review(self):
        rec = record(); rec['messages'][1]['text'] = '这都看不懂？'
        c = candidate()
        for check in c['checks']:
            check['evidence'] = [{'message_index': 1, 'quote': '这都看不懂？'}]
        c['checks'][0].update(status='fail', reason='嘲讽客户')
        out = result(c, rec)
        self.assertEqual(out['qc_status'], 'violation')
        self.assertFalse(out['needs_review'])

    def test_rule_quote_must_belong_to_same_rule(self):
        c = candidate(); c['checks'][0]['rule_quote'] = rules()[1]['policy']
        self.assertTrue(result(c)['needs_review'])

    def test_rule_quote_must_be_complete_policy(self):
        c = candidate()
        for check in c['checks']:
            check['rule_quote'] = '客服'
        self.assertTrue(result(c)['needs_review'])

    def test_non_string_category_routes_review_without_crash(self):
        for malformed in ([], {}):
            c = candidate(); c['category'] = malformed
            self.assertTrue(result(c)['needs_review'])

    def test_missing_rule_routes_review(self):
        self.assertTrue(result(rs=rules()[:2])['needs_review'])

    def test_duplicate_rule_checks_rejected(self):
        c = candidate(); c['checks'][2] = copy.deepcopy(c['checks'][0])
        self.assertTrue(result(c)['needs_review'])

    def test_low_confidence_routes_review(self):
        c = candidate(); c['category_confidence'] = 0.4
        self.assertTrue(result(c)['needs_review'])

    def test_nan_confidence_rejected(self):
        c = candidate(); c['category_confidence'] = float('nan')
        self.assertTrue(result(c)['needs_review'])

    def test_model_cannot_assign_ticket_identity(self):
        c = candidate(); c['ticket_id'] = 'ATTACK'
        self.assertEqual(result(c)['ticket_id'], 'T001')

    def test_model_output_json_failure(self):
        out = node('03_validate', prepared_json=prepared(), rules_json=json.dumps(rules()), analysis_json='not json')
        self.assertTrue(out['needs_review'])

    def test_whole_input_invalid(self):
        p = node('01_prepare', record_json='null')['prepared_json']
        out = node('03_validate', prepared_json=p, rules_json=json.dumps(rules()), analysis_json=json.dumps(candidate()))
        self.assertTrue(out['needs_review'])

    def test_pass_without_agent_evidence_rejected(self):
        c = candidate(); c['checks'][0]['evidence'] = []
        self.assertTrue(result(c)['needs_review'])

class OutputTests(unittest.TestCase):
    def test_fallback_is_explicit_review(self):
        out = node('04_fallback', prepared_json=prepared(), failure_code='model_error')
        r = json.loads(out['result_json'])
        self.assertTrue(r['needs_review'])
        self.assertEqual(r['qc_status'], 'undetermined')

    def test_report_shows_quote_and_route(self):
        out = node('05_render', result_json=validate()['result_json'])
        self.assertIn('物流客服', out['report'])
        self.assertIn('您好，我帮您联系物流核实。', out['report'])

class BatchTests(unittest.TestCase):
    def items(self):
        return node('06_batch_prepare', records_json=json.dumps([record('T001'), record('T002')]))['items']

    def test_duplicate_ticket_ids_reject_entire_batch(self):
        out = node('06_batch_prepare', records_json=json.dumps([record(), record()]))
        self.assertFalse(out['valid']); self.assertEqual(out['items'], [])

    def test_invalid_conversation_is_kept_for_single_review(self):
        r = record(); r['messages'] = []
        out = node('06_batch_prepare', records_json=json.dumps([r]))
        self.assertTrue(out['valid']); self.assertEqual(len(out['items']), 1)

    def test_batch_limit_is_enforced(self):
        out = node('06_batch_prepare', records_json=json.dumps([record(str(i)) for i in range(51)]))
        self.assertFalse(out['valid'])

    def test_out_of_order_results_link_by_id(self):
        items = self.items(); r1 = result(rec=record('T001')); r2 = result(rec=record('T002'))
        out = node('07_batch_summary', items=items, results=[json.dumps(r2), json.dumps(r1)])
        s = json.loads(out['summary_json'])
        self.assertEqual([r['ticket_id'] for r in s['results']], ['T001','T002'])
        self.assertEqual(s['total'], 2); self.assertEqual(s['review_count'], 0)

    def test_missing_result_is_review_record_not_lost(self):
        out = node('07_batch_summary', items=self.items(), results=[json.dumps(result())])
        s = json.loads(out['summary_json'])
        self.assertEqual(s['total'], 2); self.assertEqual(s['review_count'], 1)
        self.assertEqual(s['review_records'][0]['ticket_id'], 'T002')

    def test_duplicate_result_is_not_double_counted(self):
        r = json.dumps(result())
        s = json.loads(node('07_batch_summary', items=self.items(), results=[r,r])['summary_json'])
        self.assertEqual(s['total'], 2); self.assertEqual(s['review_count'], 2)

    def test_untrusted_result_cannot_count_as_pass(self):
        r = result(); r['checks'] = []
        s = json.loads(node('07_batch_summary', items=self.items(), results=[json.dumps(r)])['summary_json'])
        self.assertEqual(s['pass_count'], 0); self.assertEqual(s['review_count'], 2)

    def test_missing_nested_contract_routes_review(self):
        r = result()
        for c in r['checks']:
            for key in ('evidence', 'rule_quote', 'reason'):
                c.pop(key)
        for key in ('category_evidence','category_confidence','schema_version','semantic_review'):
            r.pop(key)
        s = json.loads(node('07_batch_summary', items=self.items(), results=[json.dumps(r)])['summary_json'])
        self.assertEqual(s['pass_count'], 0); self.assertEqual(s['review_count'], 2)

    def test_malformed_subflow_types_do_not_abort_batch(self):
        for field,value in [('ticket_id',[]),('category',[]),('category_confidence',float('nan'))]:
            with self.subTest(field=field):
                r = result(); r[field] = value
                s = json.loads(node('07_batch_summary', items=self.items(), results=[json.dumps(r)])['summary_json'])
                self.assertEqual(s['pass_count'], 0); self.assertEqual(s['review_count'], 2)

    def test_invalid_rule_id_does_not_crash_sort(self):
        r = result(); r['checks'][0]['rule_id'] = {}
        s = json.loads(node('07_batch_summary', items=self.items(), results=[json.dumps(r)])['summary_json'])
        self.assertEqual(s['review_count'], 2)

    def test_non_object_fourth_check_routes_review(self):
        r = result(); r['checks'].append('bad')
        s = json.loads(node('07_batch_summary', items=self.items(), results=[json.dumps(r)])['summary_json'])
        self.assertEqual(s['review_count'], 2)

    def test_route_must_match_category(self):
        r = result(); r['route'] = 'bad route'; r['suggested_route'] = 'bad route'
        s = json.loads(node('07_batch_summary', items=self.items(), results=[json.dumps(r)])['summary_json'])
        self.assertEqual(s['pass_count'], 0); self.assertEqual(s['review_count'], 2)

    def test_batch_evidence_must_still_be_original_agent_words(self):
        r = result(); r['checks'][0]['evidence'][0]['quote'] = '伪造'
        s = json.loads(node('07_batch_summary', items=self.items(), results=[json.dumps(r)])['summary_json'])
        self.assertEqual(s['review_count'], 2)

if __name__ == '__main__':
    unittest.main(verbosity=2)
