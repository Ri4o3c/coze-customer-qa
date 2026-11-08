import json


async def main(args: Args) -> Output:
    # Only connect validator/fallback output here. Runtime JSON failures use its exception branch.
    result = json.loads(args.params['result_json'])
    labels = {'pass': '未见违规', 'fail': '发现违规', 'unknown': '无法判断',
              'violation': '发现违规', 'undetermined': '无法判断'}
    lines = ['客服对话质检报告', '记录：' + result['ticket_id'],
             '问题分类：' + (result['category'] if result['category_valid'] else '未确认'),
             '质检结论：' + labels[result['qc_status']],
             '是否待人工复核：' + ('是' if result['needs_review'] else '否'),
             '分流建议：' + result['route'], '摘要：' + result['summary']]
    for c in result['checks']:
        lines.append(c['rule_id'] + '：' + labels[c['status']] + '；' + c['reason'])
        if c['rule_quote']:
            lines.append('规则原文：' + c['rule_quote'])
        for e in c['evidence']:
            lines.append('客服原话 [message_index=' + str(e['message_index']) + ']：' + e['quote'])
    if result['review_reasons']:
        lines.append('复核原因：' + '；'.join(result['review_reasons']))
    lines.append('本报告只提供质检与分流建议；代码校验不等于人工确认语义正确。')
    return {'result_json': json.dumps(result, ensure_ascii=False), 'report': '\n'.join(lines),
            'needs_review': result['needs_review']}
