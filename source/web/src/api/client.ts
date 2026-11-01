const envBase=import.meta.env.VITE_API_BASE_URL?.replace(/\/$/,'');
export type Service='auth'|'content'|'audio';
const prefix:Record<Service,string>={auth:'/api/auth',content:'/api/content',audio:'/api/audio'};
export class ApiError extends Error {status:number; code?:string; constructor(message:string,status:number,code?:string){super(message);this.status=status;this.code=code;}}
export async function request<T=any>(service:Service,path:string,opts:RequestInit={},token?:string):Promise<T>{
 const base=envBase ? `${envBase.replace(/\/$/,'')}${prefix[service]}` : prefix[service];
 const headers=new Headers(opts.headers); if(opts.body && !headers.has('Content-Type')) headers.set('Content-Type','application/json'); if(token) headers.set('Authorization',`Bearer ${token}`);
 let res:Response; try{res=await fetch(`${base}${path}`,{...opts,headers});}catch{throw new ApiError('Không thể kết nối máy chủ. Hãy kiểm tra backend và kết nối mạng.',0);}
 if(!res.ok){let data:any={};try{data=await res.json()}catch{} const d=data?.detail; const msg=typeof d==='string'?d:(d?.message||data?.message||`Yêu cầu thất bại (${res.status})`); throw new ApiError(msg,res.status,d?.error||data?.error);}
 if(res.status===204) return undefined as T; const type=res.headers.get('content-type')||''; return (type.includes('json')?await res.json():await res.blob()) as T;
}
export const authApi={login:(body:any)=>request('auth','/login',{method:'POST',body:JSON.stringify(body)}),tickets:(token:string)=>request('auth','/tickets/today',{},token),createTicket:(token:string)=>request('auth','/tickets',{method:'POST'},token),activate:(body:any)=>request('auth','/tickets/activate',{method:'POST',body:JSON.stringify(body)}),meTicket:(token:string)=>request('auth','/tickets/me',{},token),users:(token:string)=>request('auth','/users',{},token),createUser:(body:any,token:string)=>request('auth','/users',{method:'POST',body:JSON.stringify(body)},token),userStatus:(id:string,body:any,token:string)=>request('auth',`/users/${id}/status`,{method:'PATCH',body:JSON.stringify(body)},token)};
export const contentApi={pois:()=>request('content','/pois'),poi:(id:string)=>request('content',`/pois/${encodeURIComponent(id)}`),nearby:(lat:number,lon:number,r:number)=>request('content',`/pois/nearby?lat=${lat}&lon=${lon}&search_radius_m=${r}`),createPoi:(body:any,t:string)=>request('content','/pois',{method:'POST',body:JSON.stringify(body)},t),updatePoi:(id:string,body:any,t:string)=>request('content',`/pois/${id}`,{method:'PUT',body:JSON.stringify(body)},t),patchTranslation:(id:string,lang:string,body:any,t:string)=>request('content',`/pois/${id}/translations/${lang}`,{method:'PATCH',body:JSON.stringify(body)},t),deletePoi:(id:string,t:string)=>request('content',`/pois/${id}`,{method:'DELETE'},t),dashboard:(t:string)=>request('content','/stats/dashboard',{},t), events:(t:string)=>request('content','/events?limit=20',{},t),
  sendEvent:(body:{poi_id:string;type:string;lat?:number;lon?:number},t:string)=>
    request('content','/events',{method:'POST',body:JSON.stringify(body)},t)
};
export const audioApi={visitor:(id:string,lang:string,t:string)=>request<Blob>('audio',`/audio/poi/${id}?lang=${lang}`,{},t),preview:(id:string,lang:string,t:string)=>request<Blob>('audio',`/audio/preview/${id}?lang=${lang}`,{},t),status:(id:string,t:string)=>request('audio',`/audio/status/${id}`,{},t)};
