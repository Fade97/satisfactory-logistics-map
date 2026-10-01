// Formatierung + gemeinsame Farben.

// Diagrammreihen: validiert (dataviz validate_palette, dark, Fläche #1b1c1e) — Reihenfolge fest.
export const SERIES = ['#d27a0e', '#3f7fbf', '#2f9c6a', '#9a65d6', '#a8860f', '#c2527a'];

// Bedeutungsfarben der Karte (DESIGN.md): Beladen = Orange, Entladen = Kobalt.
export const C = {
  load: '#f59a23', unload: '#5b9bd5', mixed: '#b58be8', none: '#6f6b64',
  ok: '#4cc38a', warn: '#e2b93b', bad: '#e5484d', idle: '#6f6b64',
  player: '#f5f2ea', train: '#5b9bd5', truck: '#f59a23',
};
export const MODE_LABEL: Record<string, string> = { load: 'Load', unload: 'Unload', mixed: 'mixed', none: 'no platform' };
/** Farbe einer Maschine: stehend wegen vollem Ausgang = gewollter Puffer → grau, nur Mangel ist rot. */
export const machineColor = (m: { state: string; block?: string | null }) =>
  m.state === 'stopped' && m.block === 'full' ? '#8a857c' : STATE_COLOR[m.state] || '#6f6b64';
export const STATE_COLOR: Record<string, string> = {
  'running': C.ok, 'partial': C.warn, 'stopped': C.bad, 'paused': '#8f8a82', 'off': '#4a4d52',
};

import { locale, tr } from './i18n';

// Zahlen im Format der Sprache (ein Sprachwechsel lädt die Seite neu, daher reicht es, das Format einmal zu bauen)
const nf1 = new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat(locale(), { maximumFractionDigits: 0 });
export function fmtNum(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  const a = Math.abs(v);
  if (a >= 1e6) return nf1.format(v / 1e6) + tr('M');
  if (a >= 10000) return nf1.format(v / 1000) + tr('k');
  if (a >= 100) return nf0.format(v);
  return nf1.format(v);
}
export const fmtMW = (v: number) => (Math.abs(v) >= 1000 ? nf1.format(v / 1000) + ' GW' : nf0.format(v) + ' MW');
export function ago(t: number | string | null | undefined): string {
  if (!t) return '–';
  const ms = typeof t === 'number' ? t * 1000 : new Date(t).getTime();
  const s = Math.max(0, (Date.now() - ms) / 1000);
  if (s < 60) return tr('just now');
  if (s < 3600) return tr('{n} min ago', { n: Math.round(s / 60) });
  if (s < 86400) return tr('{n} h ago', { n: Math.round(s / 3600) });
  return tr('{n} days ago', { n: Math.round(s / 86400) });
}
export function dur(min: number | null | undefined): string {
  if (min === null || min === undefined) return '–';
  if (min < 60) return Math.round(min) + ' min';
  if (min < 1440) return nf1.format(min / 60) + ' h';
  return tr('{n} days', { n: nf1.format(min / 1440) });
}
export const clock = (t: number) => new Date(t * 1000).toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' });
