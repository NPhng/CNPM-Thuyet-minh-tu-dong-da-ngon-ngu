import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Routes,Route,Link,useNavigate,useParams,useSearchParams,Navigate} from 'react-router-dom';
import {MapContainer,TileLayer,Marker,Popup,Circle,Tooltip as LeafletTooltip,useMap,useMapEvents} from 'react-leaflet';
import L from 'leaflet'; import {QRCodeSVG} from 'qrcode.react'; import {BarChart,Bar,LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer,Legend} from 'recharts';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import {Leaf,Ticket,MapPin,Search,LocateFixed,Headphones,LockKeyhole,LogOut,LayoutDashboard,PawPrint,Users,Plus,RefreshCw,Trash2,Edit3,Copy,CheckCircle,AlertCircle,Menu,Volume2,Camera,X} from 'lucide-react';
import {authApi,contentApi,audioApi,ApiError} from './api/client'; import {languages,labels,Lang,T,catName,LOCALES,errorText} from './i18n';
import { Html5Qrcode } from 'html5-qrcode';
import {useLang,getLang} from './useLang';
type POI={id:string;name?:string;lat:number;lon:number;radius_m?:number;category:string;species_name?:string;image_url?:string;translations?:Record<string,{name?:string;description?:string}>;description?:string;distance_m?:number};
const cats=[['','Tất cả'],['thu_an_thit','Thú ăn thịt'],['thu_an_co','Thú ăn cỏ'],['chim','Chim'],['bo_sat_luong_cu','Bò sát & lưỡng cư'],['linh_truong','Linh trưởng'],['tien_ich','Tiện ích']];
const TILE=import.meta.env.VITE_TILE_URL||'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
function safeGet(key: string): string | null { try { return localStorage.getItem(key); } catch { return null; } }
function safeSet(key: string, val: string): void { try { localStorage.setItem(key, val); } catch {} }
function safeRemove(key: string): void { try { localStorage.removeItem(key); } catch {} }
function safeSessionGet(key: string): string | null { try { return sessionStorage.getItem(key); } catch { return null; } }
function safeSessionSet(key: string, val: string): void { try { sessionStorage.setItem(key, val); } catch {} }
function safeSessionRemove(key: string): void { try { sessionStorage.removeItem(key); } catch {} }
function deviceId(){let id=safeGet('zoo_device_id');if(!id){id=crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`;safeSet('zoo_device_id',id)}return id}

function useTicket() {
  const [token, setToken] = useState(
    safeGet('ticket_token') || ''
  );
  const [expiry, setExpiry] = useState(
    safeGet('ticket_expires_at') || ''
  );
  const [notice, setNotice] = useState('');

  const clear = useCallback(() => {
    safeRemove('ticket_token');
    safeRemove('ticket_expires_at');
    setToken('');
    setExpiry('');
  }, []);

  const expire = useCallback((msg?: string) => {
    clear();
    setNotice(msg || 'ticketRevoked');
  }, [clear]);

  const handleError = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) {
      expire();
      return true;
    }
    return false;
  }, [expire]);

  const valid =
    !!token && (!expiry || new Date(expiry).getTime() > Date.now());

  useEffect(() => {
    if (token && !valid) clear();
  }, [token, valid, clear]);

  // Lệnh 3: auto-expire khi đến hạn vé phía client
  useEffect(() => {
    if (!expiry) return;
    const ms = new Date(expiry).getTime() - Date.now();
    if (ms <= 0) { expire('ticketExpired'); return; }
    const tid = setTimeout(() => expire('ticketExpired'), ms);
    return () => clearTimeout(tid);
  }, [expiry, expire]);

  const save = (t: string, e?: string) => {
    safeSet('ticket_token', t);
    if (e) safeSet('ticket_expires_at', e); else safeRemove('ticket_expires_at');
    setToken(t);
    setExpiry(e || '');
    setNotice('');
  };

  return {
    token,
    expiry,
    valid,
    clear,
    save,
    notice,
    expire,
    handleError,
    dismissNotice: () => setNotice('')
  };
}
function useStaff(){const [token,setToken]=useState(safeSessionGet('staff_token')||'');const [user,setUser]=useState<any>(()=>{try{return JSON.parse(safeSessionGet('staff_user')||'null')}catch{return null}});const login=(t:string,u:any)=>{safeSessionSet('staff_token',t);safeSessionSet('staff_user',JSON.stringify(u));setToken(t);setUser(u)};const logout=()=>{safeSessionRemove('staff_token');safeSessionRemove('staff_user');setToken('');setUser(null)};return {token,user,login,logout};}
function fmtDate(v?:string,lang:Lang=getLang()){if(!v)return '—';const d=new Date(v);return isNaN(+d)?v:d.toLocaleString(LOCALES[lang],{timeZone:'Asia/Ho_Chi_Minh'})}
// errorText moved to i18n.ts
function qrWarning(url: string) {
  try {
    const host = new URL(url).hostname;
    const runningLocally =
      ['localhost', '127.0.0.1'].includes(location.hostname);

    const invalidHost =
      ['localhost', '127.0.0.1'].includes(host) ||
      host === 'example.com' ||
      host.endsWith('.example.com');

    return invalidHost && !runningLocally
      ? `Link QR đang trỏ tới "${host}". Điện thoại du khách có thể không mở được. Hãy đặt VITE_PUBLIC_BASE_URL đúng domain rồi build lại.`
      : '';
  } catch {
    return '';
  }
}
// Vite đổi tên file ảnh của Leaflet nên icon mặc định bị vỡ; khai báo icon tường minh.
const zooMarkerIcon=L.icon({iconUrl:markerIcon,iconRetinaUrl:markerIcon2x,shadowUrl:markerShadow,iconSize:[25,41],iconAnchor:[12,41],popupAnchor:[1,-34],tooltipAnchor:[16,-28],shadowSize:[41,41]});
function IconMarker({category}:{category:string}){return <span className="marker">{category==='chim'?'🐦':category==='thu_an_thit'?'🦁':category==='thu_an_co'?'🦒':category==='linh_truong'?'🐒':category==='bo_sat_luong_cu'?'🐢':'🌿'}</span>}
function MapClick({onPick}:{onPick:(lat:number,lon:number)=>void}){useMapEvents({click(e){onPick(e.latlng.lat,e.latlng.lng)}});return null}
const poiName=(p:POI,l:Lang)=>p.translations?.[l]?.name||p.translations?.en?.name||p.translations?.vi?.name||p.name||p.id;
const poiDesc=(p:POI,l:Lang)=>p.translations?.[l]?.description||p.translations?.en?.description||p.translations?.vi?.description||p.description||p.species_name||'';
const distanceM=(a:[number,number],b:[number,number])=>{const R=6371000,r=(x:number)=>x*Math.PI/180,dLat=r(b[0]-a[0]),dLon=r(b[1]-a[1]);const h=Math.sin(dLat/2)**2+Math.cos(r(a[0]))*Math.cos(r(b[0]))*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h))};
function FlyTo({target}:{target?:[number,number]|null}){const map=useMap();useEffect(()=>{if(target)map.flyTo(target,17)},[target?.[0],target?.[1],map]);return null}
function MapView({pois,position,onPick,manual,focus}:{pois:POI[];position?:[number,number]|null;onPick?:(lat:number,lon:number)=>void;manual?:boolean;focus?:[number,number]|null}){const [lang]=useLang();const center: [number,number]=position||[10.78755,106.70528];return <MapContainer center={center} zoom={16} scrollWheelZoom className="map"><TileLayer attribution='&copy; OpenStreetMap contributors' url={TILE}/><FlyTo target={focus}/>{pois.map(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon)?<span key={p.id}><Marker icon={zooMarkerIcon} position={[p.lat,p.lon]}><Popup><b>{poiName(p,lang)}</b><br/><Link to={`/poi/${p.id}`}>{T('viewDetail',lang)}</Link></Popup></Marker>{p.radius_m?<Circle center={[p.lat,p.lon]} radius={p.radius_m} pathOptions={{color:'#16a34a',fillOpacity:.08}}/>:null}</span>:null)}{position&&<Circle center={position} radius={manual?12:8} pathOptions={manual?{color:'#f59e0b',fillColor:'#fbbf24',fillOpacity:1}:{color:'#2563eb',fillColor:'#3b82f6',fillOpacity:1}}>{manual&&<LeafletTooltip permanent direction="top">{T('yourPos',lang)}</LeafletTooltip>}</Circle>}{onPick&&<MapClick onPick={onPick}/>}</MapContainer>}
const FLAGS:Record<Lang,string>={vi:'🇻🇳 VI',en:'🇬🇧 EN',zh:'🇨🇳 中文',ja:'🇯🇵 日本語',ko:'🇰🇷 한국어'};
function Header({hasTicket,onTicket}:{hasTicket:boolean;onTicket:()=>void}){const [lang,setLang]=useLang();return <header className="topbar"><Link to="/" className="brand"><span className="brand-icon"><Leaf/></span><span><b>Thảo Cầm Viên</b><small>{T('brandSub',lang)}</small></span></Link><div className="topbar-actions"><select className="lang-select" aria-label="Language" value={lang} onChange={e=>setLang(e.target.value as Lang)}>{languages.map(l=><option key={l} value={l}>{FLAGS[l]}</option>)}</select><button className="btn btn-light" onClick={onTicket}><Ticket size={17}/> {hasTicket?labels[lang].myTicket:labels[lang].activate}</button></div></header>}
function useTicketModal(ticket:ReturnType<typeof useTicket>){
  const nav=useNavigate();const [lang]=useLang();
  const [open,setOpen]=useState(false);
  const [info,setInfo]=useState<any>(null);
  const openTicket=async()=>{
    setOpen(true);
    setInfo(null);
    if(ticket.valid){
      try{setInfo(await authApi.meTicket(ticket.token))}
      catch(e) {
          if (!ticket.handleError(e)) {
            setInfo({ error: errorText(e, getLang()) });
          }
        }
    }
  };
  const onHeaderTicket=()=>{
    if(ticket.valid)void openTicket();
    else nav('/activate');
  };
  const ticketModal=open&&<div className="modal-backdrop" onClick={()=>setOpen(false)}><section className="modal" onClick={e=>e.stopPropagation()}><button className="close" aria-label={T('close',lang)} onClick={()=>setOpen(false)}>×</button><span className="eyebrow">{T('ticketEyebrow',lang)}</span><h2>{labels[lang].myTicket}</h2>{ticket.valid?<><div className="notice success"><CheckCircle/> {T('ticketOk',lang)}</div><p>{T('expires',lang)} <b>{fmtDate(ticket.expiry,lang)}</b></p>{info?.error&&<p className="muted">{info.error}</p>}</>:<div className="notice warn"><Ticket/> {T('ticketNone',lang)}</div>}
    <Link
      className="btn btn-primary full"
      to="/activate"
      onClick={() => setOpen(false)}
    >
      {ticket.valid ? T('enterOther',lang) : labels[lang].activate}
    </Link>

    {ticket.valid && (
      <button
        className="btn btn-outline full"
        onClick={() => {
          if (
            window.confirm(
              T('logoutConfirm',lang)
            )
          ) {
            ticket.clear();
            setOpen(false);
          }
        }}
      >
        {T('logoutBtn',lang)}
      </button>
    )}
</section></div>;
  return {openTicket,onHeaderTicket,ticketModal};
}
function GuestHome({ticket}:{ticket:ReturnType<typeof useTicket>}){
 const [lang]=useLang();
 const {openTicket,onHeaderTicket,ticketModal}=useTicketModal(ticket);const [pois,setPois]=useState<POI[]>([]),[loading,setLoading]=useState(true),[err,setErr]=useState(''),[query,setQuery]=useState(''),[tab,setTab]=useState<'map'|'list'>('map'),[gpsPos,setGpsPos]=useState<[number,number]|null>(null),[gpsFailed,setGpsFailed]=useState(false),[manualId,setManualId]=useState(''),[destId,setDestId]=useState(''),[gpsMsg,setGpsMsg]=useState(''),[radius,setRadius]=useState('300'),[nearby,setNearby]=useState<POI[]|null>(null);
 const load=useCallback(async()=>{setLoading(true);setErr('');try{const d:any=await contentApi.pois();setPois(d.pois||[])}catch(e){setErr(errorText(e, getLang()))}finally{setLoading(false)}},[lang]);
 useEffect(()=>{load()},[load]);useEffect(()=>{if(!navigator.geolocation){setGpsFailed(true);setGpsMsg('gpsUnsupported');return}const id=navigator.geolocation.watchPosition(p=>{setGpsPos([p.coords.latitude,p.coords.longitude]);setGpsFailed(false);setManualId('');setGpsMsg('gpsOk')},()=>{setGpsFailed(true);setGpsMsg('gpsFail')},{enableHighAccuracy:true,maximumAge:10000});return()=>navigator.geolocation.clearWatch(id)},[]);
 const filtered=useMemo(()=>pois.filter(p=>{const n=(poiName(p,lang)).toLowerCase();return n.includes(query.toLowerCase())}),[pois,query,lang]);
 const spotOptions=useMemo(()=>[...pois].sort((a,b)=>a.id==='tcv-001'?-1:b.id==='tcv-001'?1:(a.translations?.vi?.name||a.name||'').localeCompare(b.translations?.vi?.name||b.name||'','vi')),[pois,lang]);
 const manualPoi=pois.find(p=>p.id===manualId);
 const manualPos:[number,number]|null=manualPoi?[manualPoi.lat,manualPoi.lon]:null;
 // Vị trí chọn tay chỉ sống trong GuestHome: không lưu localStorage/URL và PoiDetail không đọc được, nên không gửi enter/exit.
 const pos=gpsPos||manualPos,usingManual=!gpsPos&&!!manualPos;
 const dest=pois.find(p=>p.id===destId);
 const findNearby=async()=>{if(!pos){setGpsMsg('gpsNeed');return}try{const d:any=await contentApi.nearby(pos[0],pos[1],radius==='all'?100000:Number(radius));setNearby((d.pois||[]).map((n:POI)=>({...pois.find((x:POI)=>x.id===n.id),...n,translations:n.translations||pois.find((x:POI)=>x.id===n.id)?.translations})));setTab('list')}catch(e){setErr(errorText(e, getLang()))}};
 
 return <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/><main className="guest-wrap"><section className="hero"><div className="hero-copy"><span className="eyebrow"><Leaf size={15}/> {T('eyebrow',lang)}</span><h1>{labels[lang].heroTitle1}<br/><em>{labels[lang].heroTitle2}</em></h1><p>{labels[lang].heroDesc}</p><div className="hero-actions"><button className="btn btn-primary" onClick={()=>{setTab('list');document.getElementById('explore')?.scrollIntoView({behavior:'smooth'})}}>{labels[lang].explore} <MapPin size={17}/></button><button className="btn btn-outline" onClick={()=>void openTicket()}><Ticket size={17}/> {labels[lang].myTicket}</button></div></div><div className="hero-art"><span>🌿</span><div className="hero-animal">🦒</div><span>🍃</span></div></section><section className="info-grid"><article className="info-card"><span className="info-icon">☀️</span><div><b>{T('openHours',lang)}</b><p>{T('openHoursNote',lang)}</p></div></article><article className="info-card"><span className="info-icon">📍</span><div><b>{T('address',lang)}</b><p>2 Nguyễn Bỉnh Khiêm, Quận 1, TP.HCM</p></div></article><article className="info-card"><span className="info-icon">🌱</span><div><b>{T('about',lang)}</b><p>{T('aboutNote',lang)}</p></div></article></section><section id="explore" className="explore"><div className="section-heading"><div><span className="eyebrow">{T('mapEyebrow',lang)}</span><h2>{T('whereNext',lang)}</h2><p>{T('whereNextDesc',lang)}</p></div><div className="locate-actions">{(gpsFailed||manualId)&&<select aria-label={T('ariaIAmAt',lang)} value={manualId} onChange={e=>setManualId(e.target.value)}><option value="">{T('iAmAt',lang)}</option>{spotOptions.map(p=><option key={p.id} value={p.id}>{poiName(p,lang)}</option>)}</select>}<button className="btn btn-outline" onClick={()=>void findNearby()}><LocateFixed size={17}/> {labels[lang].nearMe}</button></div></div><div className="search-row"><div className="searchbox"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder={labels[lang].searchPh} aria-label={labels[lang].searchPh}/></div><select aria-label={T('ariaDest',lang)} value={destId} onChange={e=>{setDestId(e.target.value);setTab('map')}}><option value="">{T('chooseDest',lang)}</option>{spotOptions.map(p=><option key={p.id} value={p.id}>{poiName(p,lang)}</option>)}</select><select aria-label={T('ariaRadius',lang)} value={radius} onChange={e=>setRadius(e.target.value)}><option value="100">{T('r100',lang)}</option><option value="300">{T('r300',lang)}</option><option value="500">{T('r500',lang)}</option><option value="all">{T('all',lang)}</option></select></div>{gpsMsg&&<p className="gps-note"><LocateFixed size={15}/>{T(gpsMsg,lang)}</p>}{usingManual&&<p className="gps-note"><MapPin size={15}/>{T('yourPos',lang)}: <b>{manualPoi?poiName(manualPoi,lang):''}</b>. {T('manualNote',lang)}</p>}{dest&&<><PoiCard poi={{...dest,distance_m:pos?distanceM(pos,[dest.lat,dest.lon]):undefined}}/>{!pos&&<p className="gps-note">{T('needGps',lang)}</p>}</>}<div className="tabs"><button className={tab==='map'?'active':''} onClick={()=>setTab('map')}>{T('tabMap',lang)}</button><button className={tab==='list'?'active':''} onClick={()=>setTab('list')}>{T('tabList',lang)} {nearby?`(${nearby.length})`:''}</button></div>{err&&<div className="notice error"><AlertCircle size={18}/>{err}<button onClick={()=>void load()}>{T('retry',lang)}</button></div>}{loading?<div className="skeleton large"/>:<div className="explore-content">{tab==='map'?<MapView pois={filtered} position={pos} manual={usingManual} focus={dest?[dest.lat,dest.lon]:null}/>:<div className="poi-list">{(nearby||filtered).filter(p=>!query||(poiName(p,lang)).toLowerCase().includes(query.toLowerCase())).map(p=><PoiCard key={p.id} poi={p}/>)}</div>}{tab==='map'&&<div className="poi-list map-list">{filtered.slice(0,5).map(p=><PoiCard key={p.id} poi={p}/>)}</div>}{!filtered.length&&<div className="empty"><PawPrint/><b>{T('noResults',lang)}</b><span>{T('noResultsHint',lang)}</span></div>}</div>}</section><footer>{T('footer',lang)}</footer></main>{ticketModal}</>}
function PoiCard({poi:p}:{poi:POI}){const [lang]=useLang();return <Link className="poi-card" to={`/poi/${p.id}`}><div className="poi-thumb">{p.image_url?<img src={p.image_url} alt={poiName(p,lang)} onError={e=>{e.currentTarget.style.display='none'}}/>:<span>{p.category==='chim'?'🐦':p.category==='thu_an_thit'?'🦁':p.category==='thu_an_co'?'🦒':p.category==='bo_sat_luong_cu'?'🐢':'🌿'}</span>}</div><div className="poi-card-copy"><span className="category">{catName(p.category,lang)}</span><b>{poiName(p,lang)}</b><p>{poiDesc(p,lang)||T('exploreThis',lang)}</p>{p.distance_m!==undefined&&<small><MapPin size={13}/>{p.distance_m<1000?`${Math.round(p.distance_m)} m`:`${(p.distance_m/1000).toFixed(1)} km`}</small>}</div><span className="arrow">↗</span></Link>}
function QrScanner({
  onDetected,
  onClose,
}: {
  onDetected: (text: string) => void;
  onClose: () => void;
}) {
  const [lang] = useLang();
  const [errorKey, setErrorKey] = useState('');
  const [starting, setStarting] = useState(true);

  useEffect(() => {
    let disposed = false;
    let handled = false;
    let started = false;
    let scanner: Html5Qrcode | null = null;

    const stopScanner = async () => {
      if (!scanner) return;
      if (started) {
        try {
          await scanner.stop();
        } catch {
          // Camera may already have stopped.
        } finally {
          started = false;
        }
      }
      try {
        scanner.clear();
      } catch {
        // The scan region may already be cleared.
      }
    };

    const startScanner = async () => {
      const ua = navigator.userAgent;
      const embeddedBrowser =
        /\bZalo\b/i.test(ua) ||
        /\bFBAN\b|\bFBAV\b|\bFB_IAB\b/i.test(ua) ||
        /\bInstagram\b/i.test(ua);

      if (embeddedBrowser) {
        setErrorKey('scanErrEmbedded');
        setStarting(false);
        return;
      }

      if (!window.isSecureContext) {
        setErrorKey('scanErrHttps');
        setStarting(false);
        return;
      }

      if (!navigator.mediaDevices?.getUserMedia) {
        setErrorKey('scanErrUnsupported');
        setStarting(false);
        return;
      }

      try {
        scanner = new Html5Qrcode('activate-qr-reader');
        await scanner.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 250, height: 250 } },
          (decodedText: string) => {
            if (handled || disposed) return;
            handled = true;
            onDetected(decodedText);
          },
          () => {
            // A frame without a QR code is normal; keep scanning.
          },
        );

        started = true;
        if (disposed) {
          await stopScanner();
          return;
        }
        setStarting(false);
      } catch {
        if (!disposed) {
          setErrorKey('scanErrOpen');
          setStarting(false);
        }
        await stopScanner();
      }
    };

    void startScanner();
    return () => {
      disposed = true;
      void stopScanner();
    };
  }, [onDetected]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        className="modal qr-scan-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="qr-scan-title"
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(100% - 24px, 480px)', maxHeight: '90dvh', overflowY: 'auto' }}
      >
        <button type="button" className="close" aria-label={T('scanCloseAria', lang)} onClick={onClose}>
          <X />
        </button>
        <h2 id="qr-scan-title">{T('scanTitle', lang)}</h2>
        <p>{T('scanHint', lang)}</p>
        <div id="activate-qr-reader" style={{ width: '100%', margin: '16px 0', overflow: 'hidden', borderRadius: 12 }} />
        {starting && !errorKey && <p>{T('scanStarting', lang)}</p>}
        {errorKey && <div className="notice error" role="alert">{T(errorKey, lang)}</div>}
        <button type="button" className="btn btn-outline full" onClick={onClose}>
          {T('scanClose', lang)}
        </button>
      </section>
    </div>
  );
}

function extractTicketCode(raw: string): string | null {
  const value = raw.trim();

  // QR may contain an absolute URL or a relative /activate?code=... link.
  if (/^(https?:\/\/|\/activate(?:\?|$))/i.test(value)) {
    try {
      const url = new URL(value, window.location.origin);
      if (url.pathname.replace(/\/+$/, '') !== '/activate') return null;
      const code = url.searchParams.get('code');
      if (!code) return null;
      return extractTicketCode(code);
    } catch {
      return null;
    }
  }

  const code = value.replace(/\s/g, '').toUpperCase();
  // Ticket codes use at least one hyphen, e.g. TCV-ABC123.
  if (!/^[A-Z0-9]+(?:-[A-Z0-9]+)+$/.test(code)) return null;
  return code;
}
function Activate({ticket}:{ticket:ReturnType<typeof useTicket>}){
 const [lang]=useLang();const {onHeaderTicket,ticketModal}=useTicketModal(ticket);const [params]=useSearchParams(),[code,setCode]=useState((params.get('code')||'').replace(/\s/g,'').toUpperCase()),[busy,setBusy]=useState(false),[err,setErr]=useState(''),[confirm,setConfirm]=useState(false),[replaceAsk,setReplaceAsk]=useState(false),[success,setSuccess]=useState(false),[expiry,setExpiry]=useState('');const nav=useNavigate();
const [scanOpen, setScanOpen] = useState(false);
const [scanError, setScanError] = useState('');

const handleQrDetected = useCallback((raw: string) => {
  const extracted = extractTicketCode(raw);

  if (!extracted) {
    setScanError('scanInvalid');
    setScanOpen(false);
    return;
  }

  setCode(extracted);
  setErr('');
  setScanError('');
  setScanOpen(false);
}, []);
const submit = async (
  switchDevice = false,
  skipReplaceAsk = false
) => {
  if (ticket.valid && !skipReplaceAsk) {
    setReplaceAsk(true);
    return;
  }

  setBusy(true);setErr('');try{const d:any=await authApi.activate({code:code.replace(/\s/g,'').toUpperCase(),device_id:deviceId(),confirm_device_switch:switchDevice});ticket.save(d.ticket_token||d.token,d.expires_at);setExpiry(d.expires_at||'');setSuccess(true);setConfirm(false)}catch(e:any){if(e instanceof ApiError&&e.status===409&&(e.code==='used_on_other_device'||String(e.message).includes('confirm_required'))){setConfirm(true)}else if(e instanceof ApiError&&e.status===404)setErr('errTicketInvalid');else if(e instanceof ApiError&&e.status===410)setErr('errTicketExpired');else if(e instanceof ApiError&&e.status===429)setErr('errTooMany');else setErr(errorText(e, getLang()))}finally{setBusy(false)}};useEffect(()=>{if(params.get('code'))void submit(false)},[]);return <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/>{ticketModal}<main className="auth-page"><Link to="/" className="back-link">{T('backHome',lang)}</Link><section className="auth-card"><div className="auth-illustration">🎟️<span>🌿</span></div>{success?<><div className="success-round"><CheckCircle/></div><h1>{T('successTitle',lang)}</h1><p>{T('successDesc',lang)}</p>{expiry&&<p>{T('expires',lang)} <b>{fmtDate(expiry,lang)}</b></p>}<button className="btn btn-primary full" onClick={()=>nav('/')}>{T('goHome',lang)}</button><button className="btn btn-outline full" onClick={()=>nav('/poi/tcv-001')}>{T('goListen',lang)}</button></>:<><span className="eyebrow">{T('unlockEyebrow',lang)}</span><h1>{T('activateTitle',lang)}</h1><p>{T('activateDesc',lang)}</p><label htmlFor="ticket-code">{T('ticketCode',lang)}</label><input id="ticket-code" className="field code-field" value={code} onChange={e=>setCode(e.target.value.replace(/\s/g,'').toUpperCase())} placeholder={T('ticketCodePh',lang)} autoComplete="off"/><button type="button" className="btn btn-outline full" onClick={()=>{setScanError('');setScanOpen(true)}}><Camera size={17}/> {T('scanQr',lang)}</button>{scanError&&<div className="notice error" role="alert"><AlertCircle/>{T(scanError,lang)}</div>}{err&&<div className="notice error"><AlertCircle/>{T(err,lang)}<button onClick={()=>void submit(false,true)}>{T('retry',lang)}</button></div>}<button className="btn btn-primary full" disabled={busy||!code.trim()} onClick={()=>void submit()}>{busy?T('activating',lang):labels[lang].activate}</button><p className="fine-print"><LockKeyhole size={14}/> {T('oneDeviceNote',lang)}</p></>}</section></main>{confirm&&<div className="modal-backdrop"><section className="modal"><h2>{T('switchTitle',lang)}</h2><p>{T('switchDesc',lang)}</p><div className="modal-actions"><button className="btn btn-outline" onClick={()=>setConfirm(false)}>{T('cancel',lang)}</button><button className="btn btn-primary" onClick={()=>void submit(true,true)}>{T('confirmSwitch',lang)}</button></div></section></div>}
{replaceAsk && (
  <div className="modal-backdrop">
    <section className="modal">
      <h2>{T('replaceTitle',lang)}</h2>
      <p>
        {T('replaceDesc',lang).replace('{date}',fmtDate(ticket.expiry,lang))}
      </p>
      <div className="modal-actions">
        <button
          className="btn btn-outline"
          onClick={() => setReplaceAsk(false)}
        >
          {T('cancel',lang)}
        </button>
        <button
          className="btn btn-primary"
          onClick={() => {
            setReplaceAsk(false);
            void submit(false, true);
          }}
        >
          {T('confirmReplace',lang)}
        </button>
      </div>
    </section>
  </div>
)}
{scanOpen && <QrScanner onDetected={handleQrDetected} onClose={() => setScanOpen(false)} />}
</>}
function AudioPlayer({id,lang,token,onUnauthorized,onListen}:{id:string;lang:Lang;token:string;onUnauthorized:()=>void;onListen:()=>void}){const [url,setUrl]=useState(''),[busy,setBusy]=useState(false),[err,setErr]=useState(''),[playing,setPlaying]=useState(false),[progress,setProgress]=useState(0),[duration,setDuration]=useState(0);const ref=useRef<HTMLAudioElement>(null);const urlRef=useRef('');useEffect(()=>{let cancelled=false;const run=async()=>{setBusy(true);setErr('');try{const blob=await audioApi.visitor(id,lang,token);if(cancelled)return;const next=URL.createObjectURL(blob);if(urlRef.current)URL.revokeObjectURL(urlRef.current);urlRef.current=next;setUrl(next);}catch(e:any){if(cancelled)return;if (e instanceof ApiError && e.status === 401) {
  onUnauthorized();
}else if(e instanceof ApiError&&e.status===502)setErr(T('audioErr502',lang));else setErr(errorText(e, getLang()))}finally{if(!cancelled)setBusy(false)}};void run();return()=>{cancelled=true;if(urlRef.current){URL.revokeObjectURL(urlRef.current);urlRef.current=''}};},[id,lang,token]);const reload=useCallback(()=>{if(urlRef.current){URL.revokeObjectURL(urlRef.current);urlRef.current=''}setUrl('');setBusy(true);setErr('');audioApi.visitor(id,lang,token).then(blob=>{const next=URL.createObjectURL(blob);urlRef.current=next;setUrl(next)}).catch((e:any)=>{if(e instanceof ApiError&&e.status===401){onUnauthorized();}else if(e instanceof ApiError&&e.status===502)setErr(T('audioErr502',lang));else setErr(errorText(e, getLang()))}).finally(()=>setBusy(false))},[id,lang,token,onUnauthorized]);useEffect(()=>{if(playing)onListen()},[playing]);return <div className="audio-box"><div className="audio-icon"><Volume2/></div><div className="audio-main"><b>{T('audioTitle',lang)}</b><p>{busy?T('audioPreparing',lang):err||T('audioReady',lang)}</p>{url&&<audio ref={ref} src={url} controls onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onTimeUpdate={e=>setProgress(e.currentTarget.currentTime)} onLoadedMetadata={e=>setDuration(e.currentTarget.duration)}/>}<div className="audio-meta">{duration?`${Math.floor(progress/60)}:${String(Math.floor(progress%60)).padStart(2,'0')} / ${Math.floor(duration/60)}:${String(Math.floor(duration%60)).padStart(2,'0')}`:T('audioHint',lang)}</div>{(busy||err)&&<button className="btn btn-outline" onClick={reload} disabled={busy}>{busy?T('loading',lang):T('retry',lang)}</button>}</div></div>}
function PoiDetail({ticket}:{ticket:ReturnType<typeof useTicket>}){
 const {onHeaderTicket,ticketModal}=useTicketModal(ticket);
 const [lang]=useLang();
 const {id=''}=useParams(),nav=useNavigate();
 const [poi,setPoi]=useState<POI|null>(null),[err,setErr]=useState(''),[loading,setLoading]=useState(true);
 const [pos,setPos]=useState<[number,number]|null>(null);
 const [gpsReal,setGpsReal]=useState(false); // true khi GPS thật (không phải chọn thủ công)

 useEffect(()=>{setLoading(true);setErr('');contentApi.poi(id).then((d:any)=>setPoi(d.poi||d)).catch(e=>setErr(errorText(e, getLang()))).finally(()=>setLoading(false))},[id,lang]);

 useEffect(()=>{
   if(!navigator.geolocation)return;
   const w=navigator.geolocation.watchPosition(
     p=>{setPos([p.coords.latitude,p.coords.longitude]);setGpsReal(true);},
     ()=>{setGpsReal(false);},
     {enableHighAccuracy:true,maximumAge:10000}
   );
   return()=>navigator.geolocation.clearWatch(w);
 },[]);

 // Lệnh 4: sendEvent trả boolean; chỉ ghi key sau khi gửi thành công
 const insideKeyRef = useRef('');
 const sendEvent = useCallback(async(type:string, currentPos?:[number,number]|null):Promise<boolean>=>{
   if(!ticket.valid||!ticket.token) return false;
   if(!gpsReal) return false; // không gửi khi chọn vị trí thủ công
   const p = currentPos ?? pos;
   try{
     await contentApi.sendEvent(
       {poi_id:id, type, ...(p?{lat:p[0],lon:p[1]}:{})},
       ticket.token
     );
     return true;
   } catch(e:any){
     if(e instanceof ApiError){
       if(e.status===401){ticket.handleError(e);return false;}
       if(e.status===422) return false; // out_of_range: không retry
       if(e.status===429){
         const wait=(e.retryAfter||5)*1000;
         await new Promise(r=>setTimeout(r,wait));
         return false; // không retry vòng lặp; caller có thể thử lại lần sau
       }
     }
     console.warn('sendEvent failed',e);
     return false;
   }
 },[id,pos,gpsReal,ticket]);

 // Lệnh 4: tính ngày VN cho key
 const todayVN=()=>new Date().toLocaleDateString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}).replace(/\//g,'-');
 const insideKey=()=>`zoo_inside_${ticket.token?.slice(-8)||'anon'}_${todayVN()}_${id}`;

 // Lệnh 4: enter/exit dựa trên GPS thật + ticket.valid
 useEffect(()=>{
   if(!poi||!pos||!ticket.valid||!gpsReal)return;
   const d=Math.hypot((pos[0]-poi.lat)*111000,(pos[1]-poi.lon)*111000*Math.cos(pos[0]*Math.PI/180));
   const inside=d<=(poi.radius_m||30);
   const key=insideKey();
   const was=safeGet(key)==='true';
   if(inside!==was){
     if(inside){
       // Ghi key CHỈ sau khi gửi thành công
       sendEvent('enter',pos).then(ok=>{
         if(ok){safeSet(key,'true');insideKeyRef.current=key;}
       });
     } else {
       const prevKey=insideKeyRef.current||key;
       sendEvent('exit',pos).then(ok=>{
         if(ok) safeRemove(prevKey);
         else safeRemove(prevKey); // dù thất bại vẫn clear để tránh stale
         insideKeyRef.current='';
       });
     }
   } else if(inside && !insideKeyRef.current){
     insideKeyRef.current=key; // đồng bộ ref khi mount vào trang đang inside
   }
 },[poi,pos,ticket.valid,gpsReal]);

 // Lệnh 4: cleanup exit khi unmount (đổi POI) + pagehide (đóng tab)
 useEffect(()=>{
   const sendExitBeacon=()=>{
     if(!insideKeyRef.current||!ticket.valid||!ticket.token) return;
     const base=(import.meta.env.VITE_API_BASE_URL||'').replace(/\/$/,'');
     const url=`${base}/api/content/events`;
     const body=JSON.stringify({poi_id:id,type:'exit',...(pos?{lat:pos[0],lon:pos[1]}:{})});
     // keepalive để gửi khi tab đóng
     void fetch(url,{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','Authorization':`Bearer ${ticket.token}`},body});
     safeRemove(insideKeyRef.current);
     insideKeyRef.current='';
   };
   const onPageHide=()=>sendExitBeacon();
   window.addEventListener('pagehide',onPageHide);
   return()=>{
     window.removeEventListener('pagehide',onPageHide);
     // cleanup khi rời trang / đổi POI
     if(insideKeyRef.current&&ticket.valid){
       sendExitBeacon();
     }
   };
 },[id,ticket.token,ticket.valid,pos]);


 if(loading) return (
   <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/>{ticketModal}<main className="detail-wrap"><div className="skeleton large"/></main></>
 );
 const tr=poi?.translations?.[lang];
 const title=tr?.name||poi?.translations?.en?.name||poi?.translations?.vi?.name||poi?.name||id;
 const poiContent = poi ? (
   <>
     <div className="detail-hero">
       <div className="detail-photo">
         {poi.image_url
           ? <img src={poi.image_url} alt={title} onError={e=>{e.currentTarget.style.display='none'}}/>
           : <div className="photo-placeholder"><span>🌳</span><span>🦜</span><small>{T('photoTag',lang)}</small></div>
         }
       </div>
       <div className="detail-copy">
         <span className="category">{catName(poi.category,lang)}</span>
         <h1>{title}</h1>
         {poi.species_name && <p className="species">{poi.species_name}</p>}
       </div>
     </div>
     <section className="description-panel">
       <h2>{labels[lang].description}</h2>
       <p>{tr?.description||poi?.translations?.en?.description||poi?.translations?.vi?.description||poi?.description||T('noDesc',lang)}</p>
     </section>
     {ticket.valid
       ? <AudioPlayer key={`${id}-${lang}`} id={id} lang={lang} token={ticket.token} onUnauthorized={()=>ticket.expire()} onListen={()=>void sendEvent('listen')}/>
       : <div className="locked-panel">
           <div className="lock-circle"><LockKeyhole/></div>
           <div>
             <b>{labels[lang].listen}</b>
             <p>{T('lockedHint',lang)}</p>
             <Link to="/activate" className="text-link">{T('lockedLink',lang)}</Link>
           </div>
           <LockKeyhole className="lock-end"/>
         </div>
     }
   </>
 ) : null;
 return (
   <><Header hasTicket={ticket.valid} onTicket={onHeaderTicket}/>{ticketModal}
     <main className="detail-wrap">
       <Link className="back-link" to="/">← {T('backAll',lang)}</Link>
       {err ? <div className="notice error">{err}</div> : poiContent}
     </main>
   </>
 );
}
function StaffLogin({staff}:{staff:ReturnType<typeof useStaff>}){const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[err,setErr]=useState(''),[busy,setBusy]=useState(false),nav=useNavigate();const submit=async(e:any)=>{e.preventDefault();setBusy(true);setErr('');try{const d:any=await authApi.login({username,password});const user={username:d.username||username,role:d.role};staff.login(d.token,user);nav(user.role==='counter'?'/staff/tickets':'/staff/dashboard')}catch(e:any){setErr(e instanceof ApiError&&e.status===401?'Sai tên đăng nhập hoặc mật khẩu.':e instanceof ApiError&&e.status===403?'Tài khoản đã bị khóa.':errorText(e, getLang()))}finally{setBusy(false)}};return <main className="login-layout"><div className="login-art"><Leaf size={45}/><h1>Thiên nhiên<br/>trong tầm tay.</h1><p>Hệ thống quản lý thuyết minh đa ngôn ngữ<br/>Thảo Cầm Viên Sài Gòn</p><div className="login-leaves">🌿 🦜 🌱</div></div><form className="login-form" onSubmit={submit}><span className="eyebrow">CỔNG QUẢN TRỊ</span><h2>Chào mừng trở lại</h2><p>Đăng nhập để tiếp tục công việc của bạn.</p><label htmlFor="username">Tên đăng nhập</label><input id="username" className="field" value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" required/><label htmlFor="password">Mật khẩu</label><input id="password" className="field" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required/>{err&&<div className="notice error">{err}</div>}<button className="btn btn-primary full" disabled={busy}>{busy?'Đang đăng nhập…':'Đăng nhập'}</button>{import.meta.env.DEV&&<div className="demo-hint"><b>Tài khoản demo</b><br/>Admin: admin / admin123<br/>Quầy vé: counter01 / counter123</div>}<Link to="/" className="back-link">← Về trang du khách</Link></form></main>}

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

  setErr(errorText(e, getLang()));
}

function StaffLayout({staff,children,adminOnly=false}:{staff:ReturnType<typeof useStaff>;children:any;adminOnly?:boolean}){const nav=useNavigate();if(!staff.token||!staff.user)return <Navigate to="/staff" replace/>;if(adminOnly&&staff.user.role!=='admin')return <Navigate to="/staff/tickets" replace/>;const links=[
  {to:'/staff/dashboard',label:'Dashboard',icon:LayoutDashboard,roles:['admin']},
  {to:'/staff/accounts',label:'Tài khoản',icon:Users,roles:['admin']},
  {to:'/staff/tickets',label:'Quản lý vé',icon:Ticket,roles:['admin','counter']},
  {to:'/staff/pois',label:'Điểm tham quan',icon:MapPin,roles:['admin']},
];return <div className="staff-shell"><aside className="sidebar"><Link to="/" className="staff-brand"><Leaf/><span><b>ZooGuide</b><small>Quản trị hệ thống</small></span></Link><div className="side-caption">MENU CHÍNH</div>{links.filter(l=>l.roles.includes(staff.user.role)).map(l=><Link key={l.to} to={l.to} className="side-link"><l.icon size={18}/>{l.label}</Link>)}<div className="sidebar-bottom"><div className="user-avatar">{staff.user.username?.slice(0,1).toUpperCase()}</div><div className="user-info"><b>{staff.user.username}</b><small>{staff.user.role==='admin'?'Quản trị viên':'Nhân viên quầy vé'}</small></div><button title="Đăng xuất" onClick={()=>{staff.logout();nav('/staff')}}><LogOut/></button></div></aside><section className="staff-main"><header className="staff-top"><span>Thảo Cầm Viên Sài Gòn <span className="crumb">/ Không gian làm việc</span></span><span className="online-dot">● Đang hoạt động</span></header><div className="staff-content">{children}</div></section></div>}
function PageTitle({eyebrow,title,desc,action}:{eyebrow:string;title:string;desc:string;action?:any}){return <div className="page-title"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{desc}</p></div>{action}</div>}

function StaffTickets({staff}:{staff:ReturnType<typeof useStaff>}){
  const nav=useNavigate();

  const [tickets,setTickets]=useState<any[]>([]);
  const [created,setCreated]=useState<any>(null);
  const [copied,setCopied]=useState(false);
  const [err,setErr]=useState('');
  const [busy,setBusy]=useState(false);

  // Tải danh sách vé
  const load=useCallback(async()=>{
    try{
      const d:any=await authApi.tickets(staff.token);
      setTickets(d.tickets||d.items||d||[]);
      setErr('');
    }catch(e){
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
      const base = (
          import.meta.env.VITE_PUBLIC_BASE_URL || location.origin
        ).replace(/\/$/, '');

    const activation_url =
        `${base}/activate?code=${encodeURIComponent(code || '')}`;

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
                setCopied(true);
                setTimeout(()=>setCopied(false),2000);
              }}
            >
              {copied?<CheckCircle size={16}/>:<Copy size={16}/>}
              {copied?'Đã sao chép!':'Sao chép mã vé'}
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
            <small className="qr-url">{created.activation_url}</small>  
            {qrWarning(created.activation_url) && (
              <div className="notice warn">
                {qrWarning(created.activation_url)}
              </div>
            )}
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
      if(e instanceof ApiError&&e.status===401){
        onUnauthorized();
      }else{
        setErr(errorText(e, getLang()));
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
      if(e instanceof ApiError&&e.status===401){
        onUnauthorized();
      }else{
        setErr(errorText(e, getLang()));
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
      setErr(errorText(e, getLang()));
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
                      {catName(p.category,'vi')}
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

export default function App() {
  const [lang] = useLang();
  const ticket = useTicket();
  const staff = useStaff();

  return (
    <>
      {/* Thông báo khi vé hết hạn hoặc bị chuyển sang thiết bị khác */}
      {ticket.notice && (
        <div className="notice warn ticket-notice">
          {T(ticket.notice, lang)}{' '}
          <Link to="/activate">{T('enterCode', lang)}</Link>
          <button aria-label={T('closeNotice', lang)} onClick={ticket.dismissNotice}>×</button>
        </div>
      )}

      <Routes>
        <Route path="/" element={<GuestHome ticket={ticket} />} />

        <Route
          path="/poi/:id"
          element={<PoiDetail ticket={ticket} />}
        />

        <Route
          path="/activate"
          element={<Activate ticket={ticket} />}
        />

        <Route
          path="/staff"
          element={
            staff.token ? (
              <Navigate
                to={
                  staff.user?.role === 'counter'
                    ? '/staff/tickets'
                    : '/staff/dashboard'
                }
              />
            ) : (
              <StaffLogin staff={staff} />
            )
          }
        />

        <Route
          path="/staff/tickets"
          element={
            <StaffLayout staff={staff}>
              <StaffTickets staff={staff} />
            </StaffLayout>
          }
        />

        <Route
          path="/staff/dashboard"
          element={
            <StaffLayout staff={staff} adminOnly>
              <Dashboard staff={staff} />
            </StaffLayout>
          }
        />

        <Route
          path="/staff/pois"
          element={
            <StaffLayout staff={staff} adminOnly>
              <StaffPois staff={staff} />
            </StaffLayout>
          }
        />

        <Route
          path="/staff/accounts"
          element={
            <StaffLayout staff={staff} adminOnly>
              <Accounts staff={staff} />
            </StaffLayout>
          }
        />

        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />
      </Routes>
    </>
  );
}