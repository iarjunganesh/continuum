# Architecture Diagrams — Brand-Themed Renders

Two diagrams, deliberately separate because they answer different questions:

| Diagram | Question it answers | Embedded in |
| --- | --- | --- |
| **`architecture-diagram`** | *What talks to what?* — components, agents, and the two CockroachDB tools | `README.md` § Architecture |
| **`recovery-sequence`** | *What survives?* — the two-cold-invocation handoff through durable state, over time | `README.md` § The Recovery Pipeline · `docs/ARCHITECTURE.md` §3 |

Rendered from mermaid source into brand-themed SVG/PNG (dark + light) rather than GitHub's generic
mermaid theme, so they match the palette the rest of the project uses: CockroachDB purple `#6933FF`,
AWS orange `#FF9900`, agent blue `#2563EB`, chaos red `#DC2626`.

## Files

Each diagram has the same six outputs, named `<diagram>-<theme>[-16x9].<ext>`:

| File | Use | Size |
| --- | --- | --- |
| `<diagram>.mmd` | **Source of truth** — edit this, never the SVG/PNG | — |
| `<diagram>-{dark,light}.svg` | README / docs embed (`<picture>`, theme-matched, click-to-enlarge) | vector |
| `<diagram>-{dark,light}.png` | Raster reference at the diagram's natural aspect | architecture 2352×795 · sequence 3297×2847 |
| `<diagram>-{dark,light}-16x9.png` | Demo-video flash-cut asset — pre-built, no manual screenshot needed | 1920×1080, letterboxed |
| `architecture-diagram-{dark,light}.config.json` | `mermaid-cli` theme variables per mode — **shared by both diagrams** | — |

The config files carry flowchart *and* sequence theme variables. Mermaid ignores the irrelevant half
per diagram type, so one config per theme serves both rather than four files drifting apart.

**Neither diagram is duplicated as an inline ```mermaid``` fence anywhere.** The `.mmd` is the only
definition; `README.md` and `docs/ARCHITECTURE.md` embed the rendered SVGs. Edit the `.mmd`,
re-render, and every embed updates with it.

Why rendered SVG rather than a fence GitHub would render natively: the brand theming only exists in
the `mermaid-cli` render — GitHub's built-in renderer applies its own theme and ignores the config
file. A fence would also give the demo video nothing to cut to.

## Regenerating

```bash
cd assets/architecture
for d in architecture-diagram recovery-sequence; do
  for t in dark light; do
    bg="#0d1117"; [ "$t" = light ] && bg="#ffffff"
    for ext in svg png; do
      npx --yes -p @mermaid-js/mermaid-cli mmdc -i "$d.mmd" \
        -o "$d-$t.$ext" -b "$bg" -c "architecture-diagram-$t.config.json" --scale 3
    done
    ffmpeg -y -i "$d-$t.png" \
      -vf "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=${bg/#\#/0x}" \
      "$d-$t-16x9.png"
  done
done
```

**Do not** pass `-w`/`-H` (fixed width/height) to `mmdc` — that pads the canvas to the requested size
instead of fitting it to the diagram content, leaving large dead space. Use `--scale` only.

**Use `force_original_aspect_ratio=decrease` in the ffmpeg letterbox.** Scaling to a fixed width
works for the wide component diagram but overflows 1080 on the portrait sequence diagram, and
`pad` then fails with *"Padded dimensions cannot be smaller than input dimensions"*. Fitting inside
the box handles both orientations.

**Layout notes**

- `architecture-diagram.mmd`: the two subgraphs force `direction TB` while the graph itself is `LR`.
  mermaid-cli's bundled renderer handles subgraph direction differently from GitHub's, so the
  explicit direction is load-bearing for the CLI render — don't drop it because the GitHub preview
  looks fine without it.
- `recovery-sequence.mmd`: keep self-message labels (`A-->>A:`) short. Long ones wrap to three lines
  and collide with the `autonumber` badge, which renders as text sitting on top of the label.
