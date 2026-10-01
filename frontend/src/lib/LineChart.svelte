<script lang="ts">
  // Time series as SVG: one axis, 2px lines, legend from two series up, crosshair + tooltip.
  // Colours from SERIES (validated against #1b1c1e, dataviz validator 2026-09-29) — fixed order.
  import { SERIES, fmtNum } from './fmt';
  import { t, locale } from './i18n';

  interface S { key: string; label: string; points: [number, number][]; color?: string; dash?: boolean }
  let { series = [], unit = '', height = 220, area = false }: { series: S[]; unit?: string; height?: number; area?: boolean } = $props();

  let w = $state(600);
  const pad = { l: 52, r: 14, t: 10, b: 26 };
  let hoverX = $state<number | null>(null);

  const all = $derived(series.flatMap(s => s.points));
  const t0 = $derived(all.length ? Math.min(...all.map(p => p[0])) : 0);
  const t1 = $derived(all.length ? Math.max(...all.map(p => p[0])) : 1);
  const vmax = $derived(niceMax(all.length ? Math.max(...all.map(p => p[1])) : 1));
  const X = (t: number) => pad.l + ((t - t0) / Math.max(1, t1 - t0)) * (w - pad.l - pad.r);
  const Y = (v: number) => pad.t + (1 - v / vmax) * (height - pad.t - pad.b);

  function niceMax(v: number) {
    if (v <= 0) return 1;
    const e = Math.pow(10, Math.floor(Math.log10(v))), f = v / e;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e;
  }
  const ticks = $derived([0, .25, .5, .75, 1].map(f => f * vmax));
  const tticks = $derived.by(() => {
    const span = t1 - t0, n = Math.max(2, Math.floor((w - pad.l) / 110));
    return Array.from({ length: n + 1 }, (_, i) => t0 + (span * i) / n);
  });
  function tlabel(t: number) {
    const d = new Date(t * 1000), span = t1 - t0;
    return span > 3 * 86400 ? d.toLocaleDateString(locale(), { day: '2-digit', month: '2-digit' })
      : d.toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' });
  }
  // Don't bridge gaps (game paused, service down): jump > 3× typical interval → new polyline
  function step(pts: [number, number][]) {
    const d = pts.slice(1).map((p, i) => p[0] - pts[i][0]).sort((a, b) => a - b);
    return d.length ? d[Math.floor(d.length / 2)] : 60;
  }
  const path = (pts: [number, number][]) => {
    const gap = step(pts) * 3;
    return pts.map((p, i) => (i === 0 || p[0] - pts[i - 1][0] > gap ? 'M' : 'L') + X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join('');
  };
  // close areas per contiguous segment
  const segments = (pts: [number, number][]) => {
    const gap = step(pts) * 3, out: [number, number][][] = [];
    for (const [i, p] of pts.entries()) { if (i === 0 || p[0] - pts[i - 1][0] > gap) out.push([]); out[out.length - 1].push(p); }
    return out;
  };
  const color = (s: S, i: number) => s.color || SERIES[i % SERIES.length];

  function nearest(pts: [number, number][], t: number) {
    let best = pts[0];
    for (const p of pts) if (Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p;
    return best;
  }
  const hoverT = $derived(hoverX === null ? null : t0 + ((hoverX - pad.l) / (w - pad.l - pad.r)) * (t1 - t0));
  function move(e: PointerEvent) {
    const r = (e.currentTarget as SVGElement).getBoundingClientRect();
    const x = e.clientX - r.left;
    hoverX = x < pad.l || x > w - pad.r ? null : x;
  }
</script>

<div class="chart" bind:clientWidth={w}>
  {#if !all.length}
    <div class="empty">{$t('No values yet — the chart fills in every minute once data arrives.')}</div>
  {:else}
    {#if series.length > 1}
      <div class="legend">
        {#each series as s, i}<span><i style="background:{color(s, i)}"></i>{s.label}</span>{/each}
      </div>
    {/if}
    <svg width={w} {height} role="img" aria-label={$t('History')} onpointermove={move} onpointerleave={() => (hoverX = null)}>
      {#each ticks as v}
        <line x1={pad.l} x2={w - pad.r} y1={Y(v)} y2={Y(v)} class="grid" />
        <text x={pad.l - 6} y={Y(v) + 4} class="ax" text-anchor="end">{fmtNum(v)}</text>
      {/each}
      {#each tticks as tt}
        <text x={X(tt)} y={height - 6} class="ax" text-anchor="middle">{tlabel(tt)}</text>
      {/each}
      {#each series as s, i}
        {#if area && s.points.length > 1}
          {#each segments(s.points) as seg}
            {#if seg.length > 1}<path d={path(seg) + `L${X(seg[seg.length - 1][0])},${Y(0)}L${X(seg[0][0])},${Y(0)}Z`} fill={color(s, i)} opacity=".1" />{/if}
          {/each}
        {/if}
        <path d={path(s.points)} fill="none" stroke={color(s, i)} stroke-width="2" stroke-linejoin="round" stroke-linecap="round"
              stroke-dasharray={s.dash ? '5 4' : undefined} />
      {/each}
      {#if hoverT !== null}
        <line x1={hoverX} x2={hoverX} y1={pad.t} y2={height - pad.b} class="cross" />
        {#each series as s, i}
          {#if s.points.length}
            {@const p = nearest(s.points, hoverT)}
            <circle cx={X(p[0])} cy={Y(p[1])} r="4" fill={color(s, i)} stroke="var(--steel)" stroke-width="2" />
          {/if}
        {/each}
      {/if}
    </svg>
    {#if hoverT !== null}
      <div class="tip" style="left:{Math.min(hoverX + 12, w - 190)}px">
        <div class="tt">{new Date(nearest(series[0].points, hoverT)[0] * 1000).toLocaleString(locale(), { dateStyle: 'short', timeStyle: 'short' })}</div>
        {#each series as s, i}
          {#if s.points.length}
            <div class="tr"><i style="background:{color(s, i)}"></i>{s.label}<b>{fmtNum(nearest(s.points, hoverT)[1])} {unit}</b></div>
          {/if}
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .chart { position: relative; width: 100%; }
  svg { display: block; touch-action: pan-y; }
  .grid { stroke: var(--seam); stroke-width: 1; }
  .ax { fill: var(--dim); font-size: 11px; font-variant-numeric: tabular-nums; }
  .cross { stroke: var(--dim); stroke-width: 1; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--text2); margin-bottom: 6px; }
  .legend i, .tr i { display: inline-block; width: 12px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
  .tip { position: absolute; top: 20px; background: var(--plate); border: 1px solid var(--seam); padding: 8px 10px;
         font-size: 12px; pointer-events: none; min-width: 170px; z-index: 2; }
  .tt { color: var(--dim); margin-bottom: 4px; }
  .tr { display: flex; align-items: center; gap: 2px; color: var(--text2); }
  .tr b { margin-left: auto; padding-left: 12px; color: var(--text); font-variant-numeric: tabular-nums; font-weight: 500; }
  .empty { color: var(--dim); font-size: 13px; padding: 28px 0; }
</style>
