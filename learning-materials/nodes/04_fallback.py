import json


async def main(args: Args) -> Output:
    try:
        prepared = json.loads(args.params.get('prepared_json', '{}'))
    except (TypeError, ValueError):
        prepared = {}
    if not isinstance(prepared, dict):
        prepared = {}
    allowed = ('invalid_input', 'retrieval_error', 'rule_coverage_error', 'model_error', 'validator_error')
    code = args.params.get('failure_code')
    code = code if code in allowed else 'validator_error'
    reasons = [code]
    if code == 'invalid_input' and isinstance(prepared.get('errors'), list):
        reasons.extend(str(s)[:100] for s in prepared['errors'])
    result = {'schema_version': '1.0', 'ticket_id': prepared.get('ticket_id', ''),
              'category': '其他问题', 'category_valid': False, 'category_confidence': 0,
              'category_evidence': [], 'summary': '未取得可验证的自动分析，待人工复核。',
              'checks': [{'rule_id': rid, 'status': 'unknown', 'rule_quote': '',
                          'reason': '未执行或未成功完成质检。', 'evidence': []}
                         for rid in ('R01', 'R02', 'R03')],
              'qc_status': 'undetermined', 'needs_review': True, 'review_reasons': reasons,
              'route': '人工复核队列', 'suggested_route': '综合客服', 'action': 'suggest_only',
              'validation': 'fallback', 'semantic_review': 'not_evaluated'}
    return {'result_json': json.dumps(result, ensure_ascii=False), 'needs_review': True}
