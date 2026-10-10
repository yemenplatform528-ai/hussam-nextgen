import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import pg from 'pg';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const dataDir = path.join(root, 'data');
fs.mkdirSync(dataDir, {recursive:true});
const stateFile = path.join(dataDir, 'canonical.json');
const chatFile = path.join(dataDir, 'chat.jsonl');
const pool=process.env.DATABASE_URL?new pg.Pool({connectionString:process.env.DATABASE_URL,max:2,idleTimeoutMillis:30000}):null;

const requireAuth = process.env.YIB_AUTH_MODE !== 'disabled';
const accessToken = process.env.YIB_ACCESS_TOKEN || '';
const openaiApiKey = process.env.OPENAI_API_KEY || '';
const openaiModel = process.env.OPENAI_MODEL || 'gpt-6-astra';
const geminiApiKey = process.env.GEMINI_API_KEY || '';
const geminiModel = process.env.GEMINI_MODEL || 'gemini-2.5-flash-lite';
const geminiFreeTierEnabled = process.env.YIB_GEMINI_FREE_TIER_ENABLED === 'true';
const geminiEnabled = Boolean(geminiApiKey && geminiFreeTierEnabled);
let lastGenerationVerified = false;

const initial = {
  schema:'YIB-WORLD-INDEPENDENT-v1',
  world:'Yemen Intelligence Bridge / WORLD',
  identity:'الحسام اليمني ⚔️🇾🇪',
  task:'YIB-KERNEL-001',
  checkpoint:'YIB-KERNEL-001:0001',
  versionRef:'independent-local-v1',
  tiniestPortal:'OBSERVED_V68',
  verification:'PASS',
  evidence:'OBSERVED',
  recovery:'VERIFIED-SIMULATION',
  nextAction:'resume-from-checkpoint',
  approval:{task:'YIB-APPROVAL-001',risk:'HIGH_RISK_WRITE',status:'WAITING',externalSideEffect:'DISABLED'},
  truth:{externalDeployment:'UNKNOWN',modelConnection:'UNKNOWN',persistence:'LOCAL_FILE',ownership:'OWNER_CONTROLLED'},
  capabilities:{localPersistence:pool?'POSTGRES_DURABLE':'LOCAL_FILE_ONLY',localContinuity:'EXECUTABLE',aiAdapter:geminiEnabled?'GEMINI_FREE_TIER_CONFIGURED_UNVERIFIED':(openaiApiKey && process.env.YIB_ALLOW_BILLABLE_AI === 'true'?'OPENAI_CONFIGURED_UNVERIFIED':'NOT_CONFIGURED'),externalFetch:'UNKNOWN',highRiskEffects:'FAIL-CLOSED'},
  updatedAt:new Date().toISOString()
};
if(!fs.existsSync(stateFile)) fs.writeFileSync(stateFile,JSON.stringify(initial,null,2));
if(!fs.existsSync(chatFile)) fs.writeFileSync(chatFile,'');

