<script lang="ts">
  // Zeitreise: Minutenbilder der letzten Stunden abspielen. Liefert das gewählte Bild per onframe an die Karte.
  import { onMount, onDestroy } from 'svelte';
  import { clock } from '../fmt';
  import { t, locale } from '../i18n';

  export interface Frame { p: any[]; tr: any[]; tk: any[]; f: any[]; pw: any[] }
  let { onframe, onclose }: { onframe: (t: number | null, f: Frame | null) => void; onclose: () => void } = $props();

  let hours = $state(6);
  let frames = $state<[number, Frame][]>([]);
  let idx = $state(0);
  let playing = $state(false);
  let speed = $state(10);                  // Bilder je Sekunde
  let loading = $state(true);
  let timer = 0;

  async function load() {
    loading = true;
    const step = hours > 12 ? 180 : hours > 6 ? 120 : 60;
    frames = await (await fetch(`/api/frames?h=${hours}&step=${step}`)).json();
    idx = Math.max(0, frames.length - 1);
    loading = false; emit();
  }
  function emit() { const f = frames[idx]; onframe(f ? f[0] : null, f ? f[1] : null); }
  function play() {
    playing = !playing;
    clearInterval(timer);
    if (playing) {
      if (idx >= frames.length - 1) idx = 0;
      timer = window.setInterval(() => {
        if (idx >= frames.length - 1) { playing = false; clearInterval(timer); return; }
        idx++; emit();
      }, 1000 / speed);
    }
  }
  onMount(load);
  onDestroy(() => { clearInterval(timer); onframe(null, null); });
  // Lücken (Pausen, Dienst aus) auf der Zeitleiste markieren
  const gaps = $derived(frames.slice(1).map((f, i) => f[0] - frames[i][0] > 600 ? i + 1 : -1).filter(i => i > 0));
</script>

<div class="tt panel">
  <div class="hd"><b>{$t('Time travel')}</b>
    <select class="field sel" bind:value={hours} onchange={load} aria-label={$t('Time range')}>
      {#each [[2, '2 h'], [6, '6 h'], [12, '12 h'], [24, '24 h']] as [h, l]}<option value={h}>{l}</option>{/each}
    </select>
    <span class="muted">{loading ? $t('loading …') : frames.length ? clock(frames[idx][0]) + ' · ' + new Date(frames[idx][0] * 1000).toLocaleDateString(locale(), { weekday: 'short' }) : ''}</span>
    <button class="x" onclick={onclose} aria-label={$t('Close time travel')}>✕</button>
  </div>
  {#if frames.length > 1}
    <div class="row">
      <button class="btn pl" onclick={play} aria-label={playing ? $t('Pause') : $t('Play')}>{playing ? '❚❚' : '▶'}</button>
      <div class="track">
        <input type="range" min="0" max={frames.length - 1} bind:value={idx} oninput={() => { playing = false; clearInterval(timer); emit(); }} aria-label={$t('Point in time')} />
        {#each gaps as g}<i class="gap" style="left:{(g / (frames.length - 1)) * 100}%" title={$t('Pause/gap')}></i>{/each}
      </div>
      <select class="field sel" bind:value={speed} onchange={() => { if (playing) { playing = false; play(); } }} aria-label={$t('Speed')}>
        {#each [5, 10, 30] as s}<option value={s}>{s}×</option>{/each}
      </select>
    </div>
    <p class="muted">{clock(frames[0][0])} – {clock(frames[frames.length - 1][0])} · {$t('Factory outlines show the status at that time. Live data is paused meanwhile.')}</p>
  {:else if !loading}
    <p class="muted">{$t('Nothing recorded yet. Time travel saves a snapshot every minute while someone is playing (the server pauses when nobody is online).')}</p>
  {/if}
</div>

<style>
  .tt { position: absolute; left: 50%; bottom: 36px; transform: translateX(-50%); width: min(620px, calc(100% - 24px)); padding: 10px 12px;
        z-index: 16; box-shadow: 0 8px 24px #0007; display: flex; flex-direction: column; gap: 8px; }
  .hd { display: flex; align-items: center; gap: 10px; }
  .hd .muted { flex: 1; font-size: 13px; font-variant-numeric: tabular-nums; }
  .x { background: none; border: none; color: var(--dim); }
  .sel { width: auto; padding: 3px 6px; }
  .row { display: flex; gap: 10px; align-items: center; }
  .pl { min-width: 40px; }
  .track { position: relative; flex: 1; }
  .track input { width: 100%; accent-color: var(--ficsit); }
  .gap { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--warn); pointer-events: none; }
  p { margin: 0; font-size: 12px; }
  @media (max-width: 760px) { .tt { bottom: 12px; } }
</style>
