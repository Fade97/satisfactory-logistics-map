// Fuzzy search for item/station names: tolerates typos, omissions and German terms.
//
// Scoring (higher = better):
//   exact match > prefix > word prefix > substring > letters in order (subsequence)
//   > typos (Damerau-Levenshtein per word, ≤ 1 error up to 4 chars, ≤ 2 above).
// German search terms are mapped to the English game names ("Eisen" → Iron, "Kupfer" → Copper).

const GERMAN_WORDS: Record<string, string> = {
  eisen: 'iron', kupferdraht: 'wire', kupferkabel: 'cable', kupfer: 'copper', stahl: 'steel', kohle: 'coal', kalk: 'limestone', kalkstein: 'limestone',
  quarz: 'quartz', schwefel: 'sulfur', bauxit: 'bauxite', uran: 'uranium', wasser: 'water', oel: 'oil', öl: 'oil',
  rohoel: 'crude oil', rohöl: 'crude oil', erz: 'ore', barren: 'ingot', platte: 'plate', stange: 'rod', schraube: 'screw',
  schrauben: 'screw', draht: 'wire', kabel: 'cable', beton: 'concrete', kunststoff: 'plastic', plastik: 'plastic',
  gummi: 'rubber', rotor: 'rotor', motor: 'motor', rahmen: 'frame', rohr: 'pipe', träger: 'beam', traeger: 'beam',
  treibstoff: 'fuel', kraftstoff: 'fuel', stickstoff: 'nitrogen', aluminium: 'aluminum', gold: 'caterium',
  caterium: 'caterium', silizium: 'silica', kristall: 'crystal', batterie: 'battery', computer: 'computer',
  schaltkreis: 'circuit', platine: 'circuit board', blech: 'sheet', verstärkt: 'reinforced', verstaerkt: 'reinforced',
  schwer: 'heavy', modular: 'modular', supercomputer: 'supercomputer', zement: 'concrete', harz: 'resin', säure: 'acid', saeure: 'acid', verpackt: 'packaged',
};

export function norm(s: string) {
  // ä→ae etc., so "Träger" and "Traeger" are treated the same; strip remaining accents
  return s.toLowerCase().replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
    .normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
}
// Dictionary in the same normal form; also covers common endings (-e, -en, -er, -es …)
const NORM_WORDS: Record<string, string> = {};
for (const [k, v] of Object.entries(GERMAN_WORDS)) {
  // recognise both "traeger" and "trager" (umlaut typed without e)
  for (const n of new Set([norm(k), norm(k).replace(/ae/g, 'a').replace(/oe/g, 'o').replace(/ue/g, 'u')])) {
    NORM_WORDS[n] ??= v;
    for (const suf of ['e', 'en', 'er', 'es', 'te', 'ter']) NORM_WORDS[n + suf] ??= v;
  }
}

/** German → game name; compounds like "Stahlträger" or "Kupferdraht" are split into known parts. */
function translate(q: string) {
  const KEYS = Object.keys(NORM_WORDS).sort((a, b) => b.length - a.length);
  const split = (w: string): string[] | null => {
    if (!w) return [];
    if (NORM_WORDS[w]) return [NORM_WORDS[w]];
    for (const k of KEYS) if (w.startsWith(k) && k.length >= 3) {
      const rest = split(w.slice(k.length).replace(/^s(?=[a-z]{3})/, ''));   // linking 's' (Fugen-s)
      if (rest) return [NORM_WORDS[k], ...rest];
    }
    // remainder with one typo ("tager" → "traeger"): only for remainders of 5+ chars
    if (w.length >= 5) for (const k of KEYS) if (k.length >= 5 && dist(w, k, 1) <= 1) return [NORM_WORDS[k]];
    return null;
  };
  return q.split(' ').map(w => (split(w) || [w]).join(' ')).join(' ');
}

/** Damerau-Levenshtein (optimal string alignment), bails out above `max`. */
function dist(a: string, b: string, max: number) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  const d: number[][] = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    let rowMin = Infinity;
    for (let j = 1; j <= b.length; j++) {
      const c = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
      rowMin = Math.min(rowMin, d[i][j]);
    }
    if (rowMin > max) return max + 1;
  }
  return d[a.length][b.length];
}

function subseq(q: string, t: string) {
  let i = 0;
  for (const ch of t) if (ch === q[i]) i++;
  return i === q.length;
}

/** Score of a candidate for the query; 0 = no match. */
export function score(query: string, text: string): number {
  const q0 = norm(query);
  if (!q0) return 1;
  const t = norm(text);
  let best = 0;
  for (const q of new Set([q0, translate(q0)])) {
    if (t === q) return 1000;
    if (t.startsWith(q)) best = Math.max(best, 900 - t.length);
    const words = t.split(' ');
    if (words.some(w => w.startsWith(q))) best = Math.max(best, 800 - t.length);
    if (t.includes(q)) best = Math.max(best, 700 - t.length);
    // all query words occur (fuzzily)
    const qw = q.split(' ');
    let ok = 0, err = 0;
    for (const w of qw) {
      if (words.some(x => x.startsWith(w))) { ok++; continue; }
      const lim = w.length <= 4 ? 1 : 2;
      const m = Math.min(...words.map(x => Math.min(dist(w, x, lim), dist(w, x.slice(0, w.length), lim))));
      if (m <= lim) { ok++; err += m; }
    }
    if (ok === qw.length) best = Math.max(best, 600 - err * 60 - t.length);
    // letters in order (abbreviations like "hmf"): only with the same first letter, otherwise almost anything matches
    if (q.length >= 3 && q[0] === t[0] && subseq(q.replace(/ /g, ''), t.replace(/ /g, ''))) best = Math.max(best, 300 - t.length);
    if (q.length >= 2 && q.length <= 5 && !q.includes(' ') && words.map(w => w[0]).join('').startsWith(q)) best = Math.max(best, 850);
  }
  return best;
}

/** Filters and sorts a list by relevance. */
export function fuzzy<T>(query: string, list: T[], key: (x: T) => string, limit = 50): T[] {
  if (!norm(query)) return list.slice(0, limit);
  return list.map(x => [x, score(query, key(x))] as const).filter(([, s]) => s > 0)
    .sort((a, b) => b[1] - a[1]).slice(0, limit).map(([x]) => x);
}

/** Does the text match the query? (for filtering lists) */
export const matches = (query: string, ...texts: (string | null | undefined)[]) =>
  !norm(query) || texts.some(t => t && score(query, t) > 0);
