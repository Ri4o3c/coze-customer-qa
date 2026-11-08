"""比较实际最终输出和人工预期；不把标签匹配当作语义完整验收。"""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def score(actual, expected):
    if isinstance(actual,dict) and isinstance(actual.get('results'),list):
        actual=actual['results']
    if not isinstance(actual,list):
        raise ValueError('实际结果必须是对象数组，或含results数组的批量摘要。')
    by_id, duplicates, invalid = {}, set(), 0
    for row in actual:
        if not isinstance(row,dict) or not isinstance(row.get('ticket_id'),str):
            invalid += 1
            continue
        tid=row['ticket_id']
        if tid in by_id:
            duplicates.add(tid)
        by_id[tid]=row
    rows=[]
    for want in expected:
        tid=want['ticket_id']; got=by_id.get(tid)
        differences=[]
        if got is None or tid in duplicates:
            differences=['missing_result' if got is None else 'duplicate_result']
        else:
            if want['category'] is not None and (got.get('category')!=want['category'] or got.get('category_valid') is not True):
                differences.append('category')
            if got.get('needs_review') is not want['needs_review']:
                differences.append('needs_review')
            checks=got.get('checks',[])
            if not isinstance(checks,list):
                checks=[]
            ids=[c.get('rule_id') for c in checks if isinstance(c,dict)]
            if sorted(x for x in ids if isinstance(x,str))!=['R01','R02','R03']:
                differences.append('check_contract')
            indexed={c.get('rule_id'):c.get('status') for c in checks if isinstance(c,dict) and isinstance(c.get('rule_id'),str)}
            for rid,status in want['checks'].items():
                if indexed.get(rid)!=status:
                    differences.append(rid)
        rows.append({'ticket_id':tid,'matched':not differences,'differences':differences})
    expected_ids={r['ticket_id'] for r in expected}
    return {'scope':'仅人工预期标签匹配；不验证模型推理或证据语义',
            'expected_total':len(expected),'received_rows':len(actual),
            'matched_cases':sum(r['matched'] for r in rows),
            'missing_ids':[r['ticket_id'] for r in expected if r['ticket_id'] not in by_id],
            'duplicate_ids':sorted(duplicates),'unexpected_ids':sorted(set(by_id)-expected_ids),
            'invalid_rows':invalid,'cases':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actual_file',type=Path)
    args=parser.parse_args()
    actual=json.loads(args.actual_file.read_text(encoding='utf-8-sig'))
    expected=json.loads((ROOT/'data/eval_expected.json').read_text(encoding='utf-8'))
    print(json.dumps(score(actual,expected),ensure_ascii=False,indent=2))
