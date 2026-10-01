export type Mode = 'load' | 'unload' | 'mixed' | 'none';
export interface Item { item: string; amount: number }
export interface Veh { id: string; type: string; last: number; round: number; per_min?: number | null }
export interface Platform { id: string; type: 'freight' | 'fluid' | 'empty'; mode: Mode | null; items: Item[]; fill?: number | null }
export interface Station {
  kind: 'truck' | 'train'; id: string; ident?: string; name: string; pos: number[]; mode: Mode;
  items: Item[]; vehicles?: Veh[]; platforms?: Platform[]; fill?: number | null;
}
export interface Route { name: string; self_driving: boolean; stops: { ident: string; name: string }[] }
export interface Player { name: string; pos: number[]; online: boolean | null; dead?: boolean; hp?: number | null; speed?: number | null; vehicle?: string | null; inventory?: { Name: string; Amount: number }[] }
export interface Train { name: string; pos: number[]; status: string | null; station: string | null; speed: number | null; derailed: boolean; payload: number | null }
export interface Truck { id: string; type: string; name: string; pos: number[]; speed: number | null; autopilot: boolean; fuel: boolean; cargo: Item | null }
export interface LiveStation { activity?: string | null; status?: string | null; rate?: number; item?: string; amount?: number; inflow?: number; outflow?: number }
export interface Live {
  at: string; source: 'frm' | 'save'; paused: boolean | null;
  session: { name: string; day: number; clock: string; is_day: boolean } | null;
  players: Player[]; trains: Train[]; trucks: Truck[]; stations: Record<string, LiveStation>;
}
export interface Stations {
  trucks: Station[]; trains: Station[]; routes: Route[]; players: Player[];
  map: { west: number; east: number; north: number; south: number; image: string };
  source: { save: string; saved_at: string; label: string };
}
export interface Flow { item: string; rate: number; max: number }
export interface Machine {
  id: string; cls: string; name: string; pos: number[]; z?: number; recipe: string | null; alt?: boolean; clock: number;
  state: 'running' | 'partial' | 'stopped' | 'paused' | 'off'; pct: number; circuit: number | null;
  by?: string | null; why?: string | null; since?: number | null; fuse?: boolean; power: number;
  out: Flow[]; inp: Flow[]; node?: string; purity?: string; block?: 'full' | 'starved' | 'unknown' | null; nopower?: boolean;
  yaw?: number;                          // rotation in degrees
}
export interface Generator {
  id: string; cls: string; name: string; pos: number[]; circuit: number | null; cap: number; producing: boolean;
  fuel: string | null; fuel_rate: number | null; fuel_minutes?: number; stock: Item[]; by?: string | null;
}
export interface Battery { id: string; pos: number[]; circuit: number | null; stored: number; capacity: number }
export interface Circuit {
  id: number; prod: number; cap: number; use: number; max_use: number; n_mach: number; n_gen?: number;
  battery: number; battery_cap: number; battery_empty?: string; battery_full?: string; fuse?: boolean;
}
export interface Balance { item: string; prod: number; cons: number; prod_max: number; cons_max: number; n_prod: number; n_cons: number }
export interface Cluster {
  key: string; name: string; auto: string; renamed: boolean; status?: string; n: number; ids: string[]; box: number[]; center: number[];
  states: Record<string, number>; starved: number; full: number; power: number; out: { item: string; rate: number }[]; inp: { item: string; rate: number }[];
}
export interface Factory {
  source: 'frm' | 'save'; at: number; machines: Machine[]; generators: Generator[]; circuits: Circuit[];
  balance: Balance[]; factories: Cluster[]; batteries: Battery[];
}
export interface Geo { at: string; source: string; rails: number[][][]; pipes: number[][][]; belts: number[][][] }
export interface Node { id: string; pos: number[]; item: string | null; purity: string | null; kind: string; used: boolean; extractor: string | null; rate: number | null }
export interface Status { now: number; title?: string; frm: { ok: boolean; since: number; error: string | null; configured?: boolean }; save: { file: string; saved_at: string; mtime: number; playtime: number; session: string } | null; save_error?: string | null; factory_source: string }
export interface Progress { schematics: string[]; n_schematics: number; active: string | null; phase: string; milestones_by_tier: Record<string, number> }
export interface GameEvent { id: number; t: number; kind: string; level: 'info' | 'warn' | 'error'; text: string; ref: string | null; x: number | null; y: number | null }
export interface Pin { id?: number; t?: number; author: string; cat: string; color: string; text: string; shape: 'point' | 'line' | 'area'; geom: number[][] }
/** Collectibles not picked up yet: positions [x, y, z] in m per kind (somersloop, mercer, slug1–3, droppod) */
export interface Collectibles {
  open: Record<string, number[][]>; looted_pods: number; total: { somersloop?: number; mercer?: number; droppod?: number };
  labels: Record<string, string>;
}
/** Container or tank with its stock (fill 0–1, null = unknown capacity) */
export interface StorageBox { id: string; cls: string; pos: number[]; z: number; items: Item[]; fill: number | null }
export interface Sink { source?: 'frm' | 'save'; points: number; coupons: number; to_coupon?: number; pct?: number; per_min?: number | null; graph?: number[] }
/** Detail layer (foundations/walls from the save): Int16 arrays, see lightweight.detail_binary */
export interface DetailLayer { tiles: Int16Array; tmeta: Uint8Array; walls: Int16Array }

// Time travel: one frame per minute, positions in m (see mapsvc/collect.py record_frame)
export type PlayerFrame = [name: string, x: number, y: number, online: 0 | 1];
export type TrainFrame = [name: string, x: number, y: number, speed: number, docked: 0 | 1];
export type TruckFrame = [id: string, x: number, y: number, speed: number];
/** Per factory: share running and share starved, each 0–100 */
export type FactoryFrame = [key: string, running: number, starved: number];
export type PowerFrame = [circuit: number, use: number, cap: number];
export interface Frame { p: PlayerFrame[]; tr: TrainFrame[]; tk: TruckFrame[]; f: FactoryFrame[]; pw: PowerFrame[] }

// Planner (/api/plan)
export interface PlanStep {
  recipe: string; cls: string; alt: boolean; building: string; machines: number; full: number; full_clock: number;
  clock: number | null; power: number; out: { item: string; rate: number }[]; inp: { item: string; rate: number }[]; bp?: boolean;
}
export interface PlanResult {
  ok: true; steps: PlanStep[]; raw: { item: string; key?: string; rate: number }[];
  surplus_used: { item: string; rate: number; available: number }[]; byproducts: { item: string; rate: number }[];
  power: number; machines: number; shards: number; sloops: number; goal?: string; max_clock?: number;
  targets: { item: string; rate: number }[];
}
export type PlanResponse = PlanResult | { ok: false; error: string };
