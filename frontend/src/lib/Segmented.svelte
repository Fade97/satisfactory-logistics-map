<script lang="ts" generics="T extends string | number">
  // Segmented control: one button per option, the chosen one gets class "on".
  // Renders only the buttons — the wrapper (.seg) and its styles stay with the page (`.seg :global(button)`).
  let { options, value = $bindable(), onchange }: { options: [T, string][]; value: T; onchange?: (v: T) => void } = $props();
</script>

{#each options as [v, label]}<button class:on={value === v} onclick={() => { value = v; onchange?.(v); }}>{label}</button>{/each}
