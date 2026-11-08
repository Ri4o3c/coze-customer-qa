import json
import math


async def main(args: Args) -> Output:
    items = args.params.get('items', [])
    incoming = args.params.get('results', [])
    if not isinstance(items, list) or not isinstance(incoming, list):
        raise ValueError('items/results must be Array')
    expected_ids = {item['ticket_id'] for item in items}
    by_id, duplicates, batch_errors = {}, set(), []
    for raw in incoming:
        if isinstance(raw, dict) and 'result_json' in raw:
            raw = raw['result_json']
        try:
            rec = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            rec = None
        if (not isinstance(rec, dict) or not isinstance(rec.get('ticket_id'), str)
                or rec['ticket_id'] not in expected_ids):
            batch_errors.append('unmatched_or_invalid_subflow_result')
            continue
        tid = rec['ticket_id']
        if tid in by_id:
            duplicates.add(tid)
        by_id[tid] = rec
    results = []
    categories = {name: 0 for name in ('物流配送', '退款退货', '商品质量', '订单与支付', '其他问题', '未确认')}
    rule_violations = {rid: 0 for rid in ('R01', 'R02', 'R03')}
    pass_count = violation_count = undetermined_count = 0
    for item in items:
        tid = item['ticket_id']
        rec = by_id.get(tid)
        issue = 'missing_subflow_result' if rec is None else ''
        if tid in duplicates:
            issue = 'duplicate_subflow_result'
        if rec is not None and not issue:
            checks = rec.get('checks')
            check_ids = [c.get('rule_id') for c in checks if isinstance(c, dict)] if isinstance(checks, list) else []
            statuses = [c.get('status') for c in checks if isinstance(c, dict)] if isinstance(checks, list) else []
            valid_statuses = len(statuses) == 3 and all(s in ('pass','fail','unknown') for s in statuses)
            derived_qc = ('violation' if 'fail' in statuses else 'pass' if statuses == ['pass'] * 3 else 'undetermined')
            required_texts = ('summary', 'route', 'suggested_route')
            confidence = rec.get('category_confidence')
            category = rec.get('category')
            routes = {'物流配送': '物流客服', '退款退货': '售后客服', '商品质量': '商品售后',
                      '订单与支付': '订单客服', '其他问题': '综合客服'}
            if (not isinstance(checks,list) or len(checks) != 3 or not all(isinstance(c,dict) for c in checks)
                    or not all(isinstance(rid,str) for rid in check_ids)
                    or sorted(check_ids) != ['R01','R02','R03'] or not valid_statuses
                    or rec.get('qc_status') != derived_qc
                    or rec.get('schema_version') != '1.0'
                    or type(rec.get('needs_review')) is not bool
                    or type(rec.get('category_valid')) is not bool
                    or not isinstance(category,str) or category not in routes
                    or type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0 <= confidence <= 1
                    or not isinstance(rec.get('category_evidence'),list)
                    or not isinstance(rec.get('review_reasons'), list)
                    or not all(isinstance(v,str) for v in rec.get('review_reasons', []))
                    or rec.get('validation') not in ('code_checked','fallback')
                    or rec.get('action') != 'suggest_only'
                    or rec.get('semantic_review') not in ('model_judgement_not_human_verified','not_evaluated')
                    or not all(isinstance(rec.get(k),str) for k in required_texts)
                    or not rec.get('summary','').strip()
                    or ('unknown' in statuses and not rec.get('needs_review'))
                    or (rec.get('review_reasons') and not rec.get('needs_review'))
                    or (not rec.get('category_valid') and not rec.get('needs_review'))
                    or (confidence < 0.75 and not rec.get('needs_review'))
                    or (rec.get('needs_review') and rec.get('route') != '人工复核队列')
                    or (not rec.get('needs_review') and rec.get('route') != routes.get(category))
                    or rec.get('suggested_route') != (routes.get(category) if rec.get('category_valid') else '综合客服')):
                issue = 'invalid_subflow_result_contract'
            if not issue:
                try:
                    source = json.loads(item['record_json'])
                    messages = source.get('messages', []) if isinstance(source,dict) else []
                except (TypeError,ValueError):
                    messages = []
                if not isinstance(messages,list):
                    messages = []
                if rec['category_valid'] and not rec['category_evidence']:
                    issue = 'invalid_subflow_category_evidence'
                evidence_groups = [('customer', rec['category_evidence'])]
                for check in checks:
                    if (not isinstance(check.get('reason'),str) or not check['reason'].strip()
                            or not isinstance(check.get('rule_quote'),str)
                            or not isinstance(check.get('evidence'),list)
                            or (check['status'] in ('pass','fail') and
                                (not check['rule_quote'].strip() or not check['evidence']))):
                        issue = 'invalid_subflow_check_contract'
                        break
                    evidence_groups.append(('agent',check['evidence']))
                for role, evidence in evidence_groups:
                    for e in evidence:
                        idx = e.get('message_index') if isinstance(e,dict) else None
                        quote = e.get('quote') if isinstance(e,dict) else None
                        if (type(idx) is not int or not 0 <= idx < len(messages)
                                or not isinstance(messages[idx],dict) or messages[idx].get('role') != role
                                or not isinstance(messages[idx].get('text'),str)
                                or not isinstance(quote,str) or not quote.strip() or quote not in messages[idx]['text']):
                            issue = 'invalid_subflow_evidence'
        if issue:
            rec = {'schema_version': '1.0', 'ticket_id': tid, 'category': '其他问题',
                   'category_valid': False, 'category_confidence': 0, 'category_evidence': [],
                   'summary': '批处理未取得唯一、完整的单条分析结果。',
                   'checks': [{'rule_id': rid, 'status': 'unknown', 'rule_quote': '',
                               'reason': '批处理结果异常。', 'evidence': []} for rid in ('R01','R02','R03')],
                   'qc_status': 'undetermined', 'needs_review': True, 'review_reasons': [issue],
                   'route': '人工复核队列', 'suggested_route': '综合客服', 'action': 'suggest_only',
                   'validation': 'fallback', 'semantic_review': 'not_evaluated'}
        results.append(rec)
        categories[rec['category'] if rec['category_valid'] else '未确认'] += 1
        pass_count += rec['qc_status'] == 'pass'
        violation_count += rec['qc_status'] == 'violation'
        undetermined_count += rec['qc_status'] == 'undetermined'
        for c in rec['checks']:
            if c['status'] == 'fail':
                rule_violations[c['rule_id']] += 1
    reviews = [{'ticket_id': r['ticket_id'], 'reasons': r['review_reasons']}
               for r in results if r['needs_review']]
    summary = {'batch_status': 'completed_with_review' if reviews or batch_errors else 'completed',
               'total': len(items), 'returned_count': len(incoming),
               'pass_count': pass_count, 'violation_count': violation_count,
               'undetermined_count': undetermined_count, 'review_count': len(reviews),
               'category_counts': categories, 'rule_violation_counts': rule_violations,
               'review_records': reviews, 'batch_errors': batch_errors, 'results': results}
    lines = ['客服质检批量报告', '总记录：' + str(len(items)),
             '未见违规：' + str(pass_count), '发现违规：' + str(violation_count),
             '无法判断：' + str(undetermined_count), '待人工复核：' + str(len(reviews)),
             '注意：待复核是独立维度，不与前三项相加。',
             '问题分类：' + json.dumps(categories, ensure_ascii=False),
             '规则违规次数：' + json.dumps(rule_violations, ensure_ascii=False)]
    for r in reviews:
        lines.append('待复核 ' + r['ticket_id'] + '：' + '；'.join(r['reasons']))
    if batch_errors:
        lines.append('批次异常：' + '；'.join(batch_errors))
    return {'summary_json': json.dumps(summary, ensure_ascii=False), 'report': '\n'.join(lines)}
