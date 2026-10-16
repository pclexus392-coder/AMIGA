"""Account linking + immutable review preview + explicit, idempotent dispatch."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json,re,secrets
from sqlalchemy import select,delete,update,text
from ...api_common import (api,g,current_app,body,ok,fail,request,scoped_request,scoped_invoice,
    require_review,roles,client_ids,CLIENT_ROLES,authenticate,latest_review,fields_for,audit,uid,now,reason)
from ...models import TelegramLink,TelegramChallenge,TelegramDelivery,AgentTurn,User,Setting,Voucher
from ...workflow import input_hash
from ...telegram_service import telegram_call,TelegramError


def expires(minutes):
    return (datetime.now(timezone.utc)+timedelta(minutes=minutes)).isoformat(timespec='microseconds').replace('+00:00','Z')


def private_link():
    if not roles(g.db,g.actor)&CLIENT_ROLES:fail(403,'UPLOADER_REQUIRED','Telegram dihubungkan pada akun uploader/klien.')


def status():
    row=g.db.get(TelegramLink,g.actor.id)
    return {'configured':bool(current_app.config['TELEGRAM_BOT_TOKEN']),'connected':bool(row),
            'username':row.username if row else None,'verified_at':row.verified_at if row else None}


@api.get('/telegram/status')
def telegram_status():return ok(status())


@api.post('/telegram/link')
def telegram_link():
    private_link()
    if not current_app.config['TELEGRAM_BOT_TOKEN']:fail(503,'TELEGRAM_NOT_CONFIGURED','Telegram belum diaktifkan pengelola. Akun tetap dapat digunakan.')
    username=current_app.config['TELEGRAM_BOT_USERNAME']
    if not username:
        g.db.commit()
        try:username=telegram_call('getMe',{},current_app.config)['username']
        except (TelegramError,KeyError):fail(502,'TELEGRAM_UNAVAILABLE','Bot belum dapat dihubungi.')
        authenticate();private_link()
    if not re.fullmatch(r'[A-Za-z0-9_]{5,32}',username):fail(503,'TELEGRAM_NOT_CONFIGURED','Nama bot belum valid.')
    token='amiga_'+secrets.token_urlsafe(32)
    g.db.execute(delete(TelegramChallenge).where(TelegramChallenge.user_id==g.actor.id))
    g.db.add(TelegramChallenge(user_id=g.actor.id,token_hash=sha256(token.encode()).hexdigest(),expires_at=expires(15)))
    return ok({'url':'https://t.me/'+username+'?start='+token,'expires_in_seconds':900})


@api.post('/telegram/verify')
def telegram_verify():
    private_link()
    pending=g.db.get(TelegramChallenge,g.actor.id)
    if not pending or pending.expires_at<=now():fail(409,'LINK_EXPIRED','Buat tautan baru, buka bot dan tekan Start.')
    cursor=g.db.get(Setting,'telegram_update_offset');offset=int(cursor.value) if cursor else 0
    g.db.commit()
    try:updates=telegram_call('getUpdates',{'offset':offset,'limit':100,'timeout':0,'allowed_updates':['message']},current_app.config)
    except TelegramError:fail(502,'TELEGRAM_UNAVAILABLE','Telegram belum dapat diperiksa. Jika bot memakai webhook, gunakan bot khusus AMIGA tanpa webhook.')
    if not isinstance(updates,list):fail(502,'TELEGRAM_UNAVAILABLE','Respons bot belum valid.')
    g.db.rollback()
    if g.db.bind.dialect.name=='sqlite':g.db.execute(text('BEGIN IMMEDIATE'))
    authenticate();private_link()
    for event in updates:
        message=event.get('message',{});chat=message.get('chat',{});sender=message.get('from',{})
        text_value=message.get('text','')
        if (chat.get('type')!='private' or str(chat.get('id'))!=str(sender.get('id')) or sender.get('is_bot')
            or not isinstance(text_value,str)):continue
        match=re.fullmatch(r'/start(?:@\w+)?\s+(amiga_[A-Za-z0-9_-]{43})',text_value.strip())
        if not match:continue
        challenge=g.db.scalar(select(TelegramChallenge).where(TelegramChallenge.token_hash==sha256(match.group(1).encode()).hexdigest(),TelegramChallenge.expires_at>now()).with_for_update())
        if not challenge:continue
        user=g.db.get(User,challenge.user_id)
        if not user or user.account_status!='ACTIVE' or not roles(g.db,user)&CLIENT_ROLES:continue
        chat_id=str(chat['id'])
        if not re.fullmatch(r'[1-9][0-9]{0,19}',chat_id):continue
        occupied=g.db.scalar(select(TelegramLink).where(TelegramLink.chat_id==chat_id,TelegramLink.user_id!=user.id))
        if occupied:continue
        row=g.db.get(TelegramLink,user.id)
        if not row:row=TelegramLink(user_id=user.id);g.db.add(row)
        row.chat_id,row.username,row.verified_at=chat_id,str(sender.get('username') or '')[:200] or None,now()
        g.db.delete(challenge)
        audit(g.db,'TELEGRAM_LINKED',user.id,reason='Private-chat challenge verified')
    if updates:
        new=max([offset]+[int(e.get('update_id',-1))+1 for e in updates])
        cursor=g.db.scalar(select(Setting).where(Setting.key=='telegram_update_offset').with_for_update())
        if cursor:cursor.value=str(max(int(cursor.value),new))
        else:g.db.add(Setting(key='telegram_update_offset',value=str(new)))
    g.db.flush()
    return ok(status())


@api.delete('/telegram/link')
def telegram_unlink():
    g.db.execute(delete(TelegramLink).where(TelegramLink.user_id==g.actor.id))
    g.db.execute(delete(TelegramChallenge).where(TelegramChallenge.user_id==g.actor.id))
    audit(g.db,'TELEGRAM_UNLINKED',g.actor.id)
    return ok(status())


def fingerprint(req,inv,link,body_text,voucher_id):
    review=latest_review(g.db,inv)
    value={'input':input_hash(g.db,req,inv),'pic':req.pic_id,'recipient':link.user_id,
        'chat_id':link.chat_id,'linked_at':link.verified_at,'review':review.id if review else None,
        'message':body_text,'voucher_id':voucher_id}
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def delivery_dto(row):
    user=g.db.get(User,row.recipient_id)
    return {'id':row.id,'request_id':row.request_id,'invoice_id':row.invoice_id,'version':row.version,
            'recipient_name':user.display_name,'body':row.body,'has_voucher':bool(row.voucher_id),
            'preview_hash':row.fingerprint,'state':row.state,'expires_at':row.expires_at,
            'created_at':row.created_at,'sent_at':row.sent_at,'error_code':row.error_code}


@api.get('/requests/<request_id>/telegram-deliveries')
def telegram_deliveries(request_id):
    req=scoped_request(request_id);require_review(req)
    rows=g.db.scalars(select(TelegramDelivery).where(TelegramDelivery.request_id==req.id,TelegramDelivery.sender_id==g.actor.id).order_by(TelegramDelivery.created_at.desc()).limit(20))
    return ok({'items':[delivery_dto(r) for r in rows]})


@api.post('/requests/<request_id>/invoices/<invoice_id>/telegram-preview')
def telegram_preview(request_id,invoice_id):
    data=body();req=scoped_request(request_id,True);inv=scoped_invoice(req,invoice_id,data.get('expected_version',-1));require_review(req)
    link=g.db.get(TelegramLink,req.uploaded_by)
    if not current_app.config['TELEGRAM_BOT_TOKEN'] or not link:
        fail(409,'TELEGRAM_UNAVAILABLE_FOR_UPLOADER','Telegram uploader belum terhubung. Hasil review tetap tersedia di AMIGA.')
    turn=g.db.get(AgentTurn,data.get('turn_id')) if isinstance(data.get('turn_id'),str) else None
    if not turn or turn.user_id!=g.actor.id or turn.role!='reviewer' or turn.request_id!=req.id or turn.state!='DONE':
        fail(422,'CONVERSATION_REQUIRED','Tanyakan ringkasan hasil pada asisten reviewer untuk Request ID ini terlebih dahulu.')
    from ..agents.routes import context_for,digest
    if turn.request_hash!=digest(context_for(req.id)['selected_request']):
        fail(409,'AGENT_CONTEXT_CHANGED','Hasil review berubah sejak percakapan ini. Minta ringkasan AI terbaru sebelum membuat pratinjau.')
    message=data.get('message')
    review=latest_review(g.db,inv)
    fields=fields_for(g.db,inv)
    if message is None:
        label='Voucher resmi terbit' if review and review.decision=='APPROVED' else 'Perlu perbaikan' if review and review.decision=='REJECTED' else 'Ringkasan pemeriksaan draft'
        prefix=f"AMIGA · {label}\nRequest ID: {req.id}\nInvoice: {fields['invoice_number'] or '-'} · versi {inv.current_version}\n\n"
        message=prefix+turn.result['answer'][:max(0,1000-len(prefix))]
    if not isinstance(message,str) or not 1<=len(message.strip())<=1000:fail(422,'MESSAGE_LIMIT','Pesan Telegram harus 1–1000 karakter.')
    voucher=None
    if data.get('include_voucher') is True:
        voucher=g.db.scalar(select(Voucher).where(Voucher.invoice_id==inv.id,Voucher.version==inv.current_version))
        if not voucher or not review or review.decision!='APPROVED':fail(409,'OFFICIAL_VOUCHER_REQUIRED','Lampiran hanya boleh voucher resmi versi aktif yang sudah disetujui.')
    fp=fingerprint(req,inv,link,message.strip(),voucher.id if voucher else None)
    prior=g.db.scalar(select(TelegramDelivery).where(TelegramDelivery.fingerprint==fp,TelegramDelivery.state.in_(['SENDING','SENT','UNKNOWN'])).limit(1))
    if prior:fail(409,'TELEGRAM_ALREADY_DISPATCHED','Pesan yang sama sudah dikirim atau status pengirimannya perlu diperiksa; pengiriman tidak diulang otomatis.')
    g.db.execute(update(TelegramDelivery).where(TelegramDelivery.sender_id==g.actor.id,TelegramDelivery.request_id==req.id,TelegramDelivery.state=='DRAFT').values(state='CANCELLED'))
    row=TelegramDelivery(id=uid('tele'),request_id=req.id,invoice_id=inv.id,version=inv.current_version,
        sender_id=g.actor.id,recipient_id=link.user_id,chat_id=link.chat_id,body=message.strip(),
        voucher_id=voucher.id if voucher else None,fingerprint=fp,state='DRAFT',expires_at=expires(15))
    g.db.add(row);g.db.flush()
    audit(g.db,'TELEGRAM_PREVIEWED',g.actor.id,req.id,inv.id)
    return ok(delivery_dto(row),201)


@api.post('/telegram/previews/<preview_id>/send')
def telegram_send(preview_id):
    data=body()
    row=g.db.scalar(select(TelegramDelivery).where(TelegramDelivery.id==preview_id,TelegramDelivery.sender_id==g.actor.id))
    if not row:fail(404,'NOT_FOUND','Pratinjau tidak ditemukan.')
    req=scoped_request(row.request_id,True)
    g.db.refresh(row,with_for_update=True)
    inv=scoped_invoice(req,row.invoice_id,row.version);require_review(req)
    if row.state=='SENT':return ok(delivery_dto(row))
    if row.state!='DRAFT':fail(409,'TELEGRAM_STATE','Pengiriman tidak dapat diulang otomatis. Periksa status pesan terlebih dahulu.')
    if data.get('approved') is not True or data.get('preview_hash')!=row.fingerprint:
        fail(422,'SEND_APPROVAL_REQUIRED','Setujui penerima, versi, pesan dan lampiran pada pratinjau ini.')
    link=g.db.get(TelegramLink,row.recipient_id)
    if row.expires_at<=now() or not link or fingerprint(req,inv,link,row.body,row.voucher_id)!=row.fingerprint:
        fail(409,'TELEGRAM_PREVIEW_STALE','Data atau penerima berubah. Buat dan setujui pratinjau baru.')
    recipient=g.db.get(User,row.recipient_id)
    if recipient.account_status!='ACTIVE' or not roles(g.db,recipient)&CLIENT_ROLES or req.client_id not in client_ids(g.db,recipient):
        fail(409,'RECIPIENT_INACTIVE','Penerima tidak lagi mempunyai akses klien ini.')
    voucher=g.db.get(Voucher,row.voucher_id) if row.voucher_id else None
    pdf=bytes(voucher.pdf) if voucher else None
    payload={'chat_id':row.chat_id,'caption' if pdf else 'text':row.body}
    row.state='SENDING';g.db.commit()
    try:
        result=telegram_call('sendDocument' if pdf else 'sendMessage',payload,current_app.config,pdf)
        message_id=result.get('message_id') if isinstance(result,dict) else None
        if type(message_id) is not int:raise TelegramError('TELEGRAM_UNCERTAIN',True)
        state,error='SENT',None
    except TelegramError as exc:state,error='UNKNOWN' if exc.uncertain else 'FAILED',exc.code
    except Exception:state,error='UNKNOWN','TELEGRAM_UNCERTAIN'
    row=g.db.get(TelegramDelivery,preview_id);row.state,row.error_code=state,error
    if state=='SENT':row.sent_at,row.message_id=now(),str(message_id)
    audit(g.db,'TELEGRAM_'+state,row.sender_id,row.request_id,row.invoice_id,reason=error,
          changes=[{'field':'delivery_id','before':None,'after':row.id}])
    g.db.commit()
    return ok(delivery_dto(row))
