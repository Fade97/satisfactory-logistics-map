<script lang="ts">
  // Höhenfilter: Etagen aus den Maschinenhöhen erkennen (4-m-Stufen, Häufungen ≥ 5), Bereich per Klick oder Regler.
  import { factory } from '../api';
  import { t } from '../i18n';

  let { zRange = $bindable(null), onclose }: { zRange?: [number, number] | null; onclose: () => void } = $props();

  // Höhen der Maschinen in 4-m-Schritten bündeln, Häufungen ≥ 5 Maschinen sind Etagen
  const floors = $derived.by(() => {
    const c = new Map<number, number>();
    for (const m of $factory?.machines || []) { const z = Math.round((m.z ?? 0) / 4) * 4; c.set(z, (c.get(z) || 0) + 1); }
    const fl = [...c.entries()].filter(([, n]) => n >= 5).sort((a, b) => a[0] - b[0]);
    // benachbarte Stufen (≤ 8 m) zusammenfassen: eine Etage mit leicht versetzten Fundamenten
    const out: { lo: number; hi: number; n: number }[] = [];
    for (const [z, n] of fl) {
      const last = out[out.length - 1];
      if (last && z - last.hi <= 8) { last.hi = z; last.n += n; } else out.push({ lo: z, hi: z, n });
    }
    return out;
  });
  const zBounds = $derived.by(() => {
    const zs = ($factory?.machines || []).map(m => m.z ?? 0);
    return zs.length ? [Math.floor(Math.min(...zs) / 4) * 4 - 4, Math.ceil(Math.max(...zs) / 4) * 4 + 4] : [0, 100];
  });
</script>

      <div class="zbar panel">
  <div class="zh"><b>{$t('Height')}</b><span class="muted">{zRange ? zRange[0] + ' … ' + zRange[1] + ' m' : $t('all floors')}</span>
    <button class="x" onclick={() => { zRange = null; onclose(); }} aria-label={$t('Close height filter')}>✕</button></div>
  <div class="floors">
    <button class:on={!zRange} onclick={() => (zRange = null)}>{$t('All')}</button>
    {#each floors as f}
      <button class:on={zRange && zRange[0] === f.lo && zRange[1] === f.hi} onclick={() => (zRange = [f.lo, f.hi])}
        title={$t('{n} machines', { n: f.n })}>{f.lo === f.hi ? f.lo : f.lo + '–' + f.hi} m</button>
    {/each}
  </div>
  <div class="range">
    <input type="range" min={zBounds[0]} max={zBounds[1]} step="2" value={zRange?.[0] ?? zBounds[0]} aria-label={$t('Height from')}
      oninput={e => { const v = +(e.target as HTMLInputElement).value; zRange = [Math.min(v, zRange?.[1] ?? zBounds[1]), zRange?.[1] ?? zBounds[1]]; }} />
    <input type="range" min={zBounds[0]} max={zBounds[1]} step="2" value={zRange?.[1] ?? zBounds[1]} aria-label={$t('Height to')}
      oninput={e => { const v = +(e.target as HTMLInputElement).value; zRange = [zRange?.[0] ?? zBounds[0], Math.max(v, zRange?.[0] ?? zBounds[0])]; }} />
  </div>
  <p class="muted">{$t('Hides machines, generators and stations outside this range. Belts and rails stay visible.')}</p>
</div>

<style>
  .zbar { position: absolute; left: 150px; top: 12px; width: 300px; padding: 10px 12px; z-index: 14; box-shadow: 0 8px 24px #0007;
          display: flex; flex-direction: column; gap: 8px; }
  .zh { display: flex; align-items: center; gap: 10px; }
  .zh .muted { flex: 1; font-size: 12.5px; }
  .zbar .x { background: none; border: none; color: var(--dim); margin-left: auto; }
  .floors { display: flex; flex-wrap: wrap; gap: 4px; }
  .floors button { background: var(--steel); border: 1px solid var(--seam); padding: 2px 8px; font-size: 12.5px; color: var(--text2); }
  .floors button.on { border-color: var(--ficsit); color: var(--ficsit); }
  .range { display: flex; flex-direction: column; }
  .range input { accent-color: var(--ficsit); width: 100%; }
  .zbar p { margin: 0; font-size: 12px; }
  @media (max-width: 760px) {
    .zbar { left: 56px; right: 8px; width: auto; top: 8px; }
  }
</style>
