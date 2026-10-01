// Browser storage: all localStorage keys in one place, JSON reads that survive broken/foreign values.

export const KEYS = {
  prefs: 'fgmap.prefs', layers: 'fgmap.layers', site: 'fgmap.site', planner: 'fgmap.planner',
  plannerTargets: 'fgmap.plannerTargets', histItems: 'fgmap.histItems', lastVisit: 'fgmap.lastVisit',
  password: 'fgmap.pw', author: 'fgmap.author',
} as const;

const ls = () => (typeof localStorage !== 'undefined' ? localStorage : null);   // absent in tests (node)

/** Parsed JSON value, or `fallback` if missing or not parseable. */
export function loadJson<T>(key: string, fallback: T): T {
  try {
    const s = ls()?.getItem(key);
    return s == null ? fallback : (JSON.parse(s) ?? fallback);
  } catch { return fallback; }
}
export function saveJson(key: string, value: unknown) {
  try { ls()?.setItem(key, JSON.stringify(value)); } catch { /* quota / private mode */ }
}
