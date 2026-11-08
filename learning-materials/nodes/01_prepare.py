import json


async def main(args: Args) -> Output:
    raw = args.params.get('record_json', '')
    errors = []
    rec = {}
    if not isinstance(raw, str) or len(raw) > 150000:
        errors.append('invalid_input_type_or_size')
    else:
        try:
            rec = json.loads(raw)
        except (ValueError, TypeError):
            errors.append('invalid_json')
    if not isinstance(rec, dict):
        errors.append('record_must_be_object')
        rec = {}
    ticket_id = rec.get('ticket_id')
    if not isinstance(ticket_id, str) or not ticket_id.strip() or len(ticket_id) > 100:
        errors.append('invalid_ticket_id')
        ticket_id = ''
    messages = rec.get('messages')
    safe_messages = []
    if not isinstance(messages, list) or not 2 <= len(messages) <= 100:
        errors.append('messages_need_2_to_100_turns')
    else:
        total = 0
        for index, item in enumerate(messages):
            if not isinstance(item, dict):
                errors.append('invalid_message_' + str(index))
                continue
            role, text = item.get('role'), item.get('text')
            if role not in ('customer', 'agent') or not isinstance(text, str) or not text.strip():
                errors.append('invalid_role_or_text_' + str(index))
                continue
            total += len(text)
            safe_messages.append({'role': role, 'text': text})
        if total > 20000:
            errors.append('conversation_exceeds_20000_characters')
        if not {'customer', 'agent'}.issubset({m['role'] for m in safe_messages}):
            errors.append('missing_customer_or_agent')
    if errors:
        safe_messages = []
    rec = {'ticket_id': ticket_id, 'messages': safe_messages,
           'valid': not errors, 'errors': list(dict.fromkeys(errors))}
    return {'valid': not errors, 'prepared_json': json.dumps(rec, ensure_ascii=False),
            'ticket_id': ticket_id,
            'query': '电商客服质检规则 R01 文明服务 R02 密码支付验证码 R03 退款审核到账承诺 版本1.0'}
