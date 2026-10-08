import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const data = path.join(root, 'data');
fs.mkdirSync(data, { recursive: true });

const stateFile = path.join(data, 'canonical.json');
const chatFile = path.join(data, 'chat.jsonl');

const REQUIRE_AUTH = process.env.REQUIRE_AUTH === 'true';
const ACCESS_TOKEN = process.env.YIB_ACCESS_TOKEN || '';
const MODEL_PROVIDER = (process.env.MODEL_PROVIDER || 'auto').toLowerCase();
const GEMINI_KEY = process.env.GEMINI_API_KEY || '';
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-3.8-flash';
const GROQ_KEY = process.env.GROQ_API_KEY || '';
const GROQ_MODEL = process.env.GROQ_MODEL || 'openai/gpt-oss-120b';
const HF_KEY = process.env.HF_TOKEN || '';
const HF_MODEL = process.env.HF_MODEL || 'deepseek-ai/DeepSeek-V3-0324';
const OPENAI_KEY = process.env.OPENAI_API_KEY || '';
const OPENAI_MODEL = process.env.OPENAI_MODEL || 'gpt-6-luna';
const OPENAI_BASE_URL = (process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, '');

function configuredProviders() {
  const p = [];
  if (GEMINI_KEY) p.push('gemini');
  if (GROQ_KEY) p.push('groq');
  if (HF_KEY) p.push('huggingface');
  if (OPENAI_KEY) p.push('openai');
  return p;
}
function selectedProvider() {
  if (MODEL_PROVIDER !== 'auto') return configuredProviders().includes(MODEL_PROVIDER) ? MODEL_PROVIDER : 'none';
  return configuredProviders()[0] || 'none';
}

const defaultState = {
  schema: 'YIB-WORLD-INDEPENDENT-v2',
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
    modelConnection: selectedProvider() === 'none' ? 'NOT_CONFIGURED' : 'CONFIGURED',
    persistence: 'EPHEMERAL_RUNTIME_WITH_EXPORT',
    ownership: 'OWNER_CONTROLLED'
  },
  model: {
    provider: selectedProvider(),
    configuredProviders: configuredProviders(),
    liveVerified: false
  }
};

if (!fs.existsSync(stateFile)) fs.writeFileSync(stateFile, JSON.stringify(defaultState, null, 2));
if (!fs.existsSync(chatFile)) fs.writeFileSync(chatFile, '');

const json = (res, status, body) => {
  res.writeHead(status, {'content-type':'application/json; charset=utf-8'});
  res.end(JSON.stringify(body));
};
const authorized = req => !REQUIRE_AUTH || (!!ACCESS_TOKEN && req.headers.authorization === 'Bearer ' + ACCESS_TOKEN);

function readHistory() {
  const raw = fs.readFileSync(chatFile, 'utf8').trim();
  if (!raw) return [];
  return raw.split('\n').map(JSON.parse).filter(x => x.role === 'user' || x.role === 'assistant').slice(-24);
}
function saveMessage(role, content, extra = {}) {
  fs.appendFileSync(chatFile, JSON.stringify({role, content, at:new Date().toISOString(), ...extra}) + '\n');
}

const SYSTEM = 'You are the AI capability layer for YIB/WORLD — الحسام اليمني ⚔️🇾🇪. Yemen is the purpose; AI is a capability layer, not authority. Preserve truth categories VERIFIED/OBSERVED/REPORTED/INFERRED/BLOCKED/UNKNOWN. Never claim an external action unless it is verified. Maintain continuity from the supplied history.';

async function callGemini(history) {
  const contents = history.map(x => ({role:x.role === 'assistant' ? 'model' : 'user', parts:[{text:String(x.content)}]}));
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/' + encodeURIComponent(GEMINI_MODEL) + ':generateContent?key=' + encodeURIComponent(GEMINI_KEY);
  const r = await fetch(url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({
    systemInstruction:{parts:[{text:SYSTEM}]},
    contents,
    generationConfig:{temperature:0.2}
  })});
  const b = await r.json().catch(()=>({}));
  if (!r.ok) return {ok:false,provider:'gemini',reason:'MODEL_HTTP_'+r.status,detail:b?.error?.message || 'GEMINI_REQUEST_FAILED'};
  const text = String(b?.candidates?.[0]?.content?.parts?.map(p=>p.text||'').join('') || '').trim();
  return text ? {ok:true,provider:'gemini',model:GEMINI_MODEL,content:text,truth:'OBSERVED'} : {ok:false,provider:'gemini',reason:'EMPTY_MODEL_RESPONSE'};
}

