// Item flow: everything on the map that produces, consumes, moves or extracts one item.
import type { Factory, Stations, Node } from '../types';
import { stationKey } from '../scene';

export interface FlowInfo {
  keys: Set<string>;          // map object keys to highlight
  paths: number[][][];        // belts/pipes carrying the item
  prod: number; cons: number; // rate /min
  np: number; nc: number; ns: number;   // number of producers, consumers, stations
}

export function computeFlow(item: string, factory: Factory | null, stations: Stations | null, nodes: Node[] | null,
                            flow: Record<string, number[][][]> | null): FlowInfo | null {
  if (!item) return null;
  const keys = new Set<string>();
  let prod = 0, cons = 0, np = 0, nc = 0, ns = 0;
  for (const m of factory?.machines || []) {
    const o = m.out.find(x => x.item === item), i = m.inp.find(x => x.item === item);
    if (o) { keys.add('machine:' + m.id); prod += o.rate; np++; }
    if (i) { keys.add('machine:' + m.id); cons += i.rate; nc++; }
  }
  for (const g of factory?.generators || []) if (g.fuel === item) { keys.add('generator:' + g.id); nc++; }
  for (const s of [...(stations?.trucks || []), ...(stations?.trains || [])])
    if (s.items.some(x => x.item === item)) { keys.add(stationKey(s)); ns++; }
  for (const n of nodes || []) if (n.item === item) keys.add('node:' + n.id);
  for (const f of factory?.factories || []) if (f.out.some(o => o.item === item) || f.inp.some(o => o.item === item)) keys.add('factory:' + f.key);
  return { keys, paths: (flow || {})[item] || [], prod, cons, np, nc, ns };
}

/** Items to pick from: everything on belts plus everything in the item balance, sorted by name */
export const flowItemList = (flow: Record<string, number[][][]> | null, factory: Factory | null, locale: string) =>
  [...new Set([...Object.keys(flow || {}), ...(factory?.balance || []).map(b => b.item)])].sort((a, b) => a.localeCompare(b, locale));
