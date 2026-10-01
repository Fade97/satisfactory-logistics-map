<script lang="ts">
  // Drawing a note: shape choice, hint, done/cancel. Points are placed by tapping the map (MapPage).
  import { t, tr } from '../i18n';
  import { minPoints, type Draft } from './draw';

  let { draw = $bindable(), onfinish }: { draw: Draft | null; onfinish: () => void } = $props();
  const SHAPES: [Draft['shape'], string][] = [['point', tr('Point')], ['line', tr('Line')], ['area', tr('Area')]];
</script>

<div class="drawbar panel">
  <div class="seg">
    {#each SHAPES as [s, l]}
      <button class:on={draw.shape === s} onclick={() => (draw = { shape: s, pts: [] })}>{l}</button>
    {/each}
  </div>
  <p>{draw.shape === 'point' ? $t('Tap where the note should go.') : $t('Place points, then “Done”.')}</p>
  {#if draw.shape !== 'point'}<button class="btn primary" onclick={onfinish} disabled={draw.pts.length < minPoints(draw.shape)}>{$t('Done')}</button>{/if}
  <button class="btn" onclick={() => (draw = null)}>{$t('Cancel')}</button>
</div>

<style>
  .drawbar { position: absolute; left: calc(100% + 8px); top: 130px; padding: 12px; width: 240px; box-shadow: 0 8px 24px #0007; }
  .drawbar p { font-size: 13px; color: var(--text2); margin: 8px 0; }
  .drawbar .btn { margin-right: 6px; }
  .seg { display: flex; }
  .seg button { flex: 1; background: var(--steel); border: 1px solid var(--seam); padding: 5px; font-size: 13px; color: var(--text2); }
  .seg button.on { border-color: var(--ficsit); color: var(--ficsit); }
  @media (max-width: 760px) { .drawbar { left: 48px; top: 0; } }
</style>
