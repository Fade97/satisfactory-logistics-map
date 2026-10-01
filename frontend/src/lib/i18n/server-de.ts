// Backend texts (English) → German via pattern pairs from server-texts.json. Placeholders {0} … match any text;
// captured parts are translated again (e.g. the factory name in "{0}: {1} of {2} machines missing input").
// The backend uses the same file once to migrate older events still stored in German to English.
import PAIRS from './server-texts.json';

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const RULES = (PAIRS as [string, string][]).map(([en, de]) => ({
  re: new RegExp('^' + esc(en).replace(/\\\{(\d)\\\}/g, '(.+?)') + '$', 's'),
  order: [...en.matchAll(/\{(\d)\}/g)].map(m => +m[1]),
  de,
}));

export function serverText(s: string, depth = 0): string {
  if (!s || depth > 3) return s;
  for (const r of RULES) {
    const m = s.match(r.re);
    if (!m) continue;
    const val: Record<number, string> = {};
    r.order.forEach((n, i) => (val[n] = serverText(m[i + 1], depth + 1)));
    return r.de.replace(/\{(\d)\}/g, (_, n) => val[+n] ?? '');
  }
  return s;
}
