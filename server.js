import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const data = path.join(root, 'data');
fs.mkdirSync(data, { recursive: true });

const stateFile = path.join(data, 'canonical.json');
const chatFile = path.join(data, 'chat.jsonl');

const defaultState = {
  schema: 'YIB-WORLD-INDEPENDENT-v1',
  world: 'Yemen Intelligence Bridge / WORLD',
  identity: 'الحسام اليمني ⚔️🇾🇪',
  task: 'YIB-KERNEL-001',
  checkpoint: 'YIB-KERNEL-001:0001',
  versionRef: 'v10',
  verification: 'PASS',
  evidence: 'OBSERVED',
  recovery: 'VERIFIED-SIMULATION',
  nextAction: 'resume-from-checkpoint',
  approval: {
    task: 'YIB-APPROVAL-001',
    risk: 'HIGH_RISK_WRITE',
    status: 'WAITING',
    externalSideEffect: 'DISABLED'
  },
  truth: {
    externalDeployment: 'OBSERVED',
    modelConnection: 'UNKNOWN',
    persistence: 'LOCAL_FILE',
    ownership: 'OWNER_CONTROLLED'
  }
};

if (!fs.existsSync(stateFile)) fs.writeFileSync(stateFile, JSON.stringify(defaultState, null, 2));
if (!fs.existsSync(chatFile)) fs.writeFileSync(chatFile, '');

const json = (res, status, body) => {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
};

const page = () => `<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>الحسام اليمني ⚔️🇾🇪</title>
<style>
body{margin:0;background:#0b1020;color:#eef2ff;font-family:system-ui,-apple-system,sans-serif;padding:22px}
main{max-width:900px;margin:auto}.card{background:#121a30;border:1px solid #273352;border-radius:16px;padding:16px;margin:12px 0}
input,button{padding:12px;border-radius:10px;border:1px solid #354260;background:#18233d;color:white}
input{width:68%}.msg{padding:9px;margin:6px 0;background:#18233d;border-radius:10px;white-space:pre-wrap}
small{opacity:.7}.status{font-weight:700}
</style>
</head>
<body>
<main>
<h1>الحسام اليمني ⚔️🇾🇪</h1>
<p>Yemen Intelligence Bridge — WORLD · Independent Core</p>
<div class="card"><div class="status">الحالة التشغيلية</div><pre id="s">جارٍ التحقق…</pre></div>
<div class="card">
<h3>المحادثة والاستمرارية</h3>
<div id="c"></div>
<form id="f"><input id="i" autocomplete="off" placeholder="اكتب رسالتك…"><button>إرسال</button></form>
<small>النواة تحفظ الرسائل. اتصال النموذج الحي غير مُثبت، لذلك لا يتم الادعاء بوجوده.</small>
</div>
</main>
<script>
async function refresh(){
  const state=await (await fetch('/api/state')).json();
  document.getElementById('s').textContent=JSON.stringify(state,null,2);
  const data=await (await fetch('/api/chat')).json();
  document.getElementById('c').innerHTML=(data.messages||[]).map(x=>'<div class="msg"><b>'+x.role+'</b><br>'+escapeHtml(x.content)+'</div>').join('');
}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
document.getElementById('f').addEventListener('submit',async e=>{
  e.preventDefault(); const input=document.getElementById('i'); const v=input.value.trim(); if(!v)return;
  await fetch('/api/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({content:v})});
  input.value=''; await refresh();
});
refresh();
</script>
</body></html>`;

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');

    if (url.pathname === '/api/health')
      return json(res, 200, { status:'PASS', service:'YIB/WORLD Independent Core', truth:'OBSERVED', model:'ADAPTER_NOT_CONFIGURED' });

    if (url.pathname === '/')
      return (res.writeHead(200, {'content-type':'text/html; charset=utf-8'}), res.end(page()));

    if (url.pathname === '/api/state')
      return json(res, 200, JSON.parse(fs.readFileSync(stateFile, 'utf8')));

    if (url.pathname === '/api/chat' && req.method === 'GET') {
      const raw = fs.readFileSync(chatFile, 'utf8').trim();
      return json(res, 200, { messages: raw ? raw.split('\n').map(JSON.parse) : [] });
    }

    if (url.pathname === '/api/chat' && req.method === 'POST') {
      let body = '';
      for await (const chunk of req) body += chunk;
      const message = String(JSON.parse(body || '{}').content || '').trim();
      if (!message) return json(res, 400, { error:'EMPTY_MESSAGE' });
      const now = new Date().toISOString();
      fs.appendFileSync(chatFile, JSON.stringify({role:'user',content:message,at:now})+'\n');
      fs.appendFileSync(chatFile, JSON.stringify({role:'system',content:'تم حفظ الرسالة داخل النواة المستقلة. الاستمرارية محفوظة؛ طبقة النموذج الحي غير مثبتة.',truth:'OBSERVED',at:new Date().toISOString()})+'\n');
      return json(res, 200, { status:'SAVED', truth:'OBSERVED' });
    }

    return json(res, 404, { error:'NOT_FOUND' });
  } catch (error) {
    return json(res, 500, { error:'INTERNAL_ERROR' });
  }
});

server.listen(process.env.PORT || 3000, '0.0.0.0');
