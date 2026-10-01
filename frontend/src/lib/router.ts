// Hash-Router: #/map?x=..&y=..&z=..&sel=kind:key · #/production · #/power · #/logistics · #/history · #/planner · #/kiosk
// Old German URLs (#/karte, ?ware=, ?folge= …) are rewritten to the English ones (backwards compatibility).
import { writable } from 'svelte/store';

export interface Route { page: string; q: URLSearchParams }
export const PAGE_ALIAS: Record<string, string> = {
  lage: 'overview', karte: 'map', produktion: 'production', strom: 'power', logistik: 'logistics', verlauf: 'history', rechner: 'planner',
};
const PARAM_ALIAS: Record<string, string> = { ware: 'item', folge: 'follow' };
function parse(): Route {
  const h = location.hash.replace(/^#\/?/, '');
  const [p, qs] = h.split('?');
  const q = new URLSearchParams(qs || '');
  for (const [de, en] of Object.entries(PARAM_ALIAS)) if (q.has(de) && !q.has(en)) { q.set(en, q.get(de)!); q.delete(de); }
  if (q.get('pick') === 'bauplatz') q.set('pick', 'site');
  return { page: PAGE_ALIAS[p] || p || 'overview', q };
}
export const route = writable<Route>(parse());
addEventListener('hashchange', () => route.set(parse()));

export function go(page: string, q: Record<string, string | number> = {}) {
  const s = new URLSearchParams(Object.entries(q).map(([k, v]) => [k, String(v)])).toString();
  location.hash = '#/' + page + (s ? '?' + s : '');
}
/** Jump the map to an object or a location */
export const toMap = (sel: string, x?: number, y?: number) =>
  go('map', { sel, ...(x !== undefined ? { x: Math.round(x), y: Math.round(y!), z: 1.5 } : {}) });

/** Update the address bar without a new history entry (map position). */
export function replaceQuery(page: string, q: Record<string, string>) {
  const s = new URLSearchParams(q).toString();
  history.replaceState(null, '', '#/' + page + (s ? '?' + s : ''));
}
