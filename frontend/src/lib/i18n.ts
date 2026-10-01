// UI translation. Keys are the English source texts; German comes from lib/i18n/de/*.ts.
// tests/i18n.test.ts fails if a key has no German entry.
//
//   Markup:  {$t('Map')}               Placeholders:  $t('{n} machines', { n: 5 })
//   Script:  tr('Map')                 (not reactive; changing the language reloads the page)
import { derived, get } from 'svelte/store';
import { prefs } from './prefs';
import DE from './i18n/de';
import { serverText } from './i18n/server-de';

export type Lang = 'en' | 'de';
export const lang = derived(prefs, p => (p.ui === 'de' ? 'de' : 'en') as Lang);
let cur: Lang = get(lang);
lang.subscribe(l => (cur = l));

export function translate(l: Lang, key: string, args?: Record<string, unknown>): string {
  let s = l === 'de' ? (DE[key] ?? key) : key;
  if (args) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in args ? String(args[k]) : m));
  return s;
}
export const tr = (key: string, args?: Record<string, unknown>) => translate(cur, key, args);
export const t = derived(lang, l => (key: string, args?: Record<string, unknown>) => translate(l, key, args));
/** Number and date format for the current language */
export const locale = () => (cur === 'de' ? 'de-DE' : 'en-GB');

// Texts produced by the backend (events, stop reasons, automatic factory names, errors) arrive in English;
// for German, serverText() translates them via patterns.
export const lx = derived(lang, l => (s: string | null | undefined) => (s == null ? '' : l === 'de' ? serverText(s) : s));
export const lxr = (s: string | null | undefined) => (s == null ? '' : cur === 'de' ? serverText(s) : s);
