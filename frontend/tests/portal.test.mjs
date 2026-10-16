import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs/promises';
import {ApiClient,ApiError} from '../portal/src/js/api-client.js';
import {parseEmailInput,portalForUser,canReview,canManageUsers,routeAllowed} from '../portal/src/js/portal-policy.js';
import {DemoAdapter} from '../portal/src/js/demo-adapter.js';import {initialState} from '../portal/src/js/domain.js';
import {consumeOwnerSetup} from '../portal/src/js/auth-setup.js';
import {progressHTML} from '../portal/src/js/work-progress.js';
import {calculate} from '../portal/src/js/money.js';
const fixtures=JSON.parse(await fs.readFile(new URL('../portal/public/fixtures/manifest.json',import.meta.url),'utf8'));

test('Browser and backend share half-up rounding, six-decimal inputs and delta direction',async()=>{
  const cases=JSON.parse(await fs.readFile(new URL('../../tests/fixtures/invoice_math.json',import.meta.url),'utf8'));
  const expectedCents=value=>{const [whole,fraction='']=value.split('.');return Number(BigInt(whole+fraction.padEnd(2,'0')));};
  for(const c of cases){
    const draft={invoice_discount_amount:c.discount,invoice_tax_amount:c.tax,total_amount:c.reported,
      line_items:c.items.map(row=>Object.fromEntries(['quantity','unit_price','discount_amount','tax_amount','line_total'].map((k,i)=>[k,row[i]])))};
    const actual=calculate(draft);
    assert.deepEqual(actual,{rows:c.items.map(row=>expectedCents(row[4])),subtotal:expectedCents(c.subtotal),total:expectedCents(c.total),delta:expectedCents(c.delta)},c.name);
    assert.equal(draft.total_amount,c.reported,'Source total must remain unchanged');
  }
});

test('Client lifecycle carries both optimistic versions through the authenticated API',async()=>{
  let captured;
  const api=new ApiClient(async(url,opts)=>{captured={url,opts};return new Response(JSON.stringify({data:{lifecycle:{state:'CLOSED'}}}));});
  api.csrf='test';
  const payload={action:'CLOSE',reason:'Accepted',expected_lifecycle_revision:2,expected_versions:{invoice:4}};
  await api.lifecycle('request/encoded',payload);
  assert.equal(captured.url,'/api/requests/request%2Fencoded/lifecycle');
  assert.deepEqual(JSON.parse(captured.opts.body),payload);
  assert.equal(captured.opts.headers['X-CSRF-Token'],'test');
});

test('Work progress escapes client notes and renders only server-authorized controls',()=>{
  const escape=v=>String(v??'').replaceAll('<','&lt;').replaceAll('>','&gt;');
  const request={lifecycle:{state:'CLOSED'},work_status:'CLOSED',updated_at:'2026-10-15T00:00:00Z',
    client_revision_note:'<script>alert(1)</script>',invoice_count:1,voucher_count:1,allowed_actions:[]};
  const html=progressHTML(request,escape,'client');
  assert.doesNotMatch(html,/<script>|id="close-work"|id="request-revision"/);
  assert.match(html,/Pekerjaan ditutup/);
  const client=progressHTML({...request,allowed_actions:['REQUEST_REVISION']},escape,'client');
  assert.match(client,/id="request-revision"/);
  assert.doesNotMatch(client,/id="close-work"/);
});

for(const suffix of ['review','view'])test(`/${suffix} requests reviewer access and retains exact email identity`,async()=>{assert.deepEqual(parseEmailInput(` Reviewer.Test+amiga@Example.test /${suffix.toUpperCase()} `),{email:'reviewer.test+amiga@example.test',adminRequested:false,reviewerRequested:true});for(const invalid of ['atmin/view','atmin/review','review/view','view/atmin'])assert.throws(()=>parseEmailInput('a@example.test/'+invalid));const a=mockAdapter();let session=await a.login({email_input:'new@example.test/'+suffix});assert.equal(session.user.account_status,'PENDING_REVIEWER');assert.deepEqual(session.user.roles,[]);await assert.rejects(()=>a.list(),e=>e.status===403);session=await a.login({email_input:'reviewer@amiga.example/'+suffix});assert.equal(session.portal,'reviewer');assert.equal(canReview(session.user),true);});

