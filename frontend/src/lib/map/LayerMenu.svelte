<script lang="ts">
  // Layer menu: one checkbox per map layer (with collectible counts), labels, legend toggle.
  import { LAYERS } from '../scene';
  import { t } from '../i18n';

  let { layers = $bindable(), counts, showLegend = $bindable(false) }: {
    layers: Record<string, boolean>; counts: Record<string, string>; showLegend?: boolean;
  } = $props();
</script>

<div class="layers panel">
  {#each LAYERS as [k, l]}
    <label><input type="checkbox" bind:checked={layers[k]} /> {l}{#if counts[k]}<span class="cnt">{counts[k]}</span>{/if}</label>
  {/each}
  <label><input type="checkbox" checked={layers.labels !== false} onchange={e => (layers.labels = e.currentTarget.checked)} /> {$t('Labels')}</label>
  <button class="lg" onclick={() => (showLegend = !showLegend)}>{showLegend ? $t('Hide legend') : $t('Show legend')}</button>
</div>

<style>
  .layers { position: absolute; left: calc(100% + 8px); top: 90px; padding: 10px 14px; display: flex; flex-direction: column; gap: 3px; width: 230px;
            box-shadow: 0 8px 24px #0007; }
  .layers label { display: flex; gap: 8px; align-items: center; font-size: 13.5px; cursor: pointer; }
  .layers input { accent-color: var(--ficsit); }
  .layers .cnt { margin-left: auto; color: var(--dim); font-size: 12px; font-variant-numeric: tabular-nums; }
  .lg { margin-top: 6px; background: none; border: none; color: var(--ficsit); text-align: left; padding: 0; font-size: 13px; }
  @media (max-width: 760px) { .layers { left: 48px; top: 0; } }
</style>
