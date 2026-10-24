import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Routes,Route,Link,useNavigate,useParams,useSearchParams,Navigate} from 'react-router-dom';
import {MapContainer,TileLayer,Marker,Popup,Circle,useMapEvents} from 'react-leaflet';
import L from 'leaflet'; import {QRCodeSVG} from 'qrcode.react'; import {BarChart,Bar,LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer,Legend} from 'recharts';
import {Leaf,Ticket,MapPin,Search,LocateFixed,Headphones,LockKeyhole,LogOut,LayoutDashboard,PawPrint,Users,Plus,RefreshCw,Trash2,Edit3,Copy,CheckCircle,AlertCircle,Menu,Volume2} from 'lucide-react';
import {authApi,contentApi,audioApi,ApiError} from './api/client'; import {languages,labels,Lang} from './i18n';
type POI={id:string;name?:string;lat:number;lon:number;radius_m?:number;category:string;species_name?:string;image_url?:string;translations?:Record<string,{name?:string;description?:string}>;description?:string;distance_m?:number};
const cats=[['','Tất cả'],['thu_an_thit','Thú ăn thịt'],['thu_an_co','Thú ăn cỏ'],['chim','Chim'],['bo_sat_luong_cu','Bò sát & lưỡng cư'],['linh_truong','Linh trưởng'],['tien_ich','Tiện ích']];
const TILE=import.meta.env.VITE_TILE_URL||'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
function deviceId(){let id=localStorage.getItem('zoo_device_id');if(!id){id=crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`;localStorage.setItem('zoo_device_id',id)}return id}
function useTicket(){const [token,setToken]=useState(localStorage.getItem('ticket_token')||'');const [expiry,setExpiry]=useState(localStorage.getItem('ticket_expires_at')||'');const clear=useCallback(()=>{localStorage.removeItem('ticket_token');localStorage.removeItem('ticket_expires_at');setToken('');setExpiry('')},[]);const valid=!!token&&(!expiry||new Date(expiry).getTime()>Date.now());useEffect(()=>{if(token&&!valid)clear()},[token,valid,clear]);const save=(t:string,e?:string)=>{localStorage.setItem('ticket_token',t);if(e)localStorage.setItem('ticket_expires_at',e);setToken(t);setExpiry(e||'')};return {token,expiry,valid,clear,save};}
function useStaff(){const [token,setToken]=useState(sessionStorage.getItem('staff_token')||'');const [user,setUser]=useState<any>(()=>{try{return JSON.parse(sessionStorage.getItem('staff_user')||'null')}catch{return null}});const login=(t:string,u:any)=>{sessionStorage.setItem('staff_token',t);sessionStorage.setItem('staff_user',JSON.stringify(u));setToken(t);setUser(u)};const logout=()=>{sessionStorage.removeItem('staff_token');sessionStorage.removeItem('staff_user');setToken('');setUser(null)};return {token,user,login,logout};}
function fmtDate(v?:string){if(!v)return '—';const d=new Date(v);return isNaN(+d)?v:d.toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'})}
function errorText(e:any){if(e instanceof ApiError){if(e.status===401)return 'Phiên đăng nhập hoặc vé không còn hiệu lực.';if(e.status===403)return 'Bạn không có quyền thực hiện thao tác này.';return e.message}return e?.message||'Đã xảy ra lỗi. Vui lòng thử lại.'}
function IconMarker({category}:{category:string}){return <span className="marker">{category==='chim'?'🐦':category==='thu_an_thit'?'🦁':category==='thu_an_co'?'🦒':category==='linh_truong'?'🐒':category==='bo_sat_luong_cuong'?'🐢':'🌿'}</span>}
function MapClick({onPick}:{onPick:(lat:number,lon:number)=>void}){useMapEvents({click(e){onPick(e.latlng.lat,e.latlng.lng)}});return null}
function MapView({pois,position,onPick}:{pois:POI[];position?:[number,number]|null;onPick?:(lat:number,lon:number)=>void}){const center: [number,number]=position||[10.78755,106.70528];return <MapContainer center={center} zoom={16} scrollWheelZoom className="map"><TileLayer attribution='&copy; OpenStreetMap contributors' url={TILE}/>{pois.map(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon)?<span key={p.id}><Marker position={[p.lat,p.lon]}><Popup><b>{p.translations?.vi?.name||p.name||p.id}</b><br/><Link to={`/poi/${p.id}`}>Xem chi tiết →</Link></Popup></Marker>{p.radius_m?<Circle center={[p.lat,p.lon]} radius={p.radius_m} pathOptions={{color:'#16a34a',fillOpacity:.08}}/>:null}</span>:null)}{position&&<Circle center={position} radius={8} pathOptions={{color:'#2563eb',fillColor:'#3b82f6',fillOpacity:1}}/>}{onPick&&<MapClick onPick={onPick}/>}</MapContainer>}
function Header({hasTicket,onTicket}:{hasTicket:boolean;onTicket:()=>void}){return <header className="topbar"><Link to="/" className="brand"><span className="brand-icon"><Leaf/></span><span><b>Thảo Cầm Viên</b><small>Sài Gòn · Thuyết minh đa ngôn ngữ</small></span></Link><button className="btn btn-light" onClick={onTicket}>{hasTicket?<><Ticket size={17}/> Vé của tôi</>:<><Ticket size={17}/> Kích hoạt vé</>}</button></header>}
function useTicketModal(ticket:ReturnType<typeof useTicket>){
  const nav=useNavigate();
  const [open,setOpen]=useState(false);
  const [info,setInfo]=useState<any>(null);
  const openTicket=async()=>{
    setOpen(true);
    setInfo(null);
    if(ticket.valid){
      try{setInfo(await authApi.meTicket(ticket.token))}
      catch(e){ticket.clear();setInfo({error:errorText(e)})}
    }
  };
  const onHeaderTicket=()=>{
    if(ticket.valid)void openTicket();
    else nav('/activate');
  };
  const ticketModal=open&&<div className="modal-backdrop" onClick={()=>setOpen(false)}><section className="modal" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setOpen(false)}>×</button><span className="eyebrow">THẺ DU KHÁCH</span><h2>Vé của tôi</h2>{ticket.valid?<><div className="notice success"><CheckCircle/> Vé đã kích hoạt trên thiết bị này.</div><p>Hết hạn: <b>{fmtDate(ticket.expiry)}</b></p>{info?.error&&<p className="muted">{info.error}</p>}</>:<div className="notice warn"><Ticket/> Bạn chưa kích hoạt vé. Bạn vẫn có thể xem tất cả điểm tham quan.</div>}<Link className="btn btn-primary full" to="/activate" onClick={()=>setOpen(false)}>Kích hoạt lại trên máy này</Link></section></div>;
  return {openTicket,onHeaderTicket,ticketModal};
}
function GuestHome({ticket}:{ticket:ReturnType<typeof useTicket>}){
 const {openTicket,onHeaderTicket,ticketModal}=useTicketModal(ticket);const [pois,setPois]=useState<POI[]>([]),[loading,setLoading]=useState(true),[err,setErr]=useState(''),[query,setQuery]=useState(''),[cat,setCat]=useState(''),[tab,setTab]=useState<'map'|'list'>('map'),[pos,setPos]=useState<[number,number]|null>(null),[gpsMsg,setGpsMsg]=useState(''),[radius,setRadius]=useState('300'),[nearby,setNearby]=useState<POI[]|null>(null);
 const load=useCallback(async()=>{setLoading(true);setErr('');try{const d:any=await contentApi.pois();setPois(d.pois||[])}catch(e){setErr(errorText(e))}finally{setLoading(false)}},[]);
 useEffect(()=>{load()},[load]);useEffect(()=>{if(!navigator.geolocation){setGpsMsg('Thiết bị chưa hỗ trợ định vị. Bạn vẫn có thể xem bản đồ và danh sách.');return}const id=navigator.geolocation.watchPosition(p=>{setPos([p.coords.latitude,p.coords.longitude]);setGpsMsg('Đã xác định vị trí của bạn.')},()=>setGpsMsg('Chưa có quyền truy cập vị trí. Bạn vẫn có thể sử dụng bản đồ.'),{enableHighAccuracy:true,maximumAge:10000});return()=>navigator.geolocation.clearWatch(id)},[]);
 const filtered=useMemo(()=>pois.filter(p=>{const n=(p.translations?.vi?.name||p.name||p.id).toLowerCase();return n.includes(query.toLowerCase())&&(!cat||p.category===cat)}),[pois,query,cat]);
 const findNearby=async()=>{if(!pos){setGpsMsg('Hãy cho phép truy cập vị trí để tìm điểm gần bạn.');return}try{const d:any=await contentApi.nearby(pos[0],pos[1],radius==='all'?100000:Number(radius));setNearby(d.pois||[]);setTab('list')}catch(e){setErr(errorText(e))}};
 
 return <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/><main className="guest-wrap"><section className="hero"><div className="hero-copy"><span className="eyebrow"><Leaf size={15}/> KHÁM PHÁ THIÊN NHIÊN</span><h1>Mỗi bước chân,<br/><em>một câu chuyện.</em></h1><p>Khám phá các loài động vật và nghe thuyết minh đa ngôn ngữ tại Thảo Cầm Viên Sài Gòn.</p><div className="hero-actions"><button className="btn btn-primary" onClick={()=>{setTab('list');document.getElementById('explore')?.scrollIntoView({behavior:'smooth'})}}>Khám phá điểm tham quan <MapPin size={17}/></button><button className="btn btn-outline" onClick={()=>void openTicket()}><Ticket size={17}/> Vé của tôi</button></div></div><div className="hero-art"><span>🌿</span><div className="hero-animal">🦒</div><span>🍃</span></div></section><section className="info-grid"><article className="info-card"><span className="info-icon">☀️</span><div><b>Giờ mở cửa</b><p>Thông tin cần xác nhận và cập nhật</p></div></article><article className="info-card"><span className="info-icon">📍</span><div><b>Địa chỉ</b><p>2 Nguyễn Bỉnh Khiêm, Quận 1, TP.HCM</p></div></article><article className="info-card"><span className="info-icon">🌱</span><div><b>Về sở thú</b><p>Nội dung giới thiệu chính thức cần cập nhật</p></div></article></section><section id="explore" className="explore"><div className="section-heading"><div><span className="eyebrow">BẢN ĐỒ TƯƠNG TÁC</span><h2>Đi đâu tiếp nhỉ?</h2><p>Tìm kiếm và khám phá các điểm tham quan quanh bạn.</p></div><button className="btn btn-outline" onClick={()=>void findNearby()}><LocateFixed size={17}/> Điểm gần tôi</button></div><div className="search-row"><div className="searchbox"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Tìm tên điểm tham quan..."/></div><select value={cat} onChange={e=>setCat(e.target.value)}>{cats.map(c=><option value={c[0]} key={c[0]}>{c[1]}</option>)}</select><select aria-label="Bán kính tìm kiếm" value={radius} onChange={e=>setRadius(e.target.value)}><option value="100">Trong 100 m</option><option value="300">Trong 300 m</option><option value="500">Trong 500 m</option><option value="all">Tất cả</option></select></div>{gpsMsg&&<p className="gps-note"><LocateFixed size={15}/>{gpsMsg}</p>}<div className="tabs"><button className={tab==='map'?'active':''} onClick={()=>setTab('map')}>Bản đồ</button><button className={tab==='list'?'active':''} onClick={()=>setTab('list')}>Danh sách {nearby?`(${nearby.length})`:''}</button></div>{err&&<div className="notice error"><AlertCircle size={18}/>{err}<button onClick={()=>void load()}>Thử lại</button></div>}{loading?<div className="skeleton large"/>:<div className="explore-content">{tab==='map'?<MapView pois={filtered} position={pos}/>:<div className="poi-list">{(nearby||filtered).filter(p=>!query||(p.translations?.vi?.name||p.name||p.id).toLowerCase().includes(query.toLowerCase())).map(p=><PoiCard key={p.id} poi={p}/>)}</div>}{tab==='map'&&<div className="poi-list map-list">{filtered.slice(0,5).map(p=><PoiCard key={p.id} poi={p}/>)}</div>}{!filtered.length&&<div className="empty"><PawPrint/><b>Chưa tìm thấy điểm tham quan</b><span>Thử đổi từ khóa hoặc bộ lọc nhé.</span></div>}</div>}</section><footer>© Thảo Cầm Viên Sài Gòn · Cùng khám phá và bảo tồn thiên nhiên</footer></main>{ticketModal}</>}
function PoiCard({poi:p}:{poi:POI}){return <Link className="poi-card" to={`/poi/${p.id}`}><div className="poi-thumb">{p.image_url?<img src={p.image_url} alt=""/>:<span>{p.category==='chim'?'🐦':p.category==='thu_an_thit'?'🦁':p.category==='thu_an_co'?'🦒':'🌿'}</span>}</div><div className="poi-card-copy"><span className="category">{cats.find(c=>c[0]===p.category)?.[1]||p.category}</span><b>{p.translations?.vi?.name||p.name||p.id}</b><p>{p.translations?.vi?.description||p.species_name||'Khám phá điểm tham quan này.'}</p>{p.distance_m!==undefined&&<small><MapPin size={13}/>{p.distance_m<1000?`${Math.round(p.distance_m)} m`:`${(p.distance_m/1000).toFixed(1)} km`}</small>}</div><span className="arrow">↗</span></Link>}
function Activate({ticket}:{ticket:ReturnType<typeof useTicket>}){
 const {onHeaderTicket,ticketModal}=useTicketModal(ticket);const [params]=useSearchParams(),[code,setCode]=useState((params.get('code')||'').replace(/\s/g,'').toUpperCase()),[busy,setBusy]=useState(false),[err,setErr]=useState(''),[confirm,setConfirm]=useState(false),[success,setSuccess]=useState(false),[expiry,setExpiry]=useState('');const nav=useNavigate();const submit=async(switchDevice=false)=>{setBusy(true);setErr('');try{const d:any=await authApi.activate({code:code.replace(/\s/g,'').toUpperCase(),device_id:deviceId(),confirm_device_switch:switchDevice});ticket.save(d.ticket_token||d.token,d.expires_at);setExpiry(d.expires_at||'');setSuccess(true);setConfirm(false)}catch(e:any){if(e instanceof ApiError&&e.status===409&&(e.code==='used_on_other_device'||String(e.message).includes('confirm_required'))){setConfirm(true)}else if(e instanceof ApiError&&e.status===404) setErr('Mã vé không đúng');else if(e instanceof ApiError&&e.status===410)setErr('Vé đã hết hạn');else if(e instanceof ApiError&&e.status===429)setErr('Thử quá nhiều lần, vui lòng đợi ít phút');else setErr(errorText(e))}finally{setBusy(false)}};useEffect(()=>{if(params.get('code'))void submit(false)},[]);return <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/>{ticketModal}<main className="auth-page"><Link to="/" className="back-link">← Về trang chủ</Link><section className="auth-card"><div className="auth-illustration">🎟️<span>🌿</span></div>{success?<><div className="success-round"><CheckCircle/></div><h1>Kích hoạt thành công!</h1><p>Vé đã được liên kết với thiết bị này. Chúc bạn có chuyến tham quan vui vẻ.</p>{expiry&&<p>Hết hạn: <b>{fmtDate(expiry)}</b></p>}<button className="btn btn-primary full" onClick={()=>nav('/')}>Về trang chủ</button><button className="btn btn-outline full" onClick={()=>nav('/poi/tcv-001')}>Đi nghe thuyết minh</button></>:<><span className="eyebrow">MỞ KHÓA TRẢI NGHIỆM</span><h1>Kích hoạt vé tham quan</h1><p>Nhập mã trên vé của bạn để mở khóa thuyết minh âm thanh.</p><label htmlFor="ticket-code">Mã vé</label><input id="ticket-code" className="field code-field" value={code} onChange={e=>setCode(e.target.value.replace(/\s/g,'').toUpperCase())} placeholder="VD: TCV-ABC123" autoComplete="off"/>{err&&<div className="notice error"><AlertCircle/>{err}<button onClick={()=>void submit()}>Thử lại</button></div>}<button className="btn btn-primary full" disabled={busy||!code.trim()} onClick={()=>void submit()}>{busy?'Đang kích hoạt…':'Kích hoạt vé'}</button><p className="fine-print"><LockKeyhole size={14}/> Vé chỉ có thể nghe trên một thiết bị tại một thời điểm.</p></>}</section></main>{confirm&&<div className="modal-backdrop"><section className="modal"><h2>Chuyển vé sang thiết bị này?</h2><p>Vé này đã dùng ở máy khác. Chuyển sang máy này? Máy cũ sẽ không nghe được nữa.</p><div className="modal-actions"><button className="btn btn-outline" onClick={()=>setConfirm(false)}>Hủy</button><button className="btn btn-primary" onClick={()=>void submit(true)}>Đồng ý chuyển</button></div></section></div>}</>}
function AudioPlayer({id,lang,token,onUnauthorized,onListen}:{id:string;lang:Lang;token:string;onUnauthorized:()=>void;onListen:()=>void}){const [url,setUrl]=useState(''),[busy,setBusy]=useState(false),[err,setErr]=useState(''),[playing,setPlaying]=useState(false),[progress,setProgress]=useState(0),[duration,setDuration]=useState(0);const ref=useRef<HTMLAudioElement>(null);const load=async()=>{setBusy(true);setErr('');try{const blob=await audioApi.visitor(id,lang,token);const next=URL.createObjectURL(blob);setUrl(old=>{if(old)URL.revokeObjectURL(old);return next});}catch(e:any){if(e instanceof ApiError&&e.status===401){onUnauthorized();setErr('Vé không còn hiệu lực hoặc đã được chuyển thiết bị.')}else if(e instanceof ApiError&&e.status===502)setErr('Dịch vụ giọng nói đang gặp sự cố. Hãy thử lại.');else setErr(errorText(e))}finally{setBusy(false)}};useEffect(()=>{void load();return()=>{if(url)URL.revokeObjectURL(url)}},[id,lang,token]);useEffect(()=>{if(playing)onListen()},[playing]);return <div className="audio-box"><div className="audio-icon"><Volume2/></div><div className="audio-main"><b>Thuyết minh âm thanh</b><p>{busy?'Đang chuẩn bị audio…':err||'Nghe giới thiệu về điểm tham quan này.'}</p>{url&&<audio ref={ref} src={url} controls onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onTimeUpdate={e=>setProgress(e.currentTarget.currentTime)} onLoadedMetadata={e=>setDuration(e.currentTarget.duration)}/>}<div className="audio-meta">{duration?`${Math.floor(progress/60)}:${String(Math.floor(progress%60)).padStart(2,'0')} / ${Math.floor(duration/60)}:${String(Math.floor(duration%60)).padStart(2,'0')}`:'Chọn ngôn ngữ để nghe'}</div>{(busy||err)&&<button className="btn btn-outline" onClick={()=>void load()} disabled={busy}>{busy?'Đang tải…':'Thử lại'}</button>}</div></div>}
function PoiDetail({ticket}:{ticket:ReturnType<typeof useTicket>}){
 const {onHeaderTicket,ticketModal}=useTicketModal(ticket);const {id=''}=useParams(),nav=useNavigate(),[poi,setPoi]=useState<POI|null>(null),[err,setErr]=useState(''),[lang,setLang]=useState<Lang>((localStorage.getItem('zoo_lang') as Lang)||'vi'),[loading,setLoading]=useState(true),[pos,setPos]=useState<[number,number]|null>(null);useEffect(()=>{contentApi.poi(id).then((d:any)=>setPoi(d.poi||d)).catch(e=>setErr(errorText(e))).finally(()=>setLoading(false))},[id]);useEffect(()=>{localStorage.setItem('zoo_lang',lang)},[lang]);useEffect(()=>{if(!navigator.geolocation)return;const w=navigator.geolocation.watchPosition(p=>setPos([p.coords.latitude,p.coords.longitude]),()=>{}, {maximumAge:10000});return()=>navigator.geolocation.clearWatch(w)},[]);
const sendEvent=async(type:string)=>{
  try{
    await contentApi.sendEvent(
      {
        poi_id:id,
        type,
        ...(pos?{lat:pos[0],lon:pos[1]}:{})
      },
      ticket.token
    );
  }catch(e){
    console.warn('sendEvent failed',e);
  }
};
useEffect(()=>{if(!poi||!pos||!ticket.valid)return;const d=Math.hypot((pos[0]-poi.lat)*111000,(pos[1]-poi.lon)*111000*Math.cos(pos[0]*Math.PI/180));const inside=d<=(poi.radius_m||30);const key=`zoo_inside_${id}`,was=localStorage.getItem(key)==='true';if(inside!==was){localStorage.setItem(key,String(inside));void sendEvent(inside?'enter':'exit')}},[poi,pos,ticket.valid]);if(loading)return <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/>{ticketModal}<main className="detail-wrap"><div className="skeleton large"/></main></>;const tr=poi?.translations?.[lang];const title=tr?.name||poi?.name||id;return <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/>{ticketModal}<main className="detail-wrap"><Link className="back-link" to="/">← Tất cả điểm tham quan</Link>{err?<div className="notice error">{err}</div>:poi&&<><div className="detail-hero"><div className="detail-photo">{poi.image_url?<img src={poi.image_url} alt={title}/>:<div className="photo-placeholder"><span>🌳</span><span>🦜</span><small>Khám phá thiên nhiên</small></div>}</div><div className="detail-copy"><span className="category">{cats.find(c=>c[0]===poi.category)?.[1]||poi.category}</span><h1>{title}</h1>{poi.species_name&&<p className="species">{poi.species_name}</p>}<div className="lang-picker"><span>Ngôn ngữ thuyết minh</span><div>{languages.map(l=><button key={l} className={lang===l?'selected':''} onClick={()=>setLang(l)}>{({vi:'🇻🇳 VI',en:'🇬🇧 EN',zh:'🇨🇳 中文',ja:'🇯🇵 日本語',ko:'🇰🇷 한국어'} as any)[l]}</button>)}</div></div></div></div><section className="description-panel"><h2>{labels[lang].description}</h2><p>{tr?.description||poi.description||'Nội dung giới thiệu cho điểm tham quan này đang được cập nhật.'}</p></section>{ticket.valid?<AudioPlayer key={`${id}-${lang}`} id={id} lang={lang} token={ticket.token} onUnauthorized={ticket.clear} onListen={()=>void sendEvent('listen')}/>:<div className="locked-panel"><div className="lock-circle"><LockKeyhole/></div><div><b>Nghe thuyết minh</b><p>Cần vé để nghe, kích hoạt ở đây.</p><Link to="/activate" className="text-link">Kích hoạt vé ngay →</Link></div><LockKeyhole className="lock-end"/></div>}</>}</main></>}
function StaffLogin({staff}:{staff:ReturnType<typeof useStaff>}){const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[err,setErr]=useState(''),[busy,setBusy]=useState(false),nav=useNavigate();const submit=async(e:any)=>{e.preventDefault();setBusy(true);setErr('');try{const d:any=await authApi.login({username,password});const user={username:d.username||username,role:d.role};staff.login(d.token,user);nav(user.role==='counter'?'/staff/tickets':'/staff/dashboard')}catch(e:any){setErr(e instanceof ApiError&&e.status===401?'Sai tên đăng nhập hoặc mật khẩu.':e instanceof ApiError&&e.status===403?'Tài khoản đã bị khóa.':errorText(e))}finally{setBusy(false)}};return <main className="login-layout"><div className="login-art"><Leaf size={45}/><h1>Thiên nhiên<br/>trong tầm tay.</h1><p>Hệ thống quản lý thuyết minh đa ngôn ngữ<br/>Thảo Cầm Viên Sài Gòn</p><div className="login-leaves">🌿 🦜 🌱</div></div><form className="login-form" onSubmit={submit}><span className="eyebrow">CỔNG QUẢN TRỊ</span><h2>Chào mừng trở lại</h2><p>Đăng nhập để tiếp tục công việc của bạn.</p><label htmlFor="username">Tên đăng nhập</label><input id="username" className="field" value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" required/><label htmlFor="password">Mật khẩu</label><input id="password" className="field" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required/>{err&&<div className="notice error">{err}</div>}<button className="btn btn-primary full" disabled={busy}>{busy?'Đang đăng nhập…':'Đăng nhập'}</button>{import.meta.env.DEV&&<div className="demo-hint"><b>Tài khoản demo</b><br/>Admin: admin / admin123<br/>Quầy vé: counter01 / counter123</div>}<Link to="/" className="back-link">← Về trang du khách</Link></form></main>}

function handleStaffError(
  e:unknown,
  staff:ReturnType<typeof useStaff>,
  nav:ReturnType<typeof useNavigate>,
  setErr:(message:string)=>void
){
  if(e instanceof ApiError && e.status===401){
    staff.logout();
    nav('/staff',{replace:true});
    return;
  }

  setErr(errorText(e));
}

function StaffLayout({staff,children,adminOnly=false}:{staff:ReturnType<typeof useStaff>;children:any;adminOnly?:boolean}){const nav=useNavigate();if(!staff.token||!staff.user)return <Navigate to="/staff" replace/>;if(adminOnly&&staff.user.role!=='admin')return <Navigate to="/staff/tickets" replace/>;const links=[{to:'/staff/tickets',label:'Quản lý vé',icon:Ticket,roles:['admin','counter']},{to:'/staff/pois',label:'Điểm tham quan',icon:MapPin,roles:['admin']},{to:'/staff/dashboard',label:'Dashboard',icon:LayoutDashboard,roles:['admin']},{to:'/staff/accounts',label:'Tài khoản',icon:Users,roles:['admin']}];return <div className="staff-shell"><aside className="sidebar"><Link to="/" className="staff-brand"><Leaf/><span><b>ZooGuide</b><small>Quản trị hệ thống</small></span></Link><div className="side-caption">MENU CHÍNH</div>{links.filter(l=>l.roles.includes(staff.user.role)).map(l=><Link key={l.to} to={l.to} className="side-link"><l.icon size={18}/>{l.label}</Link>)}<div className="sidebar-bottom"><div className="user-avatar">{staff.user.username?.slice(0,1).toUpperCase()}</div><div className="user-info"><b>{staff.user.username}</b><small>{staff.user.role==='admin'?'Quản trị viên':'Nhân viên quầy vé'}</small></div><button title="Đăng xuất" onClick={()=>{staff.logout();nav('/staff')}}><LogOut/></button></div></aside><section className="staff-main"><header className="staff-top"><span>Thảo Cầm Viên Sài Gòn <span className="crumb">/ Không gian làm việc</span></span><span className="online-dot">● Đang hoạt động</span></header><div className="staff-content">{children}</div></section></div>}
function PageTitle({eyebrow,title,desc,action}:{eyebrow:string;title:string;desc:string;action?:any}){return <div className="page-title"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{desc}</p></div>{action}</div>}

function StaffTickets({staff}:{staff:ReturnType<typeof useStaff>}){
  const nav=useNavigate();

  const [tickets,setTickets]=useState<any[]>([]);
  const [created,setCreated]=useState<any>(null);
  const [err,setErr]=useState('');
  const [busy,setBusy]=useState(false);

  // Tải danh sách vé
  const load=useCallback(async()=>{
    try{
      const d:any=await authApi.tickets(staff.token);
      setTickets(d.tickets||d.items||d||[]);
      setErr('');
    }catch(e){
      // Lỗi 7: Token hết hạn thì đăng xuất
      handleStaffError(e,staff,nav,setErr);
    }
  },[staff.token,nav]);

  // Tự động cập nhật danh sách vé mỗi 15 giây
  useEffect(()=>{
    void load();
    const id=setInterval(()=>void load(),15000);
    return()=>clearInterval(id);
  },[load]);

  // Tạo vé mới
  const create=async()=>{
    setBusy(true);
    setErr('');

    try{
      const d:any=await authApi.createTicket(staff.token);
      const code=d.code||d.ticket?.code;
      const isLocalHost=(u:string)=>{
        try{
          return ['localhost','127.0.0.1','[::1]']
            .includes(new URL(u).hostname);
        }catch{
          return false;
        }
      };

      const fallbackUrl=
        `${location.origin}/activate?code=${encodeURIComponent(code||'')}`;

      const serverUrl:string=d.activation_url||'';

      const activation_url=
        serverUrl&&!(
          isLocalHost(serverUrl)&&
          !isLocalHost(location.origin)
        )
          ?serverUrl
          :fallbackUrl;

      setCreated({...d,code,activation_url});
      void load();

    }catch(e){
      handleStaffError(e,staff,nav,setErr);
    }finally{
      setBusy(false);
    }
  };

  return (
    <>
      <PageTitle
        eyebrow="QUẦY VÉ"
        title="Quản lý vé"
        desc="Tạo vé tham quan và cấp mã kích hoạt cho du khách."
        action={
          <button
            className="btn btn-primary"
            onClick={()=>void create()}
            disabled={busy}
          >
            <Plus size={18}/>
            {busy?'Đang tạo…':'Tạo vé mới'}
          </button>
        }
      />

      {err&&(
        <div className="notice error">
          {err}
          <button onClick={()=>void load()}>
            Thử lại
          </button>
        </div>
      )}

      {created&&(
        <section className="created-ticket">
          <div>
            <span className="eyebrow">VÉ VỪA TẠO</span>
            <h2>{created.code||'Mã vé'}</h2>
            <p>Đưa mã QR này cho du khách quét để kích hoạt vé.</p>

            <button
              className="btn btn-outline"
              onClick={()=>{
                void navigator.clipboard?.writeText(created.code||'');
              }}
            >
              <Copy size={16}/>
              Sao chép mã vé
            </button>

            <button
              className="btn btn-outline"
              onClick={()=>window.print()}
            >
              In vé / QR
            </button>
          </div>

          <div className="qr-frame">
            <QRCodeSVG
              value={created.activation_url}
              size={180}
              level="H"
            />
            <small>Quét để kích hoạt</small>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Vé hôm nay</h2>
            <p>Danh sách vé được tạo trong ngày.</p>
          </div>

          <button
            className="icon-btn"
            onClick={()=>void load()}
          >
            <RefreshCw size={17}/>
            Làm mới
          </button>
        </div>

        {!tickets.length&&!err?(
          <div className="empty">
            <Ticket/>
            <b>Chưa có vé nào hôm nay</b>
            <span>Nhấn “Tạo vé mới” để bắt đầu.</span>
          </div>
        ):(
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Mã vé</th>
                  <th>Thời gian tạo</th>
                  <th>Người tạo</th>
                  <th>Trạng thái</th>
                  <th>Hết hạn</th>
                </tr>
              </thead>

              <tbody>
                {tickets.map((t:any,i:number)=>(
                  <tr key={t.id||t.code||i}>
                    <td>
                      <b>{t.code||t.ticket_code||'—'}</b>
                    </td>

                    <td>
                      {fmtDate(t.created_at||t.createdAt)}
                    </td>

                    <td>
                      {t.created_by||t.username||'—'}
                    </td>

                    <td>
                      <span
                        className={`status ${
                          String(t.status).toLowerCase().includes('activ')
                            ?'green'
                            :String(t.status).toLowerCase().includes('expir')
                              ?'red'
                              :'gray'
                        }`}
                      >
                        {t.status_label||t.status||'Chưa kích hoạt'}
                      </span>
                    </td>

                    <td>
                      {fmtDate(t.expires_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
const emptyTranslation=()=>({name:'',description:''});

function PoiForm({
  poi,token,onClose,onSaved,onUnauthorized
}:{
  poi:POI|null;
  token:string;
  onClose:()=>void;
  onSaved:()=>void;
  onUnauthorized:()=>void;
}){
  const [name,setName]=useState(
    poi?.name||poi?.translations?.vi?.name||''
  );
  const [category,setCategory]=useState(poi?.category||'tien_ich');
  const [species,setSpecies]=useState(poi?.species_name||'');
  const [image,setImage]=useState(poi?.image_url||'');
  const [lat,setLat]=useState(String(poi?.lat??10.78755));
  const [lon,setLon]=useState(String(poi?.lon??106.70528));
  const [radius,setRadius]=useState(String(poi?.radius_m??30));
  const [lang,setLang]=useState<Lang>('vi');

  const [translations,setTranslations]=useState<
    Record<string,{name:string;description:string}>
  >(()=>Object.fromEntries(
    languages.map(l=>[
      l,
      {...emptyTranslation(),...(poi?.translations?.[l]||{})}
    ])
  ));

  const [err,setErr]=useState('');
  const [busy,setBusy]=useState(false);
  const [preview,setPreview]=useState('');

  // Cập nhật tên và mô tả theo ngôn ngữ
  const update=(
    field:'name'|'description',
    value:string
  )=>{
    setTranslations(o=>({
      ...o,
      [lang]:{
        ...o[lang],
        [field]:value
      }
    }));
  };

  // Lưu điểm tham quan
  const save=async()=>{
    if(!translations.vi.name.trim()||
       !translations.vi.description.trim()){
      setErr('Vui lòng nhập tên và mô tả tiếng Việt.');
      return;
    }

    if(
      !Number.isFinite(Number(lat))||
      Number(lat)<-90||
      Number(lat)>90||
      !Number.isFinite(Number(lon))||
      Number(lon)<-180||
      Number(lon)>180||
      Number(radius)<=0
    ){
      setErr('Tọa độ không hợp lệ hoặc bán kính phải lớn hơn 0.');
      return;
    }

    setBusy(true);
    setErr('');

    try{
      const body={
        name:translations.vi.name,
        category,
        species_name:species||null,
        image_url:image||null,
        lat:Number(lat),
        lon:Number(lon),
        radius_m:Number(radius),
        translations:Object.fromEntries(
          Object.entries(translations).filter(
            ([_,v])=>v.name.trim()&&v.description.trim()
          )
        )
      };

      if(poi){
        await contentApi.updatePoi(
          poi.id,
          {
            name:body.name,
            category,
            species_name:body.species_name,
            image_url:body.image_url,
            lat:body.lat,
            lon:body.lon,
            radius_m:body.radius_m
          },
          token
        );

        for(const [l,v] of Object.entries(body.translations)){
          await contentApi.patchTranslation(poi.id,l,v,token);
        }

      }else{
        await contentApi.createPoi(body,token);
      }

      onSaved();
      onClose();

    }catch(e){
      // LỖI 7: Token nhân viên hết hạn
      if(e instanceof ApiError&&e.status===401){
        onUnauthorized();
      }else{
        setErr(errorText(e));
      }

    }finally{
      setBusy(false);
    }
  };

  // Nghe thử thuyết minh
  const play=async()=>{
    if(!poi){
      setErr('Hãy lưu điểm tham quan trước khi nghe thử.');
      return;
    }

    try{
      const blob=await audioApi.preview(poi.id,lang,token);
      const url=URL.createObjectURL(blob);

      setPreview(old=>{
        if(old)URL.revokeObjectURL(old);
        return url;
      });

    }catch(e){
      // LỖI 7: Token nhân viên hết hạn
      if(e instanceof ApiError&&e.status===401){
        onUnauthorized();
      }else{
        setErr(errorText(e));
      }
    }
  };

  return (
    <div className="modal-backdrop">
      <section className="modal poi-form-modal">
        <button className="close" onClick={onClose}>×</button>

        <span className="eyebrow">QUẢN LÝ DỮ LIỆU</span>
        <h2>
          {poi?'Chỉnh sửa điểm tham quan':'Thêm điểm tham quan'}
        </h2>

        <div className="form-grid">
          <label>
            Tên tiếng Việt *
            <input
              className="field"
              value={name}
              onChange={e=>{
                setName(e.target.value);
                setTranslations(o=>({
                  ...o,
                  vi:{...o.vi,name:e.target.value}
                }));
              }}
            />
          </label>

          <label>
            Danh mục
            <select
              className="field"
              value={category}
              onChange={e=>setCategory(e.target.value)}
            >
              {cats.filter(c=>c[0]).map(c=>(
                <option key={c[0]} value={c[0]}>
                  {c[1]}
                </option>
              ))}
            </select>
          </label>

          <label>
            Tên loài
            <input
              className="field"
              value={species}
              onChange={e=>setSpecies(e.target.value)}
            />
          </label>

          <label>
            URL ảnh
            <input
              className="field"
              value={image}
              onChange={e=>setImage(e.target.value)}
              placeholder="https://..."
            />
          </label>

          <label>
            Vĩ độ (lat)
            <input
              className="field"
              type="number"
              value={lat}
              onChange={e=>setLat(e.target.value)}
              step="any"
            />
          </label>

          <label>
            Kinh độ (lon)
            <input
              className="field"
              type="number"
              value={lon}
              onChange={e=>setLon(e.target.value)}
              step="any"
            />
          </label>

          <label>
            Bán kính vùng kích hoạt (m)
            <input
              className="field"
              type="number"
              value={radius}
              onChange={e=>setRadius(e.target.value)}
            />
          </label>
        </div>

        <div className="mini-map-wrap">
          <MapView
            pois={[]}
            onPick={(a,b)=>{
              setLat(a.toFixed(6));
              setLon(b.toFixed(6));
            }}
          />
          <p>
            Bấm vào bản đồ để chọn tọa độ; có thể chỉnh
            lat/lon bằng cách nhập tay.
          </p>
        </div>

        <div className="lang-tabs">
          {languages.map(l=>(
            <button
              key={l}
              className={lang===l?'selected':''}
              onClick={()=>setLang(l)}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>

        <label>
          Tên bản dịch
          <input
            className="field"
            value={translations[lang]?.name||''}
            onChange={e=>update('name',e.target.value)}
          />
        </label>

        <label>
          Mô tả bản dịch
          <textarea
            className="field"
            rows={3}
            value={translations[lang]?.description||''}
            onChange={e=>update('description',e.target.value)}
          />
        </label>

        <button
          className="btn btn-outline"
          onClick={()=>void play()}
        >
          <Headphones size={16}/>
          Nghe thử bản dịch {lang.toUpperCase()}
        </button>

        {preview&&<audio controls src={preview}/>}

        {err&&(
          <div className="notice error">
            {err}
          </div>
        )}

        <div className="modal-actions">
          <button
            className="btn btn-outline"
            onClick={onClose}
          >
            Hủy
          </button>

          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={()=>void save()}
          >
            {busy?'Đang lưu…':'Lưu điểm tham quan'}
          </button>
        </div>
      </section>
    </div>
  );
}

function StaffPois({staff}:{staff:ReturnType<typeof useStaff>}){
  const nav=useNavigate();

  const [pois,setPois]=useState<POI[]>([]);
  const [loading,setLoading]=useState(true);
  const [err,setErr]=useState('');
  const [query,setQuery]=useState('');
  const [cat,setCat]=useState('');
  const [editing,setEditing]=useState<POI|null|undefined>(undefined);

  // Tải danh sách điểm tham quan
  const load=useCallback(async()=>{
    setLoading(true);

    try{
      const d:any=await contentApi.pois();
      setPois(d.pois||[]);
      setErr('');
    }catch(e){
      setErr(errorText(e));
    }finally{
      setLoading(false);
    }
  },[]);

  useEffect(()=>{
    void load();
  },[load]);

  // Lọc danh sách theo tên và danh mục
  const list=pois.filter(p=>
    (p.name||p.translations?.vi?.name||p.id)
      .toLowerCase()
      .includes(query.toLowerCase()) &&
    (!cat||p.category===cat)
  );

  // Xóa điểm tham quan
  const remove=async(p:POI)=>{
    if(!confirm(
      `Bạn có chắc muốn xóa điểm "${p.translations?.vi?.name||p.name||p.id}"?`
    ))return;

    try{
      await contentApi.deletePoi(p.id,staff.token);
      await load();
    }catch(e){
      // Lỗi 7: Token hết hạn thì đăng xuất
      handleStaffError(e,staff,nav,setErr);
    }
  };

  return (
    <>
      <PageTitle
        eyebrow="NỘI DUNG"
        title="Điểm tham quan"
        desc="Quản lý thông tin, vị trí và bản dịch của các điểm."
        action={
          <button
            className="btn btn-primary"
            onClick={()=>setEditing(null)}
          >
            <Plus size={18}/>
            Thêm điểm
          </button>
        }
      />

      {err&&(
        <div className="notice error">
          {err}
          <button onClick={()=>void load()}>
            Thử lại
          </button>
        </div>
      )}

      <section className="panel">
        <div className="search-row staff-search">
          <div className="searchbox">
            <Search/>
            <input
              value={query}
              onChange={e=>setQuery(e.target.value)}
              placeholder="Tìm điểm tham quan…"
            />
          </div>

          <select
            value={cat}
            onChange={e=>setCat(e.target.value)}
          >
            {cats.map(c=>(
              <option value={c[0]} key={c[0]}>
                {c[1]}
              </option>
            ))}
          </select>
        </div>

        {loading?(
          <div className="skeleton large"/>
        ):(
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Điểm tham quan</th>
                  <th>Danh mục</th>
                  <th>Tọa độ</th>
                  <th>Bán kính</th>
                  <th>Thao tác</th>
                </tr>
              </thead>

              <tbody>
                {list.map(p=>(
                  <tr key={p.id}>
                    <td>
                      <b>{p.translations?.vi?.name||p.name||p.id}</b>
                      <small className="table-sub">{p.id}</small>
                    </td>

                    <td>
                      {cats.find(c=>c[0]===p.category)?.[1]||p.category}
                    </td>

                    <td>
                      {p.lat?.toFixed?.(5)}, {p.lon?.toFixed?.(5)}
                    </td>

                    <td>{p.radius_m||30} m</td>

                    <td>
                      <div className="table-actions">
                        <button
                          className="icon-btn"
                          onClick={()=>setEditing(p)}
                          title="Sửa"
                        >
                          <Edit3 size={16}/>
                        </button>

                        <button
                          className="icon-btn danger-icon"
                          onClick={()=>void remove(p)}
                          title="Xóa"
                        >
                          <Trash2 size={16}/>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {!list.length&&(
              <div className="empty">
                <PawPrint/>
                <b>Không có điểm phù hợp</b>
              </div>
            )}
          </div>
        )}
      </section>

      {editing!==undefined&&(
        <PoiForm
          poi={editing||null}
          token={staff.token}
          onClose={()=>setEditing(undefined)}
          onSaved={()=>void load()}
          onUnauthorized={()=>{
            staff.logout();
            nav('/staff',{replace:true});
          }}
        />
      )}
    </>
  );
}
function Dashboard({staff}:{staff:ReturnType<typeof useStaff>}){const nav=useNavigate();const [data,setData]=useState<any>(null),[events,setEvents]=useState<any[]>([]),[err,setErr]=useState(''),[sort,setSort]=useState<'present_now'|'passes_today'>('passes_today');
const load=useCallback(async()=>{
  try{
    const [d,e]:any[]=await Promise.all([
      contentApi.dashboard(staff.token),

      contentApi.events(staff.token).catch(e=>{
        if(e instanceof ApiError && e.status===401){
          throw e;
        }
        return {events:[]};
      })
    ]);

    setData(d);
    setEvents(e.events||e.items||[]);
    setErr('');

  }catch(e){
    handleStaffError(e,staff,nav,setErr);
  }
},[staff.token,nav]);
useEffect(()=>{void load();const id=setInterval(()=>void load(),20000);return()=>clearInterval(id)},[load]);const overview=data?.overview||{},pois=data?.pois?.pois||data?.pois||[],hourly=data?.hourly?.hours||data?.hourly?.hourly||data?.hourly||[];const get=(o:any,keys:string[],fallback=0)=>{for(const k of keys)if(o?.[k]!==undefined)return o[k];return fallback};const rows=[...pois].sort((a,b)=>Number(b[sort]||0)-Number(a[sort]||0));return <><PageTitle eyebrow="TỔNG QUAN" title="Dashboard" desc="Theo dõi tình hình vé và hoạt động tham quan theo thời gian thực." action={<button className="btn btn-outline" onClick={()=>void load()}><RefreshCw size={17}/> Làm mới</button>}/>{err&&<div className="notice error">{err}</div>}<div className="metric-grid"><article className="metric-card"><span className="metric-icon"><Ticket/></span><small>Vé bán hôm nay</small><strong>{get(overview,['tickets_sold_today','tickets_today','sold_today','tickets_sold'])}</strong><span className="metric-foot">Tổng vé được tạo hôm nay</span></article><article className="metric-card"><span className="metric-icon mint-bg"><Users/></span><small>Vé đang hoạt động</small><strong>{get(overview,['active_tickets','active_tickets_now','active_now'])}</strong><span className="metric-foot">Có sự kiện trong {get(overview,['n_active_minutes'],10)} phút gần nhất</span></article><article className="metric-card"><span className="metric-icon gold-bg"><MapPin/></span><small>Điểm tham quan</small><strong>{rows.length}</strong><span className="metric-foot">Điểm trong hệ thống</span></article></div><div className="dashboard-grid"><section className="panel"><div className="panel-heading"><div><h2>Lượt tham quan theo giờ</h2><p>Hoạt động trong 24 giờ gần nhất.</p></div></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={hourly}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="label" tick={{fontSize:11}}/><YAxis tick={{fontSize:11}}/><Tooltip/><Legend/><Line type="monotone" dataKey="visits" name="Lượt tham quan" stroke="#16a34a" strokeWidth={3}/><Line type="monotone" dataKey="tickets_sold" name="Vé bán" stroke="#84cc16" strokeWidth={2}/></LineChart></ResponsiveContainer></div></section><section className="panel"><div className="panel-heading"><div><h2>Điểm nổi bật</h2><p>So sánh lượng khách theo điểm.</p></div></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows.slice(0,8)}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name" hide/><YAxis/><Tooltip/><Legend/><Bar dataKey="present_now" name="Đang ở điểm" fill="#16a34a" radius={[5,5,0,0]}/><Bar dataKey="passes_today" name="Lượt đi qua" fill="#a3e635" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div></section></div><section className="panel"><div className="panel-heading"><div><h2>Thống kê theo điểm</h2><p>Đang ở điểm: khách hiện diện · Lượt đi qua: sự kiện vào điểm hôm nay.</p></div><select value={sort} onChange={e=>setSort(e.target.value as any)}><option value="passes_today">Sắp xếp lượt đi qua</option><option value="present_now">Sắp xếp hiện diện</option></select></div><div className="table-wrap"><table><thead><tr><th>Điểm</th><th>Đang ở điểm</th><th>Lượt đi qua hôm nay</th></tr></thead><tbody>{rows.map((p:any,i:number)=><tr key={p.poi_id||p.id||i}><td>{p.name||p.poi_name||p.poi_id}</td><td>{p.present_now||0}</td><td>{p.passes_today||0}</td></tr>)}</tbody></table></div></section><section className="panel"><div className="panel-heading"><div><h2>Sự kiện gần đây</h2><p>Danh sách sự kiện mới nhất từ hệ thống.</p></div></div>{!events.length?<p className="muted pad">Chưa có sự kiện hoặc API không trả dữ liệu.</p>:<div className="table-wrap"><table><thead><tr><th>Thời gian</th><th>Điểm</th><th>Loại sự kiện</th></tr></thead><tbody>{events.map((e:any,i:number)=><tr key={e.id||i}><td>{fmtDate(e.ts||e.created_at)}</td><td>{e.poi_id}</td><td>{e.type}</td></tr>)}</tbody></table></div>}</section></>}

function Accounts({staff}:{staff:ReturnType<typeof useStaff>}){
  const nav=useNavigate();

  const [users,setUsers]=useState<any[]>([]);
  const [err,setErr]=useState('');
  const [username,setUsername]=useState('');
  const [password,setPassword]=useState('');
  const [busy,setBusy]=useState(false);

  // Tải danh sách tài khoản
  const load=useCallback(async()=>{
    try{
      const d:any=await authApi.users(staff.token);
      setUsers(d.users||d||[]);
      setErr('');
    }catch(e){
      // Lỗi 7: Token hết hạn thì đăng xuất
      handleStaffError(e,staff,nav,setErr);
    }
  },[staff.token,nav]);

  useEffect(()=>{
    void load();
  },[load]);

  // Tạo tài khoản nhân viên quầy vé
  const create=async(e:any)=>{
    e.preventDefault();
    setBusy(true);
    setErr('');

    try{
      await authApi.createUser(
        {username,password,role:'counter'},
        staff.token
      );

      setUsername('');
      setPassword('');
      await load();

    }catch(e){
      // Lỗi 7: Token hết hạn thì đăng xuất
      handleStaffError(e,staff,nav,setErr);
    }finally{
      setBusy(false);
    }
  };

  // Khóa hoặc mở khóa tài khoản
  const toggle=async(u:any)=>{
    try{
      await authApi.userStatus(
        u.id,
        {is_active:!u.is_active},
        staff.token
      );

      await load();

    }catch(e){
      // Lỗi 7: Token hết hạn thì đăng xuất
      handleStaffError(e,staff,nav,setErr);
    }
  };

  return (
    <>
      <PageTitle
        eyebrow="PHÂN QUYỀN"
        title="Quản lý tài khoản"
        desc="Tạo và quản lý tài khoản nhân viên quầy vé."
      />

      {err&&(
        <div className="notice error">
          {err}
        </div>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Tạo tài khoản quầy vé</h2>
            <p>Tài khoản mới sẽ được cấp vai trò counter.</p>
          </div>
        </div>

        <form className="account-form" onSubmit={create}>
          <label>
            Tên đăng nhập
            <input
              className="field"
              value={username}
              onChange={e=>setUsername(e.target.value)}
              required
            />
          </label>

          <label>
            Mật khẩu
            <input
              className="field"
              type="password"
              value={password}
              onChange={e=>setPassword(e.target.value)}
              required
              minLength={6}
            />
          </label>

          <button className="btn btn-primary" disabled={busy}>
            <Plus size={16}/>
            Tạo tài khoản
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Tài khoản hệ thống</h2>

          <button
            className="icon-btn"
            onClick={()=>void load()}
          >
            <RefreshCw size={16}/>
            Làm mới
          </button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tên đăng nhập</th>
                <th>Vai trò</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>

            <tbody>
              {users.map((u:any)=>(
                <tr key={u.id}>
                  <td>
                    <b>{u.username}</b>
                  </td>

                  <td>{u.role}</td>

                  <td>
                    <span className={`status ${u.is_active?'green':'red'}`}>
                      {u.is_active?'Đang hoạt động':'Đã khóa'}
                    </span>
                  </td>

                  <td>
                    <button
                      className="btn btn-outline btn-small"
                      disabled={u.username===staff.user.username}
                      onClick={()=>void toggle(u)}
                    >
                      {u.is_active?'Khóa':'Mở khóa'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
export default function App(){const ticket=useTicket(),staff=useStaff();return <Routes><Route path="/" element={<GuestHome ticket={ticket}/>}/><Route path="/poi/:id" element={<PoiDetail ticket={ticket}/>}/><Route path="/activate" element={<Activate ticket={ticket}/>}/><Route path="/staff" element={staff.token?<Navigate to={staff.user?.role==='counter'?'/staff/tickets':'/staff/dashboard'}/>:<StaffLogin staff={staff}/>}/><Route path="/staff/tickets" element={<StaffLayout staff={staff}><StaffTickets staff={staff}/></StaffLayout>}/><Route path="/staff/dashboard" element={<StaffLayout staff={staff} adminOnly><Dashboard staff={staff}/></StaffLayout>}/><Route path="/staff/pois" element={<StaffLayout staff={staff} adminOnly><StaffPois staff={staff}/></StaffLayout>}/><Route path="/staff/accounts" element={<StaffLayout staff={staff} adminOnly><Accounts staff={staff}/></StaffLayout>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}
