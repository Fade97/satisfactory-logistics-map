// Map tooltip (mouse hover): bold title + one line of status per object kind.
// tr/lxr are enough for UI texts (changing the language reloads the page); item names (tn) switch live, so they are passed in.
import type { MapObj } from '../mapview';
import { MODE_LABEL } from '../fmt';
import { tr, lxr } from '../i18n';

type Name = (s: string | null | undefined) => string;

/** Title: item/recipe name for machines, nodes and generators, otherwise the label */
export function tipTitle(o: MapObj, tn: Name): string {
  const d = o.data;
  if (o.kind === 'machine') return tn(d.recipe || d.name);
  if (o.kind === 'node') return tn(d.item);
  if (o.kind === 'generator') return tn(d.name);
  return o.label ?? '';
}

export function tipText(o: MapObj, tn: Name): string {
  const d = o.data;
  if (o.kind === 'station') return (d.kind === 'train' ? tr('Train station') : tr('Truck station')) + ' · ' + tr(MODE_LABEL[d.mode]) + (d.items[0] ? ' · ' + d.items.map((i: { item: string }) => tn(i.item)).join(', ') : '');
  if (o.kind === 'machine') return tn(d.name) + ' · ' + tr(d.state) + ' ' + d.pct + ' %' + (d.why ? ' · ' + lxr(d.why) : '');
  if (o.kind === 'node') return (d.used ? tr('occupied') : tr('free')) + (d.rate ? ' · ' + d.rate + '/min' : '');
  if (o.kind === 'player') return d.online === null ? tr('as of the save') : d.online ? tr('online') : tr('offline');
  if (o.kind === 'truck' || o.kind === 'train') return (d.cargo ? tn(d.cargo.item) + ' · ' : '') + (d.speed != null ? Math.round(d.speed) + ' km/h' : tr('Position from the save'));
  if (o.kind === 'factory') return tr('{n} machines · {s} stopped', { n: d.n, s: d.states['stopped'] || 0 });
  if (o.kind === 'pin') return d.author;
  if (o.kind === 'generator') return d.producing ? tr('producing {n} MW', { n: d.cap }) : tr('stopped');
  if (o.kind === 'collectible') return tr('not collected yet · height {z} m', { z: d.pos[2] });
  return '';
}
