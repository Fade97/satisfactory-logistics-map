// Übersetzung der Oberfläche. Schlüssel ist der deutsche Text (so bleibt der Quelltext lesbar und Deutsch vollständig);
// Englisch — die Standardsprache — kommt aus lib/i18n/en/*.ts. Fehlt ein Eintrag, meldet das tests/i18n.test.ts.
//
//   Vorlage:  {$t('Karte')}            Platzhalter:  $t('{n} Maschinen', { n: 5 })
//   Skript:   tr('Karte')              (nicht reaktiv; ein Sprachwechsel lädt die Seite neu)
import { derived, get } from 'svelte/store';
import { prefs } from './prefs';
import EN from './i18n/en';

export type Lang = 'en' | 'de';
export const lang = derived(prefs, p => (p.ui === 'de' ? 'de' : 'en') as Lang);
let cur: Lang = get(lang);
lang.subscribe(l => (cur = l));

export function translate(l: Lang, key: string, args?: Record<string, unknown>): string {
  let s = l === 'de' ? key : (EN[key] ?? key);
  if (args) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in args ? String(args[k]) : m));
  return s;
}
export const tr = (key: string, args?: Record<string, unknown>) => translate(cur, key, args);
export const t = derived(lang, l => (key: string, args?: Record<string, unknown>) => translate(l, key, args));
/** Zahlen- und Datumsformat zur Sprache */
export const locale = () => (cur === 'de' ? 'de-DE' : 'en-GB');

// Texte, die das Backend erzeugt (Ereignisse, Stillstandsgründe, automatische Fabriknamen, Fehlermeldungen), kommen
// auf Englisch. Für Deutsch übersetzt serverText() sie über Muster.
import { serverText } from './i18n/server-de';
export const lx = derived(lang, l => (s: string | null | undefined) => (s == null ? '' : l === 'de' ? serverText(s) : s));
export const lxr = (s: string | null | undefined) => (s == null ? '' : cur === 'de' ? serverText(s) : s);
