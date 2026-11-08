# -*- coding: utf-8 -*-
"""客服质检与工单分流助手 —— 公开演示网页（单文件、自包含，中文、手机可用）。
只负责前端静态页，不包含任何鉴权/密钥；结果由服务端 API 返回后经 textContent 安全渲染。
"""

DEMO_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>客服质检与工单分流助手</title>
<style>
  :root{
    --bg:#f4f6fb; --card:#ffffff; --line:#e3e8f0; --text:#1f2733; --muted:#6b7686;
    --brand:#2f6fed; --brand-soft:#eaf1ff; --ok:#16a34a; --warn:#d97706; --bad:#dc2626; --gray:#64748b;
    --radius:12px;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.55}
  .wrap{max-width:880px;margin:0 auto;padding:16px}
  header{background:linear-gradient(120deg,#2f6fed,#4f8df5);color:#fff;border-radius:var(--radius);padding:18px 20px;margin-bottom:18px}
  header h1{margin:0 0 6px;font-size:20px}
  header p{margin:0;font-size:13px;opacity:.94}
  .tabs{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
  .tab{flex:1;min-width:150px;border:1px solid var(--line);background:var(--card);color:var(--muted);padding:11px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;text-align:center}
  .tab.active{background:var(--brand);color:#fff;border-color:var(--brand)}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:16px;margin-bottom:16px}
  .card h2{margin:0 0 12px;font-size:16px}
  .hint{font-size:12px;color:var(--muted);margin-top:6px}
  label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px}
  input[type=text],textarea{width:100%;border:1px solid var(--line);border-radius:8px;padding:9px 10px;font-size:14px;font-family:inherit;background:#fff}
  textarea{resize:vertical;min-height:80px}
  .row{display:flex;gap:8px;align-items:flex-start;margin-bottom:8px}
  .row select{flex:0 0 92px;padding:8px;border-radius:8px;border:1px solid var(--line);background:#fff;font-size:13px}
  .row textarea{flex:1}
  .del{flex:0 0 auto;border:none;background:#fdecec;color:var(--bad);border-radius:8px;padding:8px 10px;cursor:pointer}
  .btn{border:none;border-radius:9px;padding:10px 14px;font-size:14px;font-weight:600;cursor:pointer;background:var(--brand);color:#fff}
  .btn:disabled{opacity:.55;cursor:not-allowed}
  .btn.ghost{background:var(--brand-soft);color:var(--brand)}
  .btn.gray{background:#eee;color:#555}
  .chip{display:inline-block;background:var(--brand-soft);color:var(--brand);border-radius:20px;padding:3px 10px;font-size:12px;margin:0 6px 6px 0;cursor:pointer}
  .badge{display:inline-block;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;vertical-align:middle}
  .b-ok{background:#e7f7ee;color:var(--ok)} .b-viol{background:#fdecec;color:var(--bad)} .b-undet{background:#fef3e2;color:var(--warn)} .b-review{background:#eef1f6;color:var(--gray)}
  .kv{display:flex;flex-wrap:wrap;gap:10px;margin:6px 0}
  .kv .it{flex:1;min-width:150px;background:#f8fafc;border:1px solid var(--line);border-radius:9px;padding:9px}
  .kv .it b{display:block;font-size:12px;color:var(--muted);font-weight:600}
  .kv .it span{font-size:14px}
  .rule{border:1px solid var(--line);border-radius:10px;padding:11px;margin-bottom:10px}
  .rule .head{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}
  .rule .pid{font-weight:700}
  .rule .policy{font-size:12px;color:var(--muted);margin:6px 0}
  .rule .reason{font-size:13px;margin:6px 0}
  .evi{font-size:12px;color:var(--muted);background:#f8fafc;border-radius:7px;padding:6px 8px;margin-top:4px}
  pre.raw{white-space:pre-wrap;word-break:break-word;background:#0f172a;color:#e2e8f0;padding:12px;border-radius:9px;font-size:12px;max-height:360px;overflow:auto}
  .stat{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
  .stat .box{flex:1;min-width:96px;background:#f8fafc;border:1px solid var(--line);border-radius:9px;padding:8px;text-align:center}
  .stat .box b{display:block;font-size:20px}
  .tablewrap{overflow-x:auto}
  table{border-collapse:collapse;width:100%;font-size:12px;min-width:560px}
  th,td{border:1px solid var(--line);padding:6px 7px;text-align:left;vertical-align:top}
  th{background:#f1f5fb}
  .err{background:#fdecec;color:var(--bad);border:1px solid #f3b6b6;border-radius:8px;padding:10px;font-size:13px;margin:10px 0;display:none}
  .loading{color:var(--brand);font-size:13px;margin:10px 0;display:none}
  .hidden{display:none}
  .notice{font-size:12px;color:var(--muted);border-top:1px solid var(--line);margin-top:14px;padding-top:10px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>客服质检与工单分流助手</h1>
    <p>虚构电商售后客服对话复核：自动做问题分类与路由建议，并按 R01/R02/R03 规则做客服质检（含原文证据），标记是否需要人工复核。仅做质检与分流建议，不实际建单/退款/发消息。</p>
  </header>

  <div class="tabs">
    <div class="tab active" id="tab_single" onclick="showTab('single')">单条分析</div>
    <div class="tab" id="tab_batch" onclick="showTab('batch')">批量分析</div>
  </div>

  <div id="panel_single">
    <div class="card">
      <h2>单条对话质检</h2>
      <div style="margin-bottom:6px">
        <span class="chip" onclick="loadSingle('normal')">示例·正常物流</span>
        <span class="chip" onclick="loadSingle('vcode')">示例·索取验证码</span>
        <span class="chip" onclick="loadSingle('pending')">示例·仅客户待复核</span>
      </div>
      <label>记录 ID</label>
      <input type="text" id="ticket_id" value="DEMO-001" placeholder="例如 DEMO-001 / TK-123">
      <label>对话内容（至少 2 条且必须同时包含 customer 与 agent）</label>
      <div id="msg_rows"></div>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="btn ghost" onclick="addMsg()">+ 添加消息</button>
        <button class="btn" id="btn_single" onclick="runSingle()">开始分析</button>
      </div>
      <div class="hint">共 2–100 条消息、全文合计不超过 20000 字符，超限不截断、直接转人工复核。</div>
      <div class="err" id="err_single"></div>
      <div class="loading" id="loading_single">正在调用模型与规则知识库分析，请稍候…</div>
    </div>
    <div class="card hidden" id="res_single_card">
      <h2>分析结果</h2>
      <div id="res_single"></div>
    </div>
  </div>

  <div id="panel_batch" class="hidden">
    <div class="card">
      <h2>批量质检（1–50 条）</h2>
      <div style="margin-bottom:6px"><span class="chip" onclick="loadBatchExample()">载入内置 6 条示例</span></div>
      <label>粘贴 JSON（对象数组，每项含 ticket_id 与 messages）或上传文件</label>
      <textarea id="batch_json" placeholder='[{"ticket_id":"DEMO-001","messages":[{"role":"customer","text":"..."},...]}, ...]'></textarea>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
        <label class="btn gray" style="margin:0;font-weight:600;display:inline-block">上传 JSON 文件</label>
        <input type="file" id="batch_file" accept=".json,application/json" style="display:none">
        <button class="btn" id="btn_batch" onclick="runBatch()">开始批量分析</button>
      </div>
      <div class="hint">ID 必须非空且唯一，缺 ID 或重复 ID 整批拒绝；ID 合法但对话异常的行会保留并走人工复核。</div>
      <div class="err" id="err_batch"></div>
      <div class="loading" id="loading_batch">正在逐条调用模型与规则知识库（并发处理），请稍候…</div>
    </div>
    <div class="card hidden" id="res_batch_card">
      <h2>批量汇总</h2>
      <div id="res_batch"></div>
    </div>
  </div>

  <p class="notice">本页面仅用于产品能力演示，所有输入仅用于本次分析、不会被保存；模型返回文本已按纯文本渲染，不做脚本执行。</p>
</div>

<script>
var SINGLE_EXAMPLES = {
  normal:{ticket_id:'DEMO-001',messages:[{role:'customer',text:'我的包裹三天没更新了。'},{role:'agent',text:'您好，我帮您联系物流核实。'}]},
  vcode:{ticket_id:'DEMO-002',messages:[{role:'customer',text:'我想申请退货退款。'},{role:'agent',text:'把支付验证码发给我，我帮你办退款。'}]},
  pending:{ticket_id:'DEMO-003',messages:[{role:'customer',text:'我想退货，但是还没联系到客服。'}]}
};
var BATCH_EXAMPLES=[
  {ticket_id:'DEMO-001',messages:[{role:'customer',text:'我的包裹三天没更新了。'},{role:'agent',text:'您好，我帮您联系物流核实。'}]},
  {ticket_id:'DEMO-002',messages:[{role:'customer',text:'我想申请退货退款。'},{role:'agent',text:'把支付验证码发给我，我帮你办退款。'}]},
  {ticket_id:'DEMO-003',messages:[{role:'customer',text:'我想退货，但是还没联系到客服。'}]},
  {ticket_id:'DEMO-004',messages:[{role:'customer',text:'收到的杯子裂了。'},{role:'agent',text:'这都看不懂？自己处理。'}]},
  {ticket_id:'DEMO-005',messages:[{role:'customer',text:'我的订单重复扣款了。'},{role:'agent',text:'请提供订单号核实，不要把支付验证码发给任何人。'}]},
  {ticket_id:'DEMO-006',messages:[{role:'customer',text:'你们客服几点上班？'},{role:'agent',text:'您好，每天9点到18点提供服务。'}]}
];

function showTab(name){
  document.getElementById('tab_single').classList.toggle('active',name==='single');
  document.getElementById('tab_batch').classList.toggle('active',name==='batch');
  document.getElementById('panel_single').classList.toggle('hidden',name!=='single');
  document.getElementById('panel_batch').classList.toggle('hidden',name!=='batch');
}
function el(id){return document.getElementById(id);}
function setErr(id,msg){var e=el(id); if(msg){e.textContent=msg;e.style.display='block';}else{e.textContent='';e.style.display='none';} }
function setLoading(id,on){el(id).style.display=on?'block':'none';}
function esc(t){return String(t==null?'':t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}

/* ---------- 单条编辑器 ---------- */
function renderMsgRows(rows){
  var box=el('msg_rows'); box.innerHTML='';
  rows.forEach(function(m,i){
    var row=document.createElement('div'); row.className='row';
    var sel=document.createElement('select');
    ['customer','agent'].forEach(function(r){var o=document.createElement('option');o.value=r;o.textContent=(r==='customer'?'客户':'客服');if(r===m.role)o.selected=true;sel.appendChild(o);});
    var ta=document.createElement('textarea'); ta.placeholder='输入对话内容'; ta.value=m.text||'';
    var del=document.createElement('button'); del.className='del'; del.textContent='删除'; del.onclick=function(){box.removeChild(row);};
    row.appendChild(sel);row.appendChild(ta);row.appendChild(del);
    box.appendChild(row);
  });
  if(rows.length===0) addMsg();
}
function addMsg(){var box=el('msg_rows');var row=document.createElement('div');row.className='row';
  var sel=document.createElement('select');['customer','agent'].forEach(function(r){var o=document.createElement('option');o.value=r;o.textContent=(r==='customer'?'客户':'客服');sel.appendChild(o);});
  var ta=document.createElement('textarea');ta.placeholder='输入对话内容';
  var del=document.createElement('button');del.className='del';del.textContent='删除';del.onclick=function(){box.removeChild(row);};
  row.appendChild(sel);row.appendChild(ta);row.appendChild(del);box.appendChild(row);
}
function readSingle(){
  var rows=el('msg_rows').querySelectorAll('.row');
  var messages=[];
  rows.forEach(function(r){
    var role=r.querySelector('select').value; var text=r.querySelector('textarea').value;
    if(text && text.trim()) messages.push({role:role,text:text.trim()});
  });
  return {ticket_id:el('ticket_id').value.trim()||('DEMO-'+Math.floor(Math.random()*9000+1000)), messages:messages};
}
function loadSingle(key){
  var ex=SINGLE_EXAMPLES[key]; el('ticket_id').value=ex.ticket_id; renderMsgRows(ex.messages);
  setErr('err_single',null); el('res_single_card').classList.add('hidden');
}

async function runSingle(){
  var data=readSingle();
  setErr('err_single',null); el('res_single_card').classList.add('hidden');
  if(!data.messages.length){setErr('err_single','请至少输入一条对话内容。');return;}
  var btn=el('btn_single'); btn.disabled=true; setLoading('loading_single',true);
  try{
    var resp=await fetch('/api/demo/single',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    var out=await resp.json();
    if(!resp.ok){setErr('err_single',out.detail||'分析请求失败，请稍后重试。');return;}
    renderSingle(out); el('res_single_card').classList.remove('hidden');
  }catch(e){setErr('err_single','网络异常或服务不可用，请稍后重试。');}
  finally{btn.disabled=false;setLoading('loading_single',false);}
}

function renderSingle(out){
  var rj=out.result_json||{}; var box=el('res_single'); box.innerHTML='';
  var head=document.createElement('div');
  var qc=rj.qc_status||'undetermined'; var nr=rj.needs_review;
  var qcClass=qc==='pass'?'b-ok':(qc==='violation'?'b-viol':'b-undet');
  head.innerHTML='<h3 style="margin:0 0 10px;font-size:15px">'+esc(rj.ticket_id||'')+'</h3>'+
    '<div class="badge '+qcClass+'">'+esc(qc)+'</div> '+
    '<div class="badge '+(nr?'b-review':'b-ok')+'">'+(nr?'需人工复核':'无需复核')+'</div>';
  box.appendChild(head);

  var kv=document.createElement('div'); kv.className='kv';
  kv.innerHTML='<div class="it"><b>问题分类</b><span>'+esc(rj.category||'（未分类）')+'</span></div>'+
    '<div class="it"><b>分流路由</b><span>'+esc(rj.route||'—')+'</span></div>'+
    '<div class="it"><b>建议去向</b><span>'+esc(rj.suggested_route||'—')+'</span></div>'+
    '<div class="it"><b>置信度</b><span>'+esc(rj.category_confidence)+'</span></div>';
  box.appendChild(kv);

  if(rj.category_evidence && rj.category_evidence.length){
    var ce=document.createElement('div'); ce.className='evi'; ce.innerHTML='<b>分类依据（客户原话）：</b>';
    rj.category_evidence.forEach(function(x){ce.appendChild(document.createElement('br'));ce.appendChild(document.createTextNode('消息['+x.message_index+']：'+x.quote));});
    box.appendChild(ce);
  }

  if(rj.review_reasons&&rj.review_reasons.length){var rr=document.createElement('div');rr.className='evi';rr.innerHTML='<b>复核原因：</b>';rj.review_reasons.forEach(function(r){rr.appendChild(document.createElement('br'));rr.appendChild(document.createTextNode('· '+r));});box.appendChild(rr);}

  var rules=['R01','R02','R03'];
  rules.forEach(function(rid){
    var c=rj.checks&&rj.checks[rid]; if(!c) return;
    var d=document.createElement('div'); d.className='rule';
    var st=c.status||'unknown'; var cls=st==='pass'?'b-ok':(st==='fail'?'b-viol':'b-undet');
    var h=document.createElement('div'); h.className='head';
    h.innerHTML='<span class="pid">'+esc(rid)+'</span><span class="badge '+cls+'">'+esc(st)+'</span>';
    d.appendChild(h);
    var p=document.createElement('div'); p.className='policy'; p.textContent='规则：'+c.rule_quote; d.appendChild(p);
    var re=document.createElement('div'); re.className='reason'; re.textContent='判定依据：'+c.reason; d.appendChild(re);
    (c.evidence||[]).forEach(function(x){var ev=document.createElement('div');ev.className='evi';ev.textContent='证据[消息'+x.message_index+']：'+x.quote;d.appendChild(ev);});
    box.appendChild(d);
  });

  var det=document.createElement('div');
  var btn=document.createElement('button');btn.className='btn ghost';btn.textContent='展开原始报告';btn.onclick=function(){det.classList.toggle('hidden');};
  box.appendChild(btn);
  var pre=document.createElement('pre');pre.className='raw hidden';pre.textContent=out.report||'';det.appendChild(pre);
  // det itself is a container holding the <pre> toggle
  det.remove();
  var pre2=document.createElement('pre');pre2.className='raw hidden';pre2.textContent=out.report||'';box.appendChild(pre2);
  btn.onclick=function(){pre2.classList.toggle('hidden');};
}

/* ---------- 批量 ---------- */
function loadBatchExample(){el('batch_json').value=JSON.stringify(BATCH_EXAMPLES,null,2);setErr('err_batch',null);el('res_batch_card').classList.add('hidden');}
document.getElementById('batch_file').addEventListener('change',function(ev){
  var f=ev.target.files[0]; if(!f) return;
  var rd=new FileReader(); rd.onload=function(){el('batch_json').value=String(rd.result||'');}; rd.readAsText(f,'utf-8');
});
async function runBatch(){
  var raw=el('batch_json').value.trim();
  setErr('err_batch',null); el('res_batch_card').classList.add('hidden');
  if(!raw){setErr('err_batch','请先粘贴 JSON 或载入内置示例。');return;}
  var records;
  try{records=JSON.parse(raw);}catch(e){setErr('err_batch','JSON 格式无效：'+e.message);return;}
  if(!Array.isArray(records)||records.length<1||records.length>50){setErr('err_batch','必须是包含 1–50 条记录的数组。');return;}
  var btn=el('btn_batch'); btn.disabled=true; setLoading('loading_batch',true);
  try{
    var resp=await fetch('/api/demo/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({records:records})});
    var out=await resp.json();
    if(!resp.ok){setErr('err_batch',(typeof out.detail==='string'?out.detail:JSON.stringify(out.detail||'批量分析失败'))||'批量分析失败，请稍后重试。');return;}
    renderBatch(out); el('res_batch_card').classList.remove('hidden');
  }catch(e){setErr('err_batch','网络异常或服务不可用，请稍后重试。');}
  finally{btn.disabled=false;setLoading('loading_batch',false);}
}
function renderBatch(out){
  var s=out.summary_json||{}; var box=el('res_batch'); box.innerHTML='';
  var st=document.createElement('div'); st.className='stat';
  st.innerHTML='<div class="box"><b>'+esc(s.total)+'</b>总条数</div>'+
    '<div class="box"><b style="color:var(--ok)">'+esc(s.pass_count)+'</b>pass</div>'+
    '<div class="box"><b style="color:var(--bad)">'+esc(s.violation_count)+'</b>违规</div>'+
    '<div class="box"><b style="color:var(--warn)">'+esc(s.undetermined_count)+'</b>未定</div>'+
    '<div class="box"><b>'+esc(s.review_count)+'</b>复核</div>';
  box.appendChild(st);
  var cc=document.createElement('div'); cc.className='evi'; cc.innerHTML='<b>分类统计：</b>'+esc(JSON.stringify(s.category_counts||{})); box.appendChild(cc);
  var rc=document.createElement('div'); rc.className='evi'; rc.innerHTML='<b>规则违规统计：</b>'+esc(JSON.stringify(s.rule_violation_counts||{})); box.appendChild(rc);

  var tw=document.createElement('div'); tw.className='tablewrap';
  var tbl=document.createElement('table'); tbl.innerHTML='<tr><th>ID</th><th>分类</th><th>状态</th><th>R01</th><th>R02</th><th>R03</th><th>复核</th></tr>';
  (s.results||[]).forEach(function(r){
    var detail=r.result_json||{};
    if(typeof detail==='string'){try{detail=JSON.parse(detail);}catch(e){detail={};}}
    var ch=r.checks||detail.checks||{};
    var tr=document.createElement('tr');
    tr.innerHTML='<td>'+esc(r.ticket_id)+'</td><td>'+esc(r.category||'—')+'</td><td>'+esc(r.qc_status)+'</td>'+
      '<td>'+esc((ch.R01&&ch.R01.status)||'unknown')+'</td>'+
      '<td>'+esc((ch.R02&&ch.R02.status)||'unknown')+'</td>'+
      '<td>'+esc((ch.R03&&ch.R03.status)||'unknown')+'</td>'+
      '<td>'+(r.needs_review?'是':'否')+'</td>';
    tbl.appendChild(tr);
  });
  tw.appendChild(tbl); box.appendChild(tw);

  var dl=document.createElement('button');dl.className='btn gray';dl.textContent='下载 JSON';
  dl.onclick=function(){var blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='batch_result.json';a.click();URL.revokeObjectURL(a.href);};
  box.appendChild(dl);
}

renderMsgRows(SINGLE_EXAMPLES.normal.messages);
</script>
</body>
</html>
"""