const json=(res,status,obj)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','x-frame-options':'DENY'});res.end(JSON.stringify(obj));};
const auth=req=>!requireAuth || (!!accessToken && req.headers.authorization===`Bearer ${accessToken}`);
const readJson=f=>JSON.parse(fs.readFileSync(f,'utf8'));
const localMessages=()=>fs.readFileSync(chatFile,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const getState=async()=>{if(!pool)return readJson(stateFile);const r=await pool.query("SELECT value FROM public.yib_runtime_state WHERE key='canonical'");return r.rows[0]?.value||initial;};
const getMessages=async()=>{if(!pool)return localMessages();const r=await pool.query('SELECT role,content,truth,model,at FROM public.yib_chat_messages ORDER BY id');return r.rows;};
const saveMessage=async m=>{if(pool){await pool.query('INSERT INTO public.yib_chat_messages(role,content,truth,model,at) VALUES($1,$2,$3,$4,$5)',[m.role,m.content,m.truth||null,m.model||null,m.at||new Date().toISOString()]);return;}fs.appendFileSync(chatFile,JSON.stringify(m)+'\n');};
async function initPersistence(){
 if(!pool)return;
 const state=await pool.query("SELECT key FROM public.yib_runtime_state WHERE key='canonical'");
 if(!state.rowCount){const seed=fs.existsSync(stateFile)?readJson(stateFile):initial;await pool.query('INSERT INTO public.yib_runtime_state(key,value) VALUES($1,$2::jsonb)',['canonical',JSON.stringify(seed)]);}
 const count=await pool.query('SELECT count(*)::int AS n FROM public.yib_chat_messages');
 if(count.rows[0].n===0){for(const m of localMessages())await saveMessage(m);}
}

const localResponse=content=>{
 const q=content.trim().toLowerCase();
 if(/^(الحقيقة|truth|status|الحالة)$/.test(q)) return 'الحقيقة التشغيلية: النواة المستقلة تعمل، والاستمرارية المحلية مثبتة؛ النموذج الحي لا يُدّعى دون استجابة ناجحة؛ الآثار عالية المخاطر FAIL-CLOSED.';
 if(/^(استمر|اكمل|continue|resume)$/.test(q)) return 'استمرار آمن: نقطة YIB-KERNEL-001:0001 محفوظة والحالة قابلة للاستئناف. أي أثر خارجي يحتاج تحققًا وموافقة بشرية عند اللزوم.';
 if(/^(تعافي|recovery|استرداد)$/.test(q)) return 'التعافي: الحالة المحلية قابلة للتصدير، ونقطة الاسترداد محفوظة؛ لا يتم رفع UNKNOWN إلى VERIFIED دون دليل.';
 if(/^(قدرات|capabilities|القدرة)$/.test(q)) return 'القدرات: local persistence EXECUTABLE؛ local continuity EXECUTABLE؛ AI adapter NOT_CONFIGURED؛ external fetch UNKNOWN؛ high-risk effects FAIL-CLOSED.';
 return 'تم حفظ رسالتك داخل النواة المستقلة. لا يوجد نموذج حي مثبت حاليًا، لذلك لن أختلق ردًا من نموذج.';
};

const configuredProvider=()=>geminiEnabled?{name:'GEMINI',model:geminiModel}:((openaiApiKey && process.env.YIB_ALLOW_BILLABLE_AI === 'true')?{name:'OPENAI',model:openaiModel}:null);

const modelResponse=async(history)=>{
 lastGenerationVerified=false;
 const provider=configuredProvider();
 if(!provider) return {content:localResponse(history.at(-1)?.content||''),truth:'OBSERVED',model:openaiApiKey?'BILLABLE_AI_DISABLED':'ADAPTER_NOT_CONFIGURED'};
 const instructions='أنت طبقة الذكاء القابلة للاستبدال داخل YIB/WORLD. اليمن هو الغاية؛ الذكاء الاصطناعي طبقة قدرة. كن دقيقًا. لا تدّع تنفيذًا خارجيًا لم يحدث، وافصل VERIFIED عن OBSERVED وUNKNOWN. لا تنفذ آثارًا عالية المخاطر تلقائيًا. أجب بالعربية افتراضيًا.';
 try {
  if(provider.name==='GEMINI'){
   const contents=history.slice(-20).filter(m=>m.role==='user'||m.role==='system'||m.role==='assistant').map(m=>({role:m.role==='user'?'user':'model',parts:[{text:String(m.content||'')}]})).filter(m=>m.parts[0].text.trim());
   const r=await fetch('https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(provider.model)+':generateContent',{
    method:'POST',headers:{'content-type':'application/json','x-goog-api-key':geminiApiKey},signal:AbortSignal.timeout(25000),
    body:JSON.stringify({systemInstruction:{parts:[{text:instructions}]},contents,generationConfig:{temperature:0.3,maxOutputTokens:2048}})
   });
   if(!r.ok) return {content:'تعذّر الحصول على إجابة من مزود Gemini (HTTP '+r.status+'). لم يتم استبدال الخطأ بإجابة مولّدة محليًا.',truth:'OBSERVED',model:provider.model,providerStatus:r.status};
   const data=await r.json();
   const content=(data.candidates?.[0]?.content?.parts||[]).map(p=>p.text||'').join('').trim();
   if(!content) return {content:'وصل رد من مزود Gemini لكنه لا يحتوي على نص قابل للعرض. لم يتم ادعاء نجاح التوليد.',truth:'OBSERVED',model:provider.model};
   lastGenerationVerified=true;
   return {content,truth:'VERIFIED',model:provider.model,provider:'GEMINI'};
  }
  const input=history.slice(-20).map(m=>({role:m.role==='system'?'assistant':m.role,content:m.content}));
  const r=await fetch('https://api.openai.com/v1/responses',{method:'POST',headers:{'content-type':'application/json','authorization':`Bearer ${openaiApiKey}`},signal:AbortSignal.timeout(25000),body:JSON.stringify({model:provider.model,instructions,input})});
  if(!r.ok) return {content:'تعذّر الحصول على إجابة من مزود OpenAI (HTTP '+r.status+'). لم يتم اختلاق إجابة.',truth:'OBSERVED',model:provider.model,providerStatus:r.status};
  const data=await r.json();
  if(!String(data.output_text||'').trim()) return {content:'وصل رد من مزود OpenAI دون نص قابل للعرض. لم يتم ادعاء نجاح التوليد.',truth:'OBSERVED',model:provider.model};
  lastGenerationVerified=true;
  return {content:data.output_text,truth:'VERIFIED',model:provider.model,provider:'OPENAI'};
 } catch(e) {
  return {content:'تعذّر الاتصال بمزود الذكاء الاصطناعي أو انتهت مهلة الانتظار. لم يتم اختلاق إجابة؛ يمكنك إعادة المحاولة.',truth:'OBSERVED',model:provider.model,reason:e?.name==='TimeoutError'?'TIMEOUT':'NETWORK_ERROR'};
 }
};