test('Old auth server is rejected without guessing Google or sending credentials',async()=>{const calls=[];const api=new ApiClient(async(url,opts)=>{calls.push(url);return new Response(JSON.stringify({data:{csrf_token:'old',google_client_id:'',auth_configured:false}}));});await assert.rejects(()=>api.config(),e=>e.code==='AUTH_SERVER_OUTDATED'&&/Start-AMIGA.cmd/.test(e.message));assert.deepEqual(calls,['/api/auth/csrf']);assert.equal(api.authMethod,'local_password');});

test('Google login is selected only when the server explicitly configures Google',async()=>{const calls=[];const api=new ApiClient(async(url,opts)=>{calls.push(url);return new Response(JSON.stringify({data:url.endsWith('/csrf')?{csrf_token:'test',auth_method:'google'}:{portal:'client'}}));});await api.config();await api.login({credential:'fixture'});assert.deepEqual(calls,['/api/auth/csrf','/api/auth/google']);});

test('Owner setup capability is removed from the URL immediately and never accepted as a regular route',()=>{const calls=[],history={replaceState(...args){calls.push(args);}},token='x'.repeat(43);assert.equal(consumeOwnerSetup({pathname:'/login',search:'',hash:'#owner-setup='+token},history),token);assert.deepEqual(calls,[[null,'','/login']]);assert.equal(consumeOwnerSetup({pathname:'/admin',search:'',hash:'#owner-setup='+token},history),'');assert.equal(consumeOwnerSetup({pathname:'/login',search:'',hash:'#owner-setup=bad'},history),'');});
const mockAdapter=()=>new DemoAdapter(initialState(),fixtures,{readFile:async()=>new Uint8Array(),storeFile:async()=>'stored'},()=>{});
async function add(adapter,fixture='normal',actor='owner-a',client='A'){const f=fixtures.find(x=>x.id===fixture);return adapter.service.submit(actor,{client,date:'2026-10-15',due:'2026-10-22',requestType:'Invoice vendor',channel:'Portal'},{type:'INVOICE',name:f.file,hash:f.sha256,pages:1,size:1500,storageKey:'stored'});}
test('Email /atmin is parsed as an activation request without altering Gmail dots/plus',()=>{assert.deepEqual(parseEmailInput(' Gerardus.Test+amiga@Gmail.com /atmin '),{email:'gerardus.test+amiga@gmail.com',adminRequested:true,reviewerRequested:false});assert.deepEqual(parseEmailInput('gerardus@gmail.com'),{email:'gerardus@gmail.com',adminRequested:false,reviewerRequested:false});assert.throws(()=>parseEmailInput('x@gmail.com /admin'),/valid/);assert.throws(()=>parseEmailInput('xgmail.com /atmin'));});
test('Portal roles: clients cannot enter admin; System Admin cannot approve even with reviewer combination',()=>{const owner={account_status:'ACTIVE',roles:['CLIENT_OWNER']},admin={account_status:'ACTIVE',roles:['SYSTEM_ADMIN','FINANCE_REVIEWER']};assert.equal(portalForUser(owner),'client');assert.equal(routeAllowed(owner,'admin'),false);assert.equal(canReview(owner),false);assert.equal(canManageUsers(admin),true);assert.equal(canReview(admin),false);assert.equal(portalForUser({...admin,account_status:'PENDING_ADMIN'}),'pending');});
test('Unknown email /atmin remains pending and gains no admin privileges in preview',async()=>{const adapter=mockAdapter();const s=await adapter.login({email_input:'example@gmail.com /atmin'});assert.equal(s.user.email,'example@gmail.com');assert.equal(s.user.account_status,'PENDING_ADMIN');assert.deepEqual(s.user.roles,[]);assert.equal(s.portal,'pending');await assert.rejects(()=>adapter.list(),e=>e.status===403);});
test('Registered preview admin logs in without suffix later; session logout removes access',async()=>{const a=mockAdapter();let s=await a.login({email_input:'atmin@amiga.example /atmin'});assert.equal(s.portal,'admin');await a.logout();s=await a.login({email_input:'atmin@amiga.example'});assert.deepEqual(s.user.roles,['SYSTEM_ADMIN']);assert.equal((await a.me()).user.email,'atmin@amiga.example');await a.logout();await assert.rejects(()=>a.me(),e=>e.status===401);});
test('Preview adapter preserves tenant restriction on detail/list/document and rejects client account management',async()=>{const a=mockAdapter();const r=await add(a,'normal','owner-b','B');await a.login({email_input:'klien-a@amiga.example'});assert.equal((await a.list()).total,0);await assert.rejects(()=>a.detail(r.id),/Akses ditolak/);await assert.rejects(()=>a.document(r.id,r.documents[0].id),/Akses ditolak/);await assert.rejects(()=>a.users(),e=>e.status===403);});
test('Preview API shape exposes all line items and exact currency values; reviewer can approve',async()=>{const a=mockAdapter();const r=await add(a);await a.login({email_input:'reviewer@amiga.example'});let d=await a.detail(r.id);assert.equal(d.invoices[0].fields.line_items.length,3);assert.equal(d.invoices[0].validation.calculated.total,'650000.00');assert.equal(d.invoices[0].current_version,1);await a.decision(r.id,d.invoices[0].id,'approve',{expected_version:1});d=await a.detail(r.id);assert.equal(d.invoices[0].review_status,'APPROVED');assert.ok(d.invoices[0].allowed_actions.includes('DOWNLOAD_VOUCHER'));});
test('Preview pending or disabled user never obtains request data',async()=>{const a=mockAdapter();await add(a);await a.login({email_input:'atmin@amiga.example'});await assert.rejects(()=>a.updateUser('owner-a',{account_status:'INVENTED'}),/ACTIVE/);await a.updateUser('owner-a',{account_status:'DISABLED'});const s=await a.login({email_input:'klien-a@amiga.example'});assert.equal(s.portal,'pending');assert.equal(s.user.account_status,'DISABLED');await assert.rejects(()=>a.list(),e=>e.status===403);});
test('API client sends cookie credentials and server CSRF, encodes ids and preserves decimal strings',async()=>{const calls=[];const api=new ApiClient(async(url,opts)=>{calls.push({url,opts});return new Response(JSON.stringify({data:url.endsWith('/csrf')?{csrf_token:'server-csrf',auth_method:'local_password'}:{ok:true}}),{headers:{'Content-Type':'application/json'}});});await api.config();await api.invoice('req/id','invoice?1',{expected_version:2,fields:{total_amount:'650000.10'},reason:'Test'});assert.equal(calls[1].url,'/api/requests/req%2Fid/invoices/invoice%3F1');assert.equal(calls[1].opts.credentials,'same-origin');assert.equal(calls[1].opts.headers['X-CSRF-Token'],'server-csrf');assert.equal(JSON.parse(calls[1].opts.body).fields.total_amount,'650000.10');});
test('Live backend failure never falls back to simulated data',async()=>{const api=new ApiClient(async()=>{throw Error('offline');});await assert.rejects(()=>api.list(),e=>e instanceof ApiError&&e.code==='BACKEND_UNAVAILABLE');assert.equal(api.mode,'live');});

