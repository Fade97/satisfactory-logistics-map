<script lang="ts">
  // Map sidebar: search stations/items, filter chips, players online.
  import { live, stations } from '../api';
  import { C, MODE_LABEL } from '../fmt';
  import { tn, both } from '../names';
  import { matches, fuzzy } from '../fuzzy';
  import { t, tr, locale } from '../i18n';
  import { stationKey, stationVisible, type StationFilter } from '../scene';

  let { q = $bindable(''), filters = $bindable(), open = $bindable(false), selKey = '', onpick, onfit }: {
    q?: string; filters: StationFilter; open?: boolean; selKey?: string;
    onpick: (key: string) => void; onfit: (x0: number, y0: number, x1: number, y1: number) => void;
  } = $props();
  let tab = $state<'stations' | 'items'>('stations');
  let search: HTMLInputElement;
  /** Focus the search field (map shortcut "/") */
  export function focus() { search?.focus(); }
  const CHIPS: [keyof StationFilter, string][] = [['truck', tr('Truck')], ['train', tr('Train')], ['load', tr('Load')], ['unload', tr('Unload')]];

  const allSt = $derived($stations ? [...$stations.trains.map(s => ({ ...s, kind: 'train' as const })), ...$stations.trucks.map(s => ({ ...s, kind: 'truck' as const }))] : []);
  const visSt = $derived(allSt.filter(s => stationVisible(s, filters) && matches(q, s.name, ...s.items.map(i => both(i.item)))));
  const items = $derived.by(() => {
    const m = new Map<string, { item: string; load: number; unload: number; amount: number }>();
    for (const s of allSt) for (const i of s.items) {
      const e = m.get(i.item) || { item: i.item, load: 0, unload: 0, amount: 0 };
      e.amount += i.amount; if (s.mode === 'unload') e.unload++; else e.load++; m.set(i.item, e);
    }
    const all = [...m.values()].sort((a, b) => a.item.localeCompare(b.item, locale()));
    return q ? fuzzy(q, all, i => both(i.item), 100) : all;
  });
  const onlinePlayers = $derived(($live?.players || []).filter(p => p.online !== false));
  function pickItem(it: string) {
    if (q === it) { q = ''; return; }
    q = it;
    const ss = allSt.filter(s => s.items.some(i => i.item === it));
    if (ss.length) {
      const xs = ss.map(s => s.pos[0] / 100), ys = ss.map(s => s.pos[1] / 100);
      onfit(Math.min(...xs) - 300, Math.min(...ys) - 300, Math.max(...xs) + 300, Math.max(...ys) + 300);
    }
    open = false;
  }
