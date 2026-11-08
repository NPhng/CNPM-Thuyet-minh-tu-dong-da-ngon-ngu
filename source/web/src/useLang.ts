import { useSyncExternalStore } from 'react';
import { languages, Lang } from './i18n';

const KEY = 'zoo_lang';

// ── In-memory fallback (private/incognito mode hoặc storage bị block) ──────
let mem: Lang = 'vi';

// ── Listener set ─────────────────────────────────────────────────────────────
const listeners = new Set<() => void>();

// ── Module-level, stable subscribe ───────────────────────────────────────────
const subscribe = (cb: () => void): (() => void) => {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
};

// ── Safe localStorage helpers ─────────────────────────────────────────────────
const readStorage = (): Lang | null => {
  try {
    return localStorage.getItem(KEY) as Lang | null;
  } catch {
    return null;
  }
};

const writeStorage = (l: Lang): void => {
  try {
    localStorage.setItem(KEY, l);
  } catch {
    // ignore – mem đã được cập nhật bên dưới
  }
};

// ── Sync <html lang> ──────────────────────────────────────────────────────────
const syncHtmlLang = (l: Lang): void => {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = l;
  }
};

// ── getSnapshot ───────────────────────────────────────────────────────────────
const getSnapshot = (): Lang => {
  const v = readStorage() ?? mem;
  return (languages as readonly string[]).includes(v) ? v : 'vi';
};

// ── getServerSnapshot ─────────────────────────────────────────────────────────
const getServerSnapshot = (): Lang => 'vi';

// ── Khởi tạo mem + <html lang> từ storage (một lần duy nhất) ─────────────────
mem = getSnapshot();
syncHtmlLang(mem);

// ── Cross-tab sync: lắng nghe storage event một lần ở module-level ───────────
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e: StorageEvent) => {
    if (e.key === KEY) {
      // Cập nhật mem để getSnapshot() nhất quán khi storage bị fallback
      const v = readStorage() ?? mem;
      mem = (languages as readonly string[]).includes(v) ? v : 'vi';
      listeners.forEach(f => f());
    }
  });
}

// ── Public API ────────────────────────────────────────────────────────────────
export const get = getSnapshot;
export const getLang = get;

export const setLang = (l: Lang): void => {
  if (l === getSnapshot()) return;   // bỏ qua nếu không đổi
  mem = l;
  writeStorage(l);
  syncHtmlLang(l);
  listeners.forEach(f => f());
};

export function useLang(): [Lang, (l: Lang) => void] {
  const lang = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return [lang, setLang];
}