async function callOpenAICompatible(baseUrl, key, model, provider, history) {
  const messages = [{role:'system',content:SYSTEM}, ...history.map(x => ({role:x.role,content:String(x.content)}))];
  const r = await fetch(baseUrl + '/chat/completions',{method:'POST',headers:{'content-type':'application/json','authorization':'Bearer '+key},body:JSON.stringify({model,messages,temperature:0.2})});
  const b = await r.json().catch(()=>({}));
  if (!r.ok) return {ok:false,provider,reason:'MODEL_HTTP_'+r.status,detail:b?.error?.message || 'MODEL_REQUEST_FAILED'};
  const text = String(b?.choices?.[0]?.message?.content || '').trim();
  return text ? {ok:true,provider,model,content:text,truth:'OBSERVED'} : {ok:false,provider,reason:'EMPTY_MODEL_RESPONSE'};
}

async function callLiveModel(userMessage) {
  const history = [...readHistory(), {role:'user',content:userMessage}].slice(-24);
  const provider = selectedProvider();
  if (provider === 'none') return {ok:false,truth:'BLOCKED',reason:'NO_FREE_MODEL_CREDENTIAL_CONFIGURED'};
  if (provider === 'gemini') return callGemini(history);
  if (provider === 'groq') return callOpenAICompatible('https://api.groq.com/openai/v1',GROQ_KEY,GROQ_MODEL,'groq',history);
  if (provider === 'huggingface') return callOpenAICompatible('https://router.huggingface.co/v1',HF_KEY,HF_MODEL,'huggingface',history);
  if (provider === 'openai') {
    const r = await fetch(OPENAI_BASE_URL + '/responses',{method:'POST',headers:{'content-type':'application/json','authorization':'Bearer '+OPENAI_KEY},body:JSON.stringify({model:OPENAI_MODEL,input:[{role:'developer',content:SYSTEM},...history],reasoning:{effort:'low'}})});
    const b = await r.json().catch(()=>({}));
    if (!r.ok) return {ok:false,provider:'openai',reason:'MODEL_HTTP_'+r.status,detail:b?.error?.message || 'MODEL_REQUEST_FAILED'};
    const text = String(b.output_text || '').trim();
    return text ? {ok:true,provider:'openai',model:OPENAI_MODEL,content:text,truth:'OBSERVED'} : {ok:false,provider:'openai',reason:'EMPTY_MODEL_RESPONSE'};
  }
  return {ok:false,truth:'BLOCKED',reason:'PROVIDER_NOT_SUPPORTED'};
}

function updateState(patch) {
  const current = JSON.parse(fs.readFileSync(stateFile,'utf8'));
  const next = {...current,...patch,truth:{...current.truth,...(patch.truth||{})},model:{...current.model,...(patch.model||{})}};
  fs.writeFileSync(stateFile,JSON.stringify(next,null,2));
  return next;
}

const page = () => `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>الحسام اليمني ⚔️🇾🇪</title><style>
body{margin:0;background:#08111f;color:#edf4ff;font-family:system-ui,-apple-system,sans-serif;padding:18px}main{max-width:920px;margin:auto}.card{background:#101c2e;border:1px solid #263953;border-radius:18px;padding:16px;margin:12px 0;box-shadow:0 8px 30px #0004}h1{margin-bottom:4px}input,button{padding:13px;border-radius:11px;border:1px solid #39506f;background:#14243b;color:#fff;font-size:16px}input{width:68%}button{cursor:pointer}.msg{padding:10px;margin:7px 0;background:#162a43;border-radius:12px;white-space:pre-wrap}.meta{opacity:.7;font-size:12px}.ok{font-weight:700}.warn{font-weight:700}pre{white-space:pre-wrap;word-break:break-word}</style></head><body><main>
<h1>الحسام اليمني ⚔️🇾🇪</h1><div class="meta">Yemen Intelligence Bridge — WORLD · Independent Core</div>
<div class="card"><div class="ok">الحالة التشغيلية</div><pre id="s">جارٍ التحقق…</pre><div class="meta">نسخة الاستمرارية: WORLD v2 · التأثيرات الخارجية: مغلقة افتراضيًا · تصدير الاستعادة متاح من /api/export</div></div>
<div class="card"><h3>المحادثة والاستمرارية</h3><div id="c"></div><form id="f"><input id="i" autocomplete="off" placeholder="اكتب رسالتك…"><button>إرسال</button></form><div class="meta" id="m"></div></div>
</main><script>
async function refresh(){const [sr,cr]=await Promise.all([fetch('/api/state'),fetch('/api/chat')]);const state=await sr.json();const data=await cr.json();document.getElementById('s').textContent=JSON.stringify(state,null,2);document.getElementById('c').innerHTML=(data.messages||[]).map(x=>'<div class="msg"><b>'+x.role+'</b><br>'+escapeHtml(x.content)+'<div class="meta">'+(x.provider||x.truth||'')+'</div></div>').join('');document.getElementById('m').textContent=state.model?.liveVerified?'النموذج الحي: مُثبت بمشاهدة استجابة ناجحة.':'النواة والاستمرارية تعملان؛ النموذج الحي لن يُدّعى إلا بعد نجاح حقيقي.';}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
document.getElementById('f').addEventListener('submit',async e=>{e.preventDefault();const input=document.getElementById('i');const v=input.value.trim();if(!v)return;input.disabled=true;await fetch('/api/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({content:v})});input.value='';input.disabled=false;await refresh();});refresh();
</script></body></html>`;