const serveStatic=(u,res)=>{
 const rel=u.pathname==='/'?'/index.html':u.pathname;
 const file=path.resolve(root,'web',path.normalize(rel).replace(/^[/\\\\]+/,''));
 const webRoot=path.resolve(root,'web');
 if(!file.startsWith(webRoot+path.sep)) return json(res,403,{error:'FORBIDDEN'});
 if(!fs.existsSync(file)||!fs.statSync(file).isFile()) return json(res,404,{error:'NOT_FOUND'});
 const type=file.endsWith('.html')?'text/html; charset=utf-8':file.endsWith('.css')?'text/css; charset=utf-8':'application/octet-stream';
 res.writeHead(200,{'content-type':type,'cache-control':'no-store','x-content-type-options':'nosniff','x-frame-options':'DENY'});res.end(fs.readFileSync(file));
};

const server=http.createServer(async(req,res)=>{
 try{
  const u=new URL(req.url,'http://localhost');
  if(req.method==='GET'&&u.pathname==='/api/health') {const p=configuredProvider();return json(res,200,{status:'PASS',service:'YIB/WORLD Independent Core',truth:'OBSERVED',provider:p?.name||'NONE',model:p?.model||null,modelConfigured:Boolean(p),liveModelVerified:lastGenerationVerified,auth:requireAuth?'REQUIRED':'DISABLED',persistence:pool?'POSTGRES_DURABLE':'LOCAL_FILE_ONLY',freeTierGate:geminiFreeTierEnabled,paidOpenAIAllowed:process.env.YIB_ALLOW_BILLABLE_AI==='true',highRisk:'FAIL-CLOSED',time:new Date().toISOString()});}
  if(req.method==='GET'&&u.pathname==='/api/capabilities') {const p=configuredProvider();return json(res,200,{truth:'OBSERVED',capabilities:{localPersistence:pool?'POSTGRES_DURABLE':'LOCAL_FILE_ONLY',localContinuity:'EXECUTABLE',aiAdapter:p?(p.name+'_CONFIGURED_UNVERIFIED'):'NOT_CONFIGURED',generationTested:false,externalFetch:'UNKNOWN',highRiskEffects:'FAIL-CLOSED'}});}
  if(req.method==='GET'&&u.pathname==='/api/provider') {const p=configuredProvider();return json(res,200,{truth:'OBSERVED',provider:p?.name||'NONE',model:p?.model||null,liveModelVerified:lastGenerationVerified,generationTested:lastGenerationVerified,reason:p?'NOT_TESTED':(geminiApiKey?'GEMINI_FREE_TIER_GATE_DISABLED':'NO_ENABLED_PROVIDER')});}
  if(req.method==='GET'&&!u.pathname.startsWith('/api/')) return serveStatic(u,res);
  if(!auth(req)) return json(res,401,{error:'AUTH_REQUIRED'});
  if(req.method==='GET'&&u.pathname==='/api/provider/check'){
   const p=configuredProvider();
   if(!p) return json(res,200,{truth:'OBSERVED',provider:'NONE',configuredModelAvailable:false,reason:geminiApiKey?'GEMINI_FREE_TIER_GATE_DISABLED':'NO_ENABLED_PROVIDER',generationTested:false});
   try {
    const endpoint=p.name==='GEMINI'
     ? 'https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(p.model)+'?key='+encodeURIComponent(geminiApiKey)
     : 'https://api.openai.com/v1/models';
    const check=await fetch(endpoint,{headers:p.name==='OPENAI'?{authorization:`Bearer ${openaiApiKey}`}:{},signal:AbortSignal.timeout(8000)});
    if(!check.ok) return json(res,200,{truth:'OBSERVED',provider:p.name,model:p.model,credentialAccepted:check.status!==401&&check.status!==403,providerStatus:check.status,configuredModelAvailable:null,generationTested:false,reason:check.status===429?'RATE_LIMIT_OR_QUOTA':'PROVIDER_CHECK_FAILED'});
    const catalog=await check.json();
    const found=p.name==='GEMINI' ? catalog.name?.endsWith('/'+p.model)===true : Array.isArray(catalog.data)&&catalog.data.some(m=>m.id===p.model);
    return json(res,200,{truth:'VERIFIED',provider:p.name,credentialAccepted:true,model:p.model,configuredModelAvailable:found,generationTested:false,check:'model metadata only; no generation request'});
   } catch(e) {return json(res,200,{truth:'OBSERVED',provider:p.name,model:p.model,configuredModelAvailable:null,generationTested:false,reason:e?.name==='TimeoutError'?'TIMEOUT':'NETWORK_OR_ERROR'});}
  }
  if(req.method==='GET'&&u.pathname==='/api/state') return json(res,200,await getState());
  if(req.method==='GET'&&u.pathname==='/api/chat') return json(res,200,{messages:await getMessages()});
  if(req.method==='POST'&&u.pathname==='/api/chat'){
   let s='';for await(const c of req)s+=c;let b={};try{b=JSON.parse(s||'{}')}catch{return json(res,400,{error:'INVALID_JSON'})}
   const content=String(b.content||'').trim();if(!content)return json(res,400,{error:'EMPTY_MESSAGE'});
   const now=new Date().toISOString();await saveMessage({role:'user',content,at:now});
   const replyData=await modelResponse(await getMessages());
   const reply={role:'system',content:replyData.content,truth:replyData.truth,model:replyData.model,provider:replyData.provider||null,providerStatus:replyData.providerStatus||null,reason:replyData.reason||null,liveModelVerified:replyData.truth==='VERIFIED'&&Boolean(replyData.provider),at:new Date().toISOString()};
   await saveMessage(reply);return json(res,200,reply);
  }
  if(req.method==='GET'&&u.pathname==='/api/export') return json(res,200,{exportedAt:new Date().toISOString(),state:await getState(),messages:await getMessages(),truth:'OBSERVED',manifest:'YIB-WORLD-INDEPENDENT-v1'});
  return json(res,404,{error:'NOT_FOUND'});
 }catch(e){return json(res,500,{error:'INTERNAL_ERROR'});}
});
initPersistence().then(()=>server.listen(process.env.PORT||3000,'0.0.0.0',()=>console.log('YIB/WORLD Independent Core listening; persistence='+(pool?'POSTGRES_DURABLE':'LOCAL_FILE_ONLY')))).catch(e=>{console.error('Persistence initialization failed',e.message);process.exit(1);});
