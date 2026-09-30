<script lang="ts">
  // Waren-Auswahl mit unscharfer Suche. Gültig ist nur, was aus der Liste gewählt wird — Tippfehler landen nie im Rechner.
  //
  // Die Vorschlagsliste wird an <body> gehängt (Portal) und dort fixed positioniert. Innerhalb von `.panel`
  // (clip-path für die gestanzte Ecke) oder unter einem Elternteil mit `transform` (Warenfluss-Leiste) würde sie
  // sonst abgeschnitten — position:fixed allein hilft dort nicht, weil transform einen neuen Bezugsrahmen bildet.
  import { fuzzy } from './fuzzy';
  import { tn, both } from './names';
  import { t, tr } from './i18n';

  let { value = $bindable(''), items = [], placeholder = tr('Ware suchen'), onpick = (_: string) => {}, clearOnPick = false }:
    { value?: string; items: string[]; placeholder?: string; onpick?: (v: string) => void; clearOnPick?: boolean } = $props();

  let q = $state($tn(value));
  let open = $state(false);
  let hi = $state(0);
  let inp: HTMLInputElement;
  const listId = 'fz-' + Math.random().toString(36).slice(2, 8);
  let box = $state({ left: 0, top: 0, width: 0, up: false, max: 320 });
  const list = $derived(fuzzy(q === value && !open ? '' : q, items, both, 12));
  const valid = $derived(items.includes(value));
  $effect(() => { if (!open) q = $tn(value); });

  function place() {
    if (!inp) return;
    const r = inp.getBoundingClientRect();
    const below = innerHeight - r.bottom - 8, above = r.top - 8;
    const up = below < 200 && above > below;                     // am unteren Rand (Handy) nach oben öffnen
    box = { left: r.left, width: r.width, top: up ? r.top - 2 : r.bottom + 2, up, max: Math.min(320, up ? above : below) };
  }
  $effect(() => {
    if (!open) return;
    place();
    const f = () => place();
    addEventListener('resize', f); addEventListener('scroll', f, true);
    return () => { removeEventListener('resize', f); removeEventListener('scroll', f, true); };
  });

  /** Svelte-Action: Element an <body> umhängen, beim Entfernen wieder löschen. */
  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return { destroy() { node.remove(); } };
  }

  function pick(v: string) {
    value = clearOnPick ? '' : v; q = clearOnPick ? '' : $tn(v); open = false; onpick(v);
  }
  function key(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); open = true; hi = Math.min(hi + 1, list.length - 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); hi = Math.max(hi - 1, 0); }
    else if (e.key === 'Enter') { if (open && list[hi]) { e.preventDefault(); pick(list[hi]); } }
    else if (e.key === 'Escape') { open = false; q = $tn(value); }
  }
  function blur() {
    // Eingabe ohne Auswahl: bester Treffer übernehmen, sonst alten Wert behalten
    setTimeout(() => {
      if (!open) return;
      open = false;
      if (q && q !== $tn(value) && list.length) pick(list[0]); else q = $tn(value);
    }, 150);
  }
</script>

<div class="picker">
  <input bind:this={inp} class="field" class:bad={value && !valid} bind:value={q} {placeholder} autocomplete="off" role="combobox"
    aria-expanded={open} aria-autocomplete="list" aria-controls={listId}
    onfocus={() => { open = true; hi = 0; inp.select(); }} oninput={() => { open = true; hi = 0; place(); }} onkeydown={key} onblur={blur} />
  {#if open && (list.length || q)}
    <ul use:portal role="listbox" id={listId} class="fz-list" class:up={box.up}
        style="left:{box.left}px;width:{box.width}px;max-height:{box.max}px;{box.up ? 'bottom:' + (innerHeight - box.top) + 'px' : 'top:' + box.top + 'px'}">
      {#each list as it, i}
        <li role="option" aria-selected={i === hi}><button type="button" class:hi={i === hi} onmousedown={e => { e.preventDefault(); pick(it); }} onmouseenter={() => (hi = i)}>{$tn(it)}</button></li>
      {:else}
        <li class="none">{$t('Keine Ware passt zu „{q}“', { q })}</li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .picker { position: relative; flex: 1; min-width: 200px; }
  .bad { border-color: var(--bad); }
  :global(.fz-list) { position: fixed; z-index: 200; margin: 0; padding: 4px 0; list-style: none;
       background: var(--plate2); border: 1px solid var(--seam); overflow: auto; box-shadow: 0 8px 24px #0008; }
  :global(.fz-list button) { display: block; width: 100%; text-align: left; background: none; border: none; padding: 6px 12px; color: var(--text); }
  :global(.fz-list button.hi) { background: var(--seam); color: var(--ficsit); }
  :global(.fz-list .none) { padding: 6px 12px; color: var(--dim); font-size: 13px; }
</style>