</script>

  <aside class="side panel" class:open={open}>
    <div class="tabs">
      <button class:on={tab === 'stations'} onclick={() => (tab = 'stations')}>{$t('Stations')} <span class="muted">{allSt.length}</span></button>
      <button class:on={tab === 'items'} onclick={() => (tab = 'items')}>{$t('Items')} <span class="muted">{items.length}</span></button>
    </div>
    <div class="srch">
      <input bind:this={search} class="field" type="search" bind:value={q} placeholder={$t('Search stations, items or machines')} autocomplete="off" />
    </div>
    <div class="chips">
      {#each CHIPS as [k, l]}
        <button class="chip" class:on={filters[k]} onclick={() => (filters[k] = !filters[k])}>
          {#if k === 'load' || k === 'unload'}<span class="dot" style="background:{C[k]}"></span>{/if}{l}</button>
      {/each}
    </div>
    {#if onlinePlayers.length}
      <div class="players">
        {#each onlinePlayers as p}
          <button class="pl" onclick={() => onpick('player:' + p.name)}><span class="pdot"></span>{p.name}
            <span class="muted">{p.online === null ? $t('Save file') : p.vehicle || (p.speed && p.speed > 1 ? $t('on the move') : $t('online'))}</span></button>
        {/each}
      </div>
    {/if}
    <div class="list">
      {#if tab === 'stations'}
        {#each visSt as s (s.id)}
          {@const k = stationKey(s)}
          <button class="row" class:sel={selKey === k} onclick={() => { onpick(k); open = false; }}>
            <span class="mk {s.kind}" style="background:{C[s.mode]}"></span>
            <span class="tx"><span class="nm">{s.name}</span><span class="sub">{$t(MODE_LABEL[s.mode])}{s.items.length ? ' · ' + s.items.map(i => $tn(i.item)).join(', ') : ''}</span></span>
            {#if s.kind === 'truck' && s.fill != null}<span class="fl" title={$t('{n} % full', { n: Math.round(s.fill * 100) })}><i style="height:{s.fill * 100}%;background:{s.fill > .9 ? C.bad : C.neutral}"></i></span>{/if}
          </button>
        {:else}<div class="none">{$t('No station matches the search and filters.')}</div>{/each}
      {:else}
        {#each items as i (i.item)}
          <button class="row" class:sel={q === i.item} onclick={() => pickItem(i.item)}>
            <span class="mk" style="background:{i.load && i.unload ? C.mixed : i.unload ? C.unload : C.load}"></span>
            <span class="tx"><span class="nm">{$tn(i.item)}</span><span class="sub">{$t('{a} × loading · {b} × unloading', { a: i.load, b: i.unload })}</span></span>
          </button>
        {:else}<div class="none">{$t('No item matches the search.')}</div>{/each}
      {/if}
    </div>
  </aside>

<style>
  .side { width: 320px; flex: none; display: flex; flex-direction: column; border-right: 1px solid var(--seam); min-height: 0; z-index: 20; }
  .tabs { display: flex; border-bottom: 1px solid var(--seam); }
  .tabs button { flex: 1; background: none; border: none; padding: 10px; font-family: var(--cond); font-weight: 600; font-size: 16px; color: var(--text2);
                 border-bottom: 2px solid transparent; }
  .tabs button.on { color: var(--text); border-bottom-color: var(--ficsit); }
  .srch { padding: 10px 12px 6px; }
  .chips { display: flex; gap: 4px; flex-wrap: wrap; padding: 0 12px 8px; }
  .chip { background: none; border: 1px solid var(--seam); padding: 3px 9px; font-size: 12.5px; color: var(--dim); display: inline-flex; align-items: center; gap: 5px; }
  .chip.on { color: var(--text); border-color: #5a5d62; background: var(--plate2); }
  .players { padding: 4px 12px 8px; border-bottom: 1px solid var(--seam); display: flex; flex-direction: column; gap: 2px; }
  .pl { display: flex; align-items: center; gap: 8px; background: none; border: none; padding: 3px 0; text-align: left; font-weight: 500; }
  .pl .muted { margin-left: auto; font-size: 12px; font-weight: 400; }
  .pdot { width: 9px; height: 9px; border-radius: 50%; background: var(--ficsit); box-shadow: 0 0 0 2px #f5f2ea; }
  .list { flex: 1; overflow: auto; padding: 4px 0 12px; }
  .row { display: flex; align-items: center; gap: 10px; width: 100%; background: none; border: none; border-left: 3px solid transparent;
         padding: 6px 12px 6px 9px; text-align: left; }
  .row:hover { background: var(--plate2); }
  .row.sel { border-left-color: var(--ficsit); background: var(--plate2); }
  .mk { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .mk.train { border-radius: 2px; }
  .tx { display: flex; flex-direction: column; min-width: 0; flex: 1; }
  .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub { font-size: 12px; color: var(--dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .fl { width: 5px; height: 22px; background: #34363a; position: relative; flex: none; }
  .fl i { position: absolute; left: 0; right: 0; bottom: 0; }
  .none { padding: 16px 12px; color: var(--dim); font-size: 13px; }
  @media (max-width: 760px) {
    .side { position: absolute; left: 0; top: 0; bottom: 0; width: min(88vw, 340px); transform: translateX(-102%); transition: transform .2s; }
    .side.open { transform: none; box-shadow: 10px 0 30px #0009; }
  }
</style>
