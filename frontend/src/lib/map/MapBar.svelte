<script lang="ts">
  // Floating bar on the map (item flow, measuring, pick mode). Also styles the content passed in.
  import type { Snippet } from 'svelte';

  let { variant = 'top', children }: { variant?: 'top' | 'measure' | 'pick'; children: Snippet } = $props();
</script>

<div class="flowbar panel" class:meas={variant === 'measure'} class:pick={variant === 'pick'}>{@render children()}</div>

<style>
  .flowbar { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); width: min(460px, calc(100% - 120px)); padding: 10px 12px; z-index: 14;
             box-shadow: 0 8px 24px #0007; display: flex; flex-direction: column; gap: 6px; }
  .flowbar :global(.fr) { display: flex; gap: 6px; align-items: center; }
  .flowbar :global(.x) { background: none; border: none; color: var(--dim); font-size: 15px; }
  .flowbar :global(.fs) { display: flex; flex-wrap: wrap; gap: 2px 14px; font-size: 12.5px; color: var(--text2); }
  .flowbar :global(p) { margin: 0; font-size: 12.5px; }
  .flowbar :global(.lk) { background: none; border: none; color: var(--ficsit); padding: 0; text-align: left; font-size: 12.5px; }
  .flowbar.meas { top: auto; bottom: 40px; }
  .meas :global(.x) { background: none; border: none; color: var(--dim); margin-left: auto; }
  .meas :global(.zh) { display: flex; align-items: center; gap: 10px; }
  .flowbar.pick { flex-direction: row; justify-content: space-between; align-items: center; border-left: 3px solid var(--ficsit); }
  @media (max-width: 760px) {
    .flowbar { left: 56px; right: 8px; width: auto; transform: none; top: 8px; }
    .flowbar.meas { bottom: 12px; top: auto; }
  }
</style>
