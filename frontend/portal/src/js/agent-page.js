import {workLabels} from './work-progress.js';
const label={admin:'Asisten admin',reviewer:'Asisten reviewer',uploader:'Asisten uploader'};
const stamp=value=>new Date(value).toLocaleString('id-ID',{timeZone:'Asia/Jakarta'});

export async function agentPage({api,session,requestId='',invoiceId='',escape,shell,pageTitle,navigate,run,toast,isCurrent,root=document}){
  if(api.mode!=='live'){shell(pageTitle('Asisten AI','Tersedia pada aplikasi AMIGA dengan akun aktif.')+'<div class="callout">Pratinjau ini tidak memanggil AI.</div>','agent');return;}
  shell(pageTitle(label[session.portal==='client'?'uploader':session.portal],'Menyiapkan konteks pekerjaan…')+'<div class="callout" role="status">Memuat data sesuai akses akunmu…</div>','agent');
  const [context,history]=await Promise.all([api.agentOverview(requestId),api.agentHistory(requestId)]);
  if(!isCurrent())return;
  const role=context.role,selected=context.selected_request;
  let lastTurn=history.items.at(-1)?.id??'',preview=null;
  const urgent=context.urgent.map(r=>`<tr><td><code>${escape(r.request_id)}</code><small>${escape(r.client_name)}</small></td><td>${escape(r.pic_name||'Belum diambil')}</td><td>${escape(r.deadline)}</td><td>${r.reasons.map(s=>escape(s)).join('<br>')}</td></tr>`).join('');
  const metrics=context.performance;
  const performance=metrics?`<section class="panel"><div class="panel-head"><h2>Progres & hasil reviewer</h2><span class="tiny-tag">${metrics.days} hari</span></div><div class="panel-body"><p>${escape(metrics.definition)}</p><div class="table-scroll"><table><thead><tr><th>Reviewer</th><th>Tugas diambil</th><th>Selesai</th><th>Masih dikerjakan</th><th>Diterima tanpa revisi</th><th>Persentase</th></tr></thead><tbody>${metrics.reviewers.map(r=>`<tr><td>${escape(r.name)}<small>${r.active?'Aktif':'Nonaktif'}</small></td><td>${r.taken}</td><td>${r.completed}</td><td>${r.in_progress}</td><td>${r.accepted_without_revision} / ${r.accepted} diterima</td><td>${r.first_pass_rate===null?'Belum ada sampel':r.first_pass_rate+'%'}</td></tr>`).join('')||'<tr><td colspan="6">Belum ada reviewer.</td></tr>'}</tbody></table></div><p class="subtle">Jumlah tugas bukan penilaian tunggal kualitas reviewer. Pekerjaan selesai berarti seluruh invoice aktif sudah disetujui; hasil diterima dicatat saat klien menutup pekerjaan.</p></div></section>`:'';
  const selectedInfo=selected?`<div class="callout"><strong>${escape(workLabels[selected.work_status]??selected.work_status)}</strong><p>Request ID: <code>${escape(selected.id)}</code><br>Penanggung jawab: ${escape(selected.pic_name||'Belum diambil')} · Tenggat ${escape(selected.deadline)}</p><button id="agent-open-request" class="small">Buka dokumen</button></div>`:'';
  const turnHTML=turn=>`<article class="agent-exchange"><p class="agent-question"><strong>Kamu</strong><br>${escape(turn.question)}</p><div class="agent-answer"><strong>${escape(label[role])}</strong><p>${escape(turn.result.answer)}</p>${turn.result.next_steps.length?`<ol>${turn.result.next_steps.map(s=>`<li>${escape(s)}</li>`).join('')}</ol>`:''}<small class="subtle">${escape(stamp(turn.created_at))}</small></div></article>`;
  shell(pageTitle(label[role],'Bantuan Luna berdasarkan peran dan data pekerjaan yang boleh kamu akses.')+`
    <section class="panel"><div class="panel-body"><form id="agent-context-form" class="agent-context-form"><div><label for="agent-request-id">Tracking berdasarkan Request ID (opsional)</label><input id="agent-request-id" value="${escape(requestId)}" maxlength="80" placeholder="Tempel req_… dari dokumen"></div><button type="submit">Buka konteks</button><button id="agent-global" type="button">Ringkasan pekerjaan</button></form>${selectedInfo}</div></section>
    <section class="panel"><div class="panel-head"><h2>Perlu didahulukan</h2><span class="tiny-tag">Dari tenggat & kendala</span></div><div class="panel-body">${context.truncated?'<p class="callout warn">Ringkasan dibatasi pada pekerjaan yang dimuat. Gunakan papan tugas untuk daftar lengkap.</p>':''}<div class="table-scroll"><table><thead><tr><th>Request / klien</th><th>Penanggung jawab</th><th>Tenggat</th><th>Alasan prioritas</th></tr></thead><tbody>${urgent||'<tr><td colspan="4">Tidak ada pekerjaan mendesak pada data yang dimuat.</td></tr>'}</tbody></table></div>${role==='reviewer'?'<p class="subtle">Ringkasan tugas tersedia dapat dilihat bersama. Ambil tugas di papan reviewer untuk membuka detail dan PDF.</p>':''}</div></section>
    ${performance}
    <section class="panel"><div class="panel-head"><h2>Percakapan pekerjaan</h2><span class="tiny-tag">Luna</span></div><div class="panel-body"><p class="subtle">Tanyakan invoice, voucher, progres atau langkah pemeriksaan. Data status ditampilkan dari sistem; AI membantu menjelaskannya. Pengiriman Telegram selalu meminta persetujuan terpisah.</p><div id="agent-messages" aria-live="polite">${history.items.map(turnHTML).join('')||'<p class="subtle agent-empty">Belum ada percakapan untuk konteks ini.</p>'}</div><form id="agent-chat-form"><label for="agent-question">Pertanyaan</label><textarea id="agent-question" required maxlength="1000" placeholder="${role==='admin'?'Pekerjaan apa yang paling mendesak dan bagaimana beban reviewer?':role==='reviewer'?'Ringkaskan hasil pemeriksaan yang perlu disampaikan ke uploader.':'Request ini sudah sampai mana, dan apa yang perlu saya perbaiki?'}"></textarea><button type="submit" class="primary" id="agent-send">Tanya asisten</button></form></div></section>
    ${role==='uploader'?'<section class="panel"><div class="panel-body" id="telegram-settings"><h2>Telegram (opsional)</h2><p>Tanpa Telegram, login, unggahan dan hasil review tetap tersedia di AMIGA.</p><div id="telegram-account-status">Memuat status…</div><div id="telegram-link-target"></div><div class="actions"><button id="telegram-connect">Hubungkan Telegram</button><button id="telegram-verify" hidden>Saya sudah menekan Start, periksa koneksi</button><button id="telegram-disconnect" hidden>Putuskan koneksi</button></div></div></section>':''}
    ${role==='reviewer'&&selected?`<section class="panel"><div class="panel-head"><h2>Kirim hasil ke Telegram uploader</h2><span class="tiny-tag">Opsional</span></div><div class="panel-body">${!selected.telegram.available?'<div class="callout warn">Telegram uploader belum terhubung atau bot belum aktif. Reviewer belum bisa mengirim Telegram; hasil tetap tersedia di AMIGA.</div>':`<p>Ringkasan percakapan akan menjadi draf pesan. Periksa penerima, isi dan lampiran sebelum menyetujui pengiriman.</p><label for="telegram-invoice">Invoice yang dibahas</label><select id="telegram-invoice">${selected.invoices.map(i=>`<option value="${escape(i.id)}" ${i.id===invoiceId?'selected':''}>${escape(i.fields.invoice_number||'Tanpa nomor')} · versi ${i.current_version}</option>`).join('')}</select><label class="checkbox"><input id="telegram-attach" type="checkbox">Lampirkan voucher resmi versi aktif (jika sudah terbit)</label><button id="telegram-prepare" ${lastTurn?'':'disabled'}>Buat pratinjau pesan</button><p class="subtle">Jika belum ada percakapan, tanyakan ringkasan hasil pemeriksaan terlebih dahulu.</p><div id="telegram-preview"></div>`}<div id="telegram-receipts"></div></div></section>`:''}
  `,'agent');
  root.querySelector('#agent-context-form').onsubmit=e=>{e.preventDefault();navigate('agent',root.querySelector('#agent-request-id').value.trim());};
  root.querySelector('#agent-global').onclick=()=>navigate('agent');
  root.querySelector('#agent-open-request')?.addEventListener('click',()=>navigate('review',requestId,invoiceId));
  root.querySelector('#agent-chat-form').onsubmit=e=>{
    e.preventDefault();const input=root.querySelector('#agent-question'),question=input.value.trim();if(!question)return;
    run(async()=>{const result=await api.agentChat({question,request_id:requestId||undefined});if(!isCurrent())return;
      lastTurn=result.id;root.querySelector('.agent-empty')?.remove();root.querySelector('#agent-messages').insertAdjacentHTML('beforeend',turnHTML({question,result:result.result,created_at:new Date().toISOString()}));
      input.value='';const prepare=root.querySelector('#telegram-prepare');if(prepare)prepare.disabled=false;
      root.querySelector('#agent-messages').lastElementChild?.scrollIntoView({block:'nearest'});
    },false);
  };
  if(role==='uploader'){
    async function loadStatus(){
      const state=await api.telegramStatus();if(!isCurrent())return;
      root.querySelector('#telegram-account-status').textContent=state.connected?'Telegram terhubung'+(state.username?' sebagai @'+state.username:'')+'.':state.configured?'Belum terhubung. Hubungkan hanya jika ingin menerima pesan reviewer.':'Bot belum diaktifkan pengelola. Kamu tetap dapat menggunakan AMIGA.';
      root.querySelector('#telegram-connect').disabled=!state.configured;
      root.querySelector('#telegram-disconnect').hidden=!state.connected;
    }
    await loadStatus();if(!isCurrent())return;
    root.querySelector('#telegram-connect').onclick=()=>run(async()=>{const result=await api.telegramLink();if(!isCurrent())return;const a=document.createElement('a');a.href=result.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Buka bot Telegram dan tekan Start';root.querySelector('#telegram-link-target').replaceChildren(a);root.querySelector('#telegram-verify').hidden=false;},false);
    root.querySelector('#telegram-verify').onclick=()=>run(async()=>{const result=await api.telegramVerify();await loadStatus();toast(result.connected?'Telegram berhasil dihubungkan.':'Pesan Start belum ditemukan. Buka tautan bot lalu coba periksa lagi.');},false);
    root.querySelector('#telegram-disconnect').onclick=()=>run(async()=>{await api.telegramUnlink();await loadStatus();root.querySelector('#telegram-link-target').replaceChildren();root.querySelector('#telegram-verify').hidden=true;},false);
  }
  async function refreshReceipts(){
    const target=root.querySelector('#telegram-receipts');if(!target)return;
    const rows=await api.telegramDeliveries(requestId);if(!isCurrent())return;
    const names={DRAFT:'Pratinjau belum dikirim',CANCELLED:'Pratinjau diganti',SENDING:'Sedang dikirim / perlu diperiksa',SENT:'Terkirim',FAILED:'Gagal',UNKNOWN:'Status belum pasti — periksa Telegram'};
    target.innerHTML='<h3>Riwayat pengiriman</h3>'+rows.items.map(r=>`<p>${escape(names[r.state]??r.state)} · versi ${r.version} · ${escape(stamp(r.sent_at||r.created_at))}</p>`).join('');
  }
  if(role==='reviewer'&&selected)await refreshReceipts();
  if(!isCurrent())return;
  const prepare=root.querySelector('#telegram-prepare');
  if(prepare){
    const chosen=()=>selected.invoices.find(i=>i.id===root.querySelector('#telegram-invoice').value);
    const attach=root.querySelector('#telegram-attach');
    function changeInvoice(){attach.checked=false;attach.disabled=chosen()?.review_status!=='APPROVED';preview=null;root.querySelector('#telegram-preview').replaceChildren();}
    root.querySelector('#telegram-invoice').onchange=changeInvoice;attach.onchange=()=>{preview=null;root.querySelector('#telegram-preview').replaceChildren();};changeInvoice();
    async function makePreview(message){
      const inv=chosen();const row=await api.telegramPreview(requestId,inv.id,{expected_version:inv.current_version,turn_id:lastTurn,include_voucher:attach.checked,...(message!==undefined?{message}:{})});
      if(!isCurrent())return;preview=row;
      const target=root.querySelector('#telegram-preview');target.innerHTML=`<div class="telegram-consent"><h3>Pratinjau sebelum dikirim</h3><p>Penerima: <strong>${escape(row.recipient_name)}</strong><br>Request ID: <code>${escape(row.request_id)}</code><br>Versi invoice: ${row.version} · Lampiran: ${row.has_voucher?'voucher resmi':'tanpa lampiran'}</p><label for="telegram-message">Isi pesan yang akan dikirim</label><textarea id="telegram-message" maxlength="1000">${escape(row.body)}</textarea><button id="telegram-refresh-preview">Perbarui pratinjau setelah edit</button><label class="checkbox"><input id="telegram-consent" type="checkbox">Saya menyetujui penerima, versi hasil, isi pesan dan lampiran di atas untuk dikirim.</label><button id="telegram-dispatch" class="primary" disabled>Setujui & kirim ke Telegram</button><div id="telegram-delivery-status" role="status"></div></div>`;
      const consent=root.querySelector('#telegram-consent'),send=root.querySelector('#telegram-dispatch');
      root.querySelector('#telegram-message').oninput=()=>{preview=null;consent.checked=false;consent.disabled=true;send.disabled=true;};
      root.querySelector('#telegram-refresh-preview').onclick=()=>run(()=>makePreview(root.querySelector('#telegram-message').value),false);
      consent.onchange=()=>{send.disabled=!consent.checked||!preview;};
      send.onclick=()=>{if(!consent.checked||!preview)return;const approved=preview;run(async()=>{const result=await api.telegramSend(approved.id,approved.preview_hash);if(!isCurrent())return;preview=null;send.disabled=true;consent.disabled=true;root.querySelector('#telegram-message').disabled=true;
        await refreshReceipts();if(!isCurrent())return;root.querySelector('#telegram-delivery-status').textContent=result.state==='SENT'?'Pesan berhasil dikirim dan tercatat dalam riwayat.':result.state==='UNKNOWN'?'Status kirim belum dapat dipastikan. Periksa Telegram; pesan tidak dikirim ulang otomatis.':'Pesan belum terkirim. Periksa koneksi dan buat pratinjau baru sebelum mencoba kembali.';
      },false);};
    }
    prepare.onclick=()=>run(()=>makePreview(),false);
  }
}
