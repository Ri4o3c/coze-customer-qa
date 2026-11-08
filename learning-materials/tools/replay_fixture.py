"""手工候选回放：不调用模型或Coze，不属于业务准确率评测。"""
import asyncio
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

def call(name, **params):
    ns = runpy.run_path(str(ROOT/'nodes'/(name+'.py')), init_globals={'Args':object,'Output':dict})
    return asyncio.run(ns['main'](SimpleNamespace(params=params)))

def replay():
    record = json.loads((ROOT/'data/single_normal.json').read_text(encoding='utf-8'))
    prepared = call('01_prepare',record_json=json.dumps(record,ensure_ascii=False))
    hits=[{'content':p.read_text(encoding='utf-8')} for p in sorted((ROOT/'knowledge').glob('*.txt'))]
    rules=call('02_rules',hits=hits)
    policies=json.loads(rules['rules_json'])
    analysis={'category':'物流配送','category_confidence':0.96,
              'category_evidence':[{'message_index':0,'quote':'我的包裹三天没更新了。'}],
              'summary':'客户咨询物流停滞，客服表示将联系物流核实。',
              'checks':[{'rule_id':r['rule_id'],'status':'pass','rule_quote':r['policy'],
                         'reason':'当前提供的客服发言未见此项违规。',
                         'evidence':[{'message_index':1,'quote':'您好，我帮您联系物流核实。'}]}
                        for r in policies], 'needs_review':False,'review_reasons':[]}
    validated=call('03_validate',prepared_json=prepared['prepared_json'],
                   rules_json=rules['rules_json'],analysis_json=json.dumps(analysis,ensure_ascii=False))
    return call('05_render',result_json=validated['result_json'])

if __name__=='__main__':
    out=replay()
    print('【手工候选回放，无模型调用，无Coze运行】')
    print(out['report'])
