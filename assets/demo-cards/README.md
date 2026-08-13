# Brand Cards — README Banner + Demo Video Bookends

The README's hero banner and the demo video's opening/closing title cards. **The `.svg` files are
the single source of truth** — every PNG here is rendered from the corresponding SVG, so there is
one design to edit rather than two kept manually in sync.

| File | Use | Format |
| --- | --- | --- |
| `banner-dark.svg` · `banner-light.svg` | README hero (top of page) | vector, `<picture>` embed |
| `banner-dark.png` · `banner-light.png` | Demo video beat 1 (0:00) — title card | 16:9 (1920×1080), letterboxed |
| `banner-dark-native.png` · `banner-light-native.png` | Raster reference at the SVG's native size | 1000×410 |
| `signoff-dark.svg` · `signoff-light.svg` | README closing sign-off | vector, `<picture>` embed |
| `signoff-dark.png` · `signoff-light.png` | Demo video beat 14 (2:48) — closing card | 16:9 (1920×1080), letterboxed |
| `signoff-dark-native.png` · `signoff-light-native.png` | Raster reference at the SVG's native size | 1000×450 |

The 16:9 video cards **letterbox** the SVG (no crop) — the surrounding canvas is filled with the
card's own background colour (`#0d1117` dark / `#ffffff` light), so the padding is invisible and
the card reads as centred on a wider stage.

## The design

Built from the project's own mark ([`../logo.svg`](../logo.svg)): the **severed infinity loop** —
purple→blue gradient (`#6933FF` → `#2563EB`) with an orange break (`#FF9900` dark / `#E07800`
light, darkened for contrast on white) and an orange terminal dot.

The break is the whole idea, so the two cards use it differently:

- **Banner** — the loop is *severed*. The kill stroke cuts through it. This is the problem.
- **Sign-off** — the loop is *whole*, the kill stroke gone, only the terminal dot remaining.
  The memory outlived the failure. This is the payoff.

Don't "fix" the banner by removing the break, and don't add one to the sign-off — the asymmetry is
deliberate and it's the argument the video makes.

Typography is Georgia (wordmark, matching `logo.svg`) and Segoe UI with system fallbacks. No
webfont is loaded, so exports don't depend on network access or on a font being installed.

**Which theme?** Match the card to the mode you record the app in — dark cards if you film in dark
mode, light cards if light. Don't mix within one video.

## Editing the card text / re-rendering the PNGs

Edit the `<text>` elements directly in the `.svg` files — that's the only place the wording lives.
`banner.html` and `signoff.html` are thin theme-aware preview/export wrappers around the SVGs, not
a separate reimplementation, so there is nothing else to keep in sync.

Query parameters on the HTML wrappers:

- `?theme=dark` / `?theme=light` — force a theme and hide the on-page **◐ Toggle theme** button so
  the export is clean
- `?native=1` — switch the canvas from the 1920×1080 letterbox to a 1:1 crop at the SVG's own size

**Preview:** open `banner.html` in any browser and click **◐ Toggle theme**.

**Re-export all eight PNGs** — renders at 2× via headless Edge, downscales with ffmpeg for crisp
text:

```bash
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
CARDS_WIN="C:/ws/continuum/assets/demo-cards"   # adjust to your checkout path
i=0
render_2x () {   # html_query  window_w  window_h  target_w  target_h  out_file
  i=$((i+1))
  "$EDGE" --headless=new --disable-gpu --hide-scrollbars \
    --user-data-dir="$TEMP/edgeprof/p$i" \
    --force-device-scale-factor=2 --window-size="$2,$3" --virtual-time-budget=6000 \
    --screenshot="$CARDS_WIN/_raw$i.png" "file:///$CARDS_WIN/$1"
  ffmpeg -y -loglevel error -i "_raw$i.png" -vf "scale=$4:$5:flags=lanczos" "$6"
  rm -f "_raw$i.png"
}
for card in banner signoff; do
  h=410; [ "$card" = signoff ] && h=450   # signoff's canvas is taller
  for theme in dark light; do
    render_2x "$card.html?theme=$theme&native=1" 1000 "$h" 1000 "$h" "$card-$theme-native.png"
    render_2x "$card.html?theme=$theme"          1920 1080 1920 1080 "$card-$theme.png"
  done
done
```

**Windows/Git Bash gotchas, both hit while building these:**

- Build the `file:///` URL from a **Windows-style** path (`C:/...`). A POSIX `/c/...` path inside a
  `file://` URL isn't auto-translated and Edge fails with `ERR_FILE_NOT_FOUND`.
- Give each invocation its own `--user-data-dir`. Rapid sequential headless launches sharing the
  default profile silently produce no screenshot.
- Don't test for the output with `cygpath -u` unless you've confirmed it exists on the box — a
  failing existence check reads as a render failure when the render actually succeeded.

See [`../../submission/DEMO_SCRIPT.md`](../../submission/DEMO_SCRIPT.md) for how the cards are used
in the shoot. The architecture diagram is a separate mermaid-derived asset — see
[`../architecture/`](../architecture/).
