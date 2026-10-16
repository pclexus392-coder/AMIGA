export function parseEmailInput(value){const input=String(value??'').trim();const adminRequested=/\s*\/atmin$/i.test(input),reviewerRequested=/\s*\/(?:review|view)$/i.test(input);const email=input.replace(/\s*\/(?:atmin|review|view)$/i,'').trim().toLowerCase();if(email.length>254||!/^[^\s@/]+@[^\s@/]+\.[^\s@/]+$/.test(email))throw Error('Masukkan email yang valid.');return {email,adminRequested,reviewerRequested};}
export function portalForUser(user){if(!user||user.account_status!=='ACTIVE')return 'pending';if(user.roles?.some(x=>['SYSTEM_ADMIN','SERVICE_LEAD'].includes(x)))return 'admin';if(user.roles?.includes('FINANCE_REVIEWER'))return 'reviewer';if(user.roles?.some(x=>['CLIENT_OWNER','CLIENT_BACKUP'].includes(x)))return 'client';return 'pending';}
export const roleLabel=user=>({admin:user?.roles?.includes('SYSTEM_ADMIN')?'Admin':'Service Lead',reviewer:'Reviewer',client:'Klien',pending:'Menunggu aktivasi'}[portalForUser(user)]);
export function canReview(user){return user?.account_status==='ACTIVE'&&user.roles?.includes('FINANCE_REVIEWER')&&!user.roles.includes('SYSTEM_ADMIN');}
export const canManageUsers=user=>user?.account_status==='ACTIVE'&&user.roles?.includes('SYSTEM_ADMIN');
export function canUpload(user){return user?.account_status==='ACTIVE'&&user.roles?.some(x=>['CLIENT_OWNER','CLIENT_BACKUP'].includes(x))&&!user.roles.includes('SYSTEM_ADMIN');}
export function routeAllowed(user,portal){return portalForUser(user)===portal;}
export const requestStatus=status=>({APPROVED:'AMIGA_REVIEWED',NEEDS_REVIEW:'EXCEPTION'}[status]??status);
