import json
import math


async def main(args: Args) -> Output:
    errors = []
    prepared, rules, analysis = {}, [], {}
    for key in ('prepared_json', 'rules_json', 'analysis_json'):
        raw = args.params.get(key, '')
        try:
            obj = json.loads(raw) if isinstance(raw, str) else None
        except (ValueError, TypeError):
            obj = None
        if key == 'prepared_json':
            prepared = obj if isinstance(obj, dict) else {}
            if not prepared.get('valid'):
                errors.append('invalid_input')
        elif key == 'rules_json':
            rules = obj if isinstance(obj, list) else []
        else:
            analysis = obj if isinstance(obj, dict) else {}
            if not isinstance(obj, dict):
                errors.append('invalid_model_json')
    messages = prepared.get('messages', [])
    rule_map = {}
    for r in rules:
        if (isinstance(r, dict) and r.get('rule_id') in ('R01', 'R02', 'R03')
                and r.get('version') == '1.0' and isinstance(r.get('policy'), str)
                and r['policy'].strip() and r['rule_id'] not in rule_map):
            rule_map[r['rule_id']] = r
        else:
            errors.append('invalid_or_duplicate_retrieved_rule')
    if set(rule_map) != {'R01', 'R02', 'R03'}:
        errors.append('incomplete_rule_coverage')
    routes = {'物流配送': '物流客服', '退款退货': '售后客服', '商品质量': '商品售后',
              '订单与支付': '订单客服', '其他问题': '综合客服'}
    category = analysis.get('category')
    category_valid = isinstance(category, str) and category in routes
    confidence = analysis.get('category_confidence')
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        confidence = 0
        category_valid = False
        errors.append('invalid_category_confidence')
    if not category_valid:
        category = '其他问题'
        errors.append('invalid_category')
    category_evidence = analysis.get('category_evidence')
    if not isinstance(category_evidence, list) or not category_evidence:
        category_valid = False
        category_evidence = []
        errors.append('missing_category_evidence')
    for evidence in category_evidence:
        idx = evidence.get('message_index') if isinstance(evidence, dict) else None
        quote = evidence.get('quote') if isinstance(evidence, dict) else None
        if (type(idx) is not int or not 0 <= idx < len(messages)
                or messages[idx].get('role') != 'customer' or not isinstance(quote, str)
                or not quote.strip() or quote not in messages[idx].get('text', '')):
            category_valid = False
            errors.append('invalid_category_evidence')
    if confidence < 0.75:
        errors.append('low_category_confidence')
    summary = analysis.get('summary')
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
        summary = '信息不足或分析结果异常，待人工核查。'
        errors.append('invalid_summary')
    review_flag = analysis.get('needs_review')
    reasons = analysis.get('review_reasons')
    if type(review_flag) is not bool or not isinstance(reasons, list) or any(not isinstance(v, str) for v in reasons):
        errors.append('invalid_model_review_fields')
        reasons = []
    if review_flag is True:
        errors.append('model_requested_review')
    if reasons:
        errors.extend('model_reason: ' + s[:200] for s in reasons if s.strip())
    incoming = analysis.get('checks')
    if not isinstance(incoming, list) or len(incoming) != 3:
        incoming = []
        errors.append('checks_must_have_three_rules')
    by_id = {}
    for check in incoming:
        rid = check.get('rule_id') if isinstance(check, dict) else None
        if rid not in ('R01', 'R02', 'R03') or rid in by_id:
            errors.append('invalid_or_duplicate_check')
        else:
            by_id[rid] = check
    checks = []
    for rid in ('R01', 'R02', 'R03'):
        check = by_id.get(rid, {})
        status = check.get('status')
        evidence = check.get('evidence')
        rule_quote = check.get('rule_quote')
        reason = check.get('reason')
        local_errors = []
        if status not in ('pass', 'fail', 'unknown'):
            local_errors.append('invalid_status')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            local_errors.append('invalid_reason')
        if (not isinstance(rule_quote, str) or not rule_quote.strip()
                or rid not in rule_map or rule_quote != rule_map[rid]['policy']):
            local_errors.append('invalid_rule_quote')
        if not isinstance(evidence, list) or (status in ('pass', 'fail') and not evidence):
            local_errors.append('missing_evidence')
            evidence = []
        for e in evidence:
            idx = e.get('message_index') if isinstance(e, dict) else None
            quote = e.get('quote') if isinstance(e, dict) else None
            if (type(idx) is not int or not 0 <= idx < len(messages)
                    or messages[idx].get('role') != 'agent' or not isinstance(quote, str)
                    or not quote.strip() or quote not in messages[idx].get('text', '')):
                local_errors.append('invalid_agent_evidence')
        if local_errors:
            errors.extend(rid + ':' + e for e in local_errors)
        checks.append({'rule_id': rid, 'status': status if not local_errors else 'unknown',
                       'rule_quote': rule_quote if not local_errors else '',
                       'reason': reason if not local_errors else '字段、规则或原文证据校验失败。',
                       'evidence': evidence if not local_errors else []})
    # Any structural/grounding failure invalidates this model judgement as a whole.
    fatal = any(e not in ('low_category_confidence', 'model_requested_review')
                and not e.startswith('model_reason: ') for e in errors)
    if fatal:
        checks = [{'rule_id': rid, 'status': 'unknown', 'rule_quote': '',
                   'reason': '本次输出校验未通过，待人工复核。', 'evidence': []}
                  for rid in ('R01', 'R02', 'R03')]
    if any(c['status'] == 'unknown' for c in checks):
        errors.append('undetermined_rule')
    needs_review = bool(errors)
    qc_status = ('violation' if any(c['status'] == 'fail' for c in checks)
                 else 'pass' if all(c['status'] == 'pass' for c in checks) else 'undetermined')
    result = {'schema_version': '1.0', 'ticket_id': prepared.get('ticket_id', ''),
              'category': category, 'category_valid': category_valid and not fatal,
              'category_confidence': confidence, 'category_evidence': category_evidence if not fatal else [],
              'summary': summary, 'checks': checks, 'qc_status': qc_status,
              'needs_review': needs_review, 'review_reasons': list(dict.fromkeys(errors)),
              'route': '人工复核队列' if needs_review else routes[category],
              'suggested_route': routes[category] if category_valid and not fatal else '综合客服',
              'action': 'suggest_only', 'validation': 'code_checked',
              'semantic_review': 'model_judgement_not_human_verified'}
    return {'result_json': json.dumps(result, ensure_ascii=False, allow_nan=False),
            'needs_review': needs_review}
