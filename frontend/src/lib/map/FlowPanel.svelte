<script lang="ts">
  // Item flow bar: pick an item, show producers/consumers/stations, zoom to all locations.
  import ItemPicker from '../ItemPicker.svelte';
  import MapBar from './MapBar.svelte';
  import { fmtNum } from '../fmt';
  import { t } from '../i18n';
  import type { FlowInfo } from './flow';

  let { item = $bindable(''), items, info, onfit, onclose }: {
    item?: string; items: string[]; info: FlowInfo | null; onfit: () => void; onclose: () => void;
  } = $props();
</script>

<MapBar>
  <div class="fr"><ItemPicker bind:value={item} {items} placeholder={$t('Trace an item, e.g. Steel Beam')} onpick={() => setTimeout(onfit, 30)} />
    <button class="x" onclick={onclose} aria-label={$t('Close item flow')}>✕</button></div>
  {#if info}
    <div class="fs"><span><b class="num">{fmtNum(info.prod)}</b>{$t('/min produced · {n} machines', { n: info.np })}</span>
      <span><b class="num">{fmtNum(info.cons)}</b>{$t('/min consumed · {n}', { n: info.nc })}</span>
      <span>{$t('{s} stations · {p} belts/pipes', { s: info.ns, p: info.paths.length })}</span></div>
    {#if !info.paths.length}<p class="muted">{$t('In the last save this item was not on any belt.')}</p>{/if}
    <button class="lk" onclick={onfit}>{$t('Zoom to all locations')}</button>
  {/if}
</MapBar>
