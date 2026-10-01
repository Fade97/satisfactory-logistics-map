<script lang="ts">
  // Measuring bar: distance, straight line, area and building material for the points placed on the map.
  import MapBar from './MapBar.svelte';
  import { fmtNum, fmtDist } from '../fmt';
  import { t } from '../i18n';
  import { measureStats, fmtArea } from './measure';

  let { pts, onchange }: { pts: number[][]; onchange: (pts: number[][] | null) => void } = $props();
  const info = $derived(measureStats(pts));
</script>

<MapBar variant="measure">
  <div class="zh"><b>{$t('Measure')}</b><button class="x" onclick={() => onchange(null)} aria-label={$t('Stop measuring')}>✕</button></div>
  {#if info}
    <div class="fs"><span>{$t('Distance')} <b class="num">{fmtDist(info.len)}</b></span>
      {#if pts.length > 2}<span>{$t('Straight line start–end')} <b class="num">{Math.round(info.direct)} m</b></span>
        <span>{$t('Area')} <b class="num">{fmtArea(info.area)}</b> ≈ {$t('{n} foundations 8×8', { n: fmtNum(info.foundations) })}</span>{/if}
      <span>≈ {$t('{r} rail pieces · {b} belts (max. 56 m)', { r: fmtNum(info.rails), b: fmtNum(info.belts) })}</span></div>
    <button class="lk" onclick={() => onchange(pts.slice(0, -1))}>{$t('remove last point')}</button>
  {:else}<p class="muted">{$t('Tap points on the map. Points snap to stations and machines.')}</p>{/if}
</MapBar>