test('Local auth config selects register/login endpoints without storing password or JWT',async()=>{const calls=[];const api=new ApiClient(async(url,opts)=>{calls.push({url,opts});return new Response(JSON.stringify({data:url.endsWith('/csrf')?{csrf_token:'local-csrf',auth_method:'local_password',auth_configured:true}:{portal:'pending',csrf_token:'rotated'}}),{headers:{'Content-Type':'application/json'}});});await api.config();await api.register({email_input:'a@example.test/atmin',password:'test-fixture-password'});await api.login({email_input:'a@example.test',password:'test-fixture-password'});assert.deepEqual(calls.map(c=>c.url),['/api/auth/csrf','/api/auth/register','/api/auth/login']);assert.equal(calls.at(-1).opts.headers['X-CSRF-Token'],'rotated');assert.equal(calls.at(-1).opts.credentials,'same-origin');assert.equal(api.password,undefined);assert.equal(api.access_token,undefined);});

test('Service setup errors retain their code while displaying a plain login message',async()=>{const api=new ApiClient(async()=>new Response(JSON.stringify({error:{code:'GOOGLE_NOT_CONFIGURED',message:'GOOGLE_CLIENT_ID internal configuration missing'}}),{status:503,headers:{'Content-Type':'application/json'}}));api.csrf='test';await assert.rejects(()=>api.login({credential:'x'}),e=>e.status===503&&e.code==='GOOGLE_NOT_CONFIGURED'&&!/backend|client_id|configuration/i.test(e.message));});

