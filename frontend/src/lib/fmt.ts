// Formatting + shared colours and UI constants.
import { locale, tr } from './i18n';

// Chart series: validated (dataviz validate_palette, dark, surface #1b1c1e) — fixed order.
export const SERIES = ['#d27a0e', '#3f7fbf', '#2f9c6a', '#9a65d6', '#a8860f', '#c2527a'];

// Semantic map colours (DESIGN.md): load = orange, unload = cobalt.
export const C = {
  load: '#f59a23', unload: '#5b9bd5', mixed: '#b58be8', none: '#6f6b64',
  ok: '#4cc38a', warn: '#e2b93b', bad: '#e5484d', idle: '#6f6b64',
  player: '#f5f2ea', train: '#5b9bd5', truck: '#f59a23',
  accent: '#f59a23',      // FICSIT orange: selection, measuring, routes, own notes
  light: '#f5f2ea',       // rings around moving objects, drafts, item flow
  full: '#8a857c',        // stopped because the output is full (intended buffer)
  neutral: '#c3bfb7',     // fill bars without a warning
  ring: '#0c0d0e',        // dark outline of map symbols
  mapBg: '#16171a',       // map background
};
export const MODE_LABEL: Record<string, string> = { load: 'Load', unload: 'Unload', mixed: 'mixed', none: 'no platform' };
export const STATE_COLOR: Record<string, string> = {
  'running': C.ok, 'partial': C.warn, 'stopped': C.bad, 'paused': '#8f8a82', 'off': '#4a4d52',
};
/** Machine colour: stopped because the output is full = intended buffer → grey; only starvation is red. */
export const machineColor = (m: { state: string; block?: string | null }) =>
  m.state === 'stopped' && m.block === 'full' ? C.full : STATE_COLOR[m.state] || C.none;
/** Factory status from shares (0–1) of starved and running machines; full outputs don't count as a problem. */
export const factoryStatusColor = (starved: number, running: number) =>
  starved > .3 ? C.bad : starved > .08 ? C.warn : running > .2 ? C.ok : C.full;

/** Node purity: rank for sorting (unknown = 0); the names are shared i18n keys (i18n/de/parts.ts). */
export const PURITY_RANK: Record<string, number> = { pure: 3, normal: 2, impure: 1 };
export const purityRank = (p: string | null | undefined) => PURITY_RANK[p || ''] || 0;
export const purityLabel = (p: string | null | undefined, unknown = '?') => (purityRank(p) ? tr(p!) : unknown);

/** Same breakpoint as the CSS media queries (phone layout). */
export const MOBILE_QUERY = '(max-width: 760px)';

// Numbers in the language's format (changing the language reloads the page, so building the format once is enough)
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
/** Distance in metres: "740 m", "1.25 km" */
export const fmtDist = (m: number) => (m >= 1000 ? (m / 1000).toFixed(2) + ' km' : Math.round(m) + ' m');
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
