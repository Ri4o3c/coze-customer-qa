import json


async def main(args: Args) -> Output:
    raw = args.params.get('records_json', '')
    errors = []
    records = []
    if not isinstance(raw, str) or len(raw) > 2000000:
        errors.append('invalid_batch_input_type_or_size')
    else:
        try:
            records = json.loads(raw)
        except ValueError:
            errors.append('invalid_batch_json')
    if not isinstance(records, list) or not 1 <= len(records) <= 50:
        errors.append('batch_requires_1_to_50_records')
        records = []
    items, ids = [], set()
    for index, rec in enumerate(records):
        tid = rec.get('ticket_id') if isinstance(rec, dict) else None
        if not isinstance(tid, str) or not tid.strip() or len(tid) > 100:
            errors.append('invalid_ticket_id_at_row_' + str(index + 1))
            continue
        if tid in ids:
            errors.append('duplicate_ticket_id_' + tid)
        ids.add(tid)
        items.append({'source_index': index, 'ticket_id': tid,
                      'record_json': json.dumps(rec, ensure_ascii=False)})
    if errors:
        items = []
    summary = {'batch_status': 'rejected' if errors else 'ready', 'errors': errors,
               'total': len(records), 'processed_count': 0}
    return {'valid': not errors, 'items': items,
            'summary_json': json.dumps(summary, ensure_ascii=False),
            'report': ('批量输入未通过校验，未调用模型：' + '；'.join(errors)) if errors else '批量输入校验通过。'}