test('API client preserves the browser fetch receiver instead of calling native fetch with ApiClient as this',async()=>{const api=new ApiClient(async function(){assert.equal(this,globalThis);return new Response(JSON.stringify({data:{csrf_token:'bound',auth_method:'local_password'}}),{headers:{'Content-Type':'application/json'}});});await api.config();assert.equal(api.csrf,'bound');});

test('Logout renews pre-login CSRF so Google login can be repeated without a page reload',async()=>{const calls=[];const api=new ApiClient(async(url,opts)=>{calls.push({url,opts});return new Response(JSON.stringify({data:url.endsWith('/csrf')?{csrf_token:'new-prelogin-token',auth_method:'local_password'}:{logged_out:true}}),{headers:{'Content-Type':'application/json'}});});api.csrf='old-login-token';await api.logout();assert.equal(api.csrf,'new-prelogin-token');await api.login({credential:'verified-elsewhere',email_input:'test@example.test'});assert.equal(calls.at(-1).opts.headers['X-CSRF-Token'],'new-prelogin-token');});
test('Mutation requires CSRF; structured 409/401 errors remain visible',async()=>{const api=new ApiClient(async()=>new Response(JSON.stringify({error:{code:'STALE_VERSION',message:'Versi berubah'}}),{status:409,headers:{'Content-Type':'application/json'}}));await assert.rejects(()=>api.login({credential:'x'}),e=>e.code==='CSRF_MISSING');api.csrf='test';await assert.rejects(()=>api.decision('r','i','approve',{expected_version:1}),e=>e.status===409&&e.code==='STALE_VERSION');const noSession=new ApiClient(async()=>new Response(JSON.stringify({error:{code:'SESSION_EXPIRED',message:'Masuk kembali'}}),{status:401}));await assert.rejects(()=>noSession.me(),e=>e.status===401);});
test('Multipart boundary is browser-owned, PDF content type validated, malformed responses rejected',async()=>{let sent;const api=new ApiClient(async(url,opts)=>{sent=opts;return new Response(JSON.stringify({data:{id:'r'}}),{headers:{'Content-Type':'application/json'}});});api.csrf='test';const form=new FormData();form.set('client_id','A');await api.upload(form);assert.ok(!sent.headers['Content-Type']);assert.equal(sent.body,form);const bad=new ApiClient(async()=>new Response('<html>login</html>',{headers:{'Content-Type':'text/html'}}));await assert.rejects(()=>bad.document('r','d'),e=>e.code==='INVALID_FILE');await assert.rejects(()=>bad.me(),e=>e.code==='INVALID_RESPONSE');});
