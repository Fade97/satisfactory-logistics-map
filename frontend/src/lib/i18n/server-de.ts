// Backend-Texte (Englisch) → Deutsch über Musterpaare aus server-texts.json. Platzhalter {0} … fangen beliebigen Text;
// eingefangene Teile werden erneut übersetzt (z. B. der Fabrikname in „{0}: {1} of {2} machines missing input“).
// Dieselbe Datei nutzt das Backend einmalig, um ältere, noch deutsch gespeicherte Ereignisse auf Englisch umzustellen.
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
