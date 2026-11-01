import {useSyncExternalStore} from 'react';
import {languages,Lang} from './i18n';

const KEY='zoo_lang';
const listeners=new Set<()=>void>();
const get=():Lang=>{
  const v=localStorage.getItem(KEY) as Lang;
  return (languages as readonly string[]).includes(v)?v:'vi';
};
export const setLang=(l:Lang)=>{localStorage.setItem(KEY,l);listeners.forEach(f=>f())};
export function useLang():[Lang,(l:Lang)=>void]{
  const lang=useSyncExternalStore(cb=>{listeners.add(cb);return()=>listeners.delete(cb)},get);
  return [lang,setLang];
}