const server=http.createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://localhost');
    if(!authorized(req)) return json(res,401,{error:'UNAUTHORIZED'});
    if(url.pathname==='/api/health'){const s=JSON.parse(fs.readFileSync(stateFile,'utf8'));return json(res,200,{status:'PASS',service:'YIB/WORLD Independent Core',truth:'OBSERVED',model:selectedProvider()==='none'?'MODEL_NOT_CONFIGURED':selectedProvider(),liveVerified:Boolean(s.model?.liveVerified),persistence:s.truth?.persistence||'UNKNOWN'});}
    if(url.pathname==='/') return (res.writeHead(200,{'content-type':'text/html; charset=utf-8'}),res.end(page()));
    if(url.pathname==='/api/capabilities'){const s=JSON.parse(fs.readFileSync(stateFile,'utf8'));return json(res,200,{truth:'OBSERVED',independentCore:true,continuity:true,providers:{configured:configuredProviders(),selected:selectedProvider()},liveModelVerified:Boolean(s.model?.liveVerified),externalSideEffects:'FAIL_CLOSED',ownerRecoveryExport:'/api/export'});}
    if(url.pathname==='/api/state') return json(res,200,JSON.parse(fs.readFileSync(stateFile,'utf8')));
    if(url.pathname==='/api/export'&&req.method==='GET'){const state=JSON.parse(fs.readFileSync(stateFile,'utf8'));const raw=fs.readFileSync(chatFile,'utf8');const payload={exportedAt:new Date().toISOString(),state,chat:raw?raw.split('\n').filter(Boolean).map(JSON.parse):[],manifest:'YIB-WORLD-INDEPENDENT-v2'};res.writeHead(200,{'content-type':'application/json; charset=utf-8','content-disposition':'attachment; filename="yib-world-export.json"'});return res.end(JSON.stringify(payload,null,2));}
    if(url.pathname==='/api/chat'&&req.method==='GET'){const raw=fs.readFileSync(chatFile,'utf8').trim();return json(res,200,{messages:raw?raw.split('\n').map(JSON.parse):[]});}
    if(url.pathname==='/api/chat'&&req.method==='POST'){
      let body='';for await(const chunk of req)body+=chunk;const message=String(JSON.parse(body||'{}').content||'').trim();if(!message)return json(res,400,{error:'EMPTY_MESSAGE'});
      saveMessage('user',message);
      const result=await callLiveModel(message);
      if(result.ok){saveMessage('assistant',result.content,{provider:result.provider,model:result.model,truth:'OBSERVED'});updateState({truth:{modelConnection:'LIVE_VERIFIED'},model:{provider:result.provider,liveVerified:true,lastVerifiedAt:new Date().toISOString()}});return json(res,200,{status:'RESPONDED',truth:'OBSERVED',provider:result.provider,content:result.content});}
      saveMessage('system','تم حفظ رسالتك داخل النواة. لم تُثبت استجابة نموذج حي، لذلك لن أدّعي وجودها.',{truth:'BLOCKED',reason:result.reason});
      return json(res,200,{status:'SAVED_ONLY',truth:'BLOCKED',reason:result.reason,detail:result.detail||null});
    }
    return json(res,404,{error:'NOT_FOUND'});
  }catch(error){return json(res,500,{error:'INTERNAL_ERROR'});}
});
server.listen(process.env.PORT||3000,'0.0.0.0');
