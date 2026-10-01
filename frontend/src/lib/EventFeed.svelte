<script lang="ts">
  import { events } from './api';
  import { go } from './router';
  import { clock } from './fmt';
  import { t, tr, lx, locale } from './i18n';

  let { onclose = () => {}, compact = false }: { onclose?: () => void; compact?: boolean } = $props();
  const KINDS: Record<string, string> = {
    '': tr('All'), stoerung: tr('Issues'), versorgung: tr('Supply'), player: tr('Player'), fortschritt: tr('Progress'),
  };
  const GROUP: Record<string, string> = {
    fuse: 'stoerung', derail: 'stoerung', nofuel: 'stoerung', stall: 'stoerung', system: 'stoerung',
    empty: 'versorgung', full: 'versorgung', battery: 'versorgung', fuel: 'versorgung',
    player: 'player', build: 'fortschritt', progress: 'fortschritt', pin: 'fortschritt',
  };
  let f = $state('');
  const list = $derived($events.filter(e => !f || GROUP[e.kind] === f));

  function day(t: number) {
    const d = new Date(t * 1000), now = new Date();
    return d.toDateString() === now.toDateString() ? tr('Today') : d.toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'numeric' });
  }
  function open(e: any) {
    if (e.x === null) return;
    const sel = e.ref?.startsWith('player:') ? e.ref : '';
    go('map', { x: Math.round(e.x), y: Math.round(e.y), z: 1.6, ...(sel ? { sel } : {}) });
  }
</script>

<div class="wrap" class:compact>
  {#if !compact}
    <div class="head">
      <h2>{$t('Events')}</h2>
      <button class="x" onclick={onclose} aria-label={$t('Close')}>✕</button>
    </div>
    <div class="filters">
      {#each Object.entries(KINDS) as [k, l]}
        <button class="chip" class:on={f === k} onclick={() => (f = k)}>{l}</button>
      {/each}
    </div>
  {/if}
  <ol>
    {#each list as e, i (e.id)}
      {#if !compact && (i === 0 || day(e.t) !== day(list[i - 1].t))}<li class="day">{day(e.t)}</li>{/if}
      <li class="ev {e.level}" class:click={e.x !== null}>
        <button onclick={() => open(e)} disabled={e.x === null}>
          <span class="t num">{clock(e.t)}</span>
          <span class="mk" aria-hidden="true"></span>
          <span class="tx">{$lx(e.text)}</span>
        </button>
      </li>
    {:else}
      <li class="none">{$t('No events. Issues, supply gaps, players and build progress show up here as they happen.')}</li>
    {/each}
  </ol>
</div>

<style>
  .wrap { display: flex; flex-direction: column; min-height: 0; height: 100%; }
  .head { display: flex; align-items: center; padding: 12px 14px 6px; }
  .head h2 { flex: 1; }
  .x { background: none; border: none; color: var(--dim); font-size: 16px; }
  .filters { display: flex; gap: 4px; flex-wrap: wrap; padding: 0 14px 8px; border-bottom: 1px solid var(--seam); }
  .chip { background: none; border: 1px solid var(--seam); padding: 2px 9px; font-size: 12px; color: var(--text2); }
  .chip.on { border-color: var(--ficsit); color: var(--ficsit); }
  ol { list-style: none; margin: 0; padding: 4px 0; overflow: auto; flex: 1; }
  .day { font-family: var(--cond); font-weight: 600; color: var(--dim); padding: 10px 14px 2px; font-size: 13px; }
  .ev button { display: flex; gap: 8px; align-items: baseline; width: 100%; text-align: left; background: none; border: none;
               padding: 5px 14px; color: var(--text2); font-size: 13px; }
  .ev.click button:hover { background: var(--plate2); color: var(--text); }
  .ev button:disabled { cursor: default; }
  .t { color: var(--dim); font-size: 12px; flex: none; }
  .mk { width: 7px; height: 7px; flex: none; transform: translateY(-1px); background: var(--dim); border-radius: 50%; }
  .warn .mk { background: var(--warn); border-radius: 0; transform: translateY(-1px) rotate(45deg); }
  .error .mk { background: var(--bad); border-radius: 0; }
  .error .tx { color: var(--text); }
  .none { color: var(--dim); padding: 16px 14px; font-size: 13px; }
  .compact .ev button { padding: 4px 0; font-size: 14px; }
</style>
