"""
Render benchmark evidence to theme-aware SVG charts (`make charts`).

Charts are GENERATED from a committed evidence run, never screenshotted. A
screenshot of a number is stale the moment the number changes, and this project
has already shipped one benchmark table that silently described the wrong code.
Every chart here carries the run id it came from, so a figure on a slide can
always be traced back to the JSON that produced it.

Outputs, matching the convention in assets/architecture/:

    assets/charts/<name>-{dark,light}.svg        embeddable
    assets/charts/<name>-{dark,light}-16x9.svg   1920x1080, for the demo video

Forms are chosen by the job the data does, not by habit:

  * vector scale   -> line chart. Two series over a growing corpus; the SHAPE is
                      the argument, so it must be a line.
  * throughput     -> bar chart. Magnitude across three discrete levels.
  * kill storm     -> stat tiles, NOT a chart. "50 kills, 0 duplicated" is a
                      headline; drawing a bar of height zero next to one of
                      height fifty communicates less than the words do.
  * lambda timeout -> stat tiles, same reasoning.

Palette validated with the dataviz validator (six checks, both modes) rather
than eyeballed:

    dark  #8b6dff / #e06a3a on #0d0d0d   - all checks pass
    light #6933ff / #b8420f on #ffffff   - all checks pass

#6933ff is CockroachDB's own brand purple, so the index series carries the right
identity rather than an arbitrary hue.

Usage:
    python scripts/build_charts.py                 # newest run under assets/resilience-run/
    python scripts/build_charts.py --run cebb0501
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "assets" / "resilience-run"
OUT_DIR = REPO_ROOT / "assets" / "charts"

# --- theme -----------------------------------------------------------------
# Text wears text tokens, never the series colour; the coloured mark beside a
# label is what carries identity.
THEMES = {
    "dark": {
        "surface": "#0d0d0d",
        "panel": "#161619",
        "ink": "#ffffff",
        "ink2": "#c3c2b7",
        "muted": "#898781",
        "grid": "rgba(255,255,255,0.08)",
        "axis": "rgba(255,255,255,0.22)",
        "series": ["#8b6dff", "#e06a3a"],
        "good": "#3fbf3f",
    },
    "light": {
        "surface": "#ffffff",
        "panel": "#f7f7f5",
        "ink": "#14131a",
        "ink2": "#44424d",
        "muted": "#6b6975",
        "grid": "rgba(0,0,0,0.08)",
        "axis": "rgba(0,0,0,0.25)",
        "series": ["#6933ff", "#b8420f"],
        "good": "#0a7d0a",
    },
}

FONT = "ui-sans-serif, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'Cascadia Code', Consolas, 'SF Mono', monospace"


def _esc(s: object) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _svg(width: int, height: int, body: str, t: dict, title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(title)}">
  <title>{_esc(title)}</title>
  <rect width="{width}" height="{height}" fill="{t["surface"]}"/>
{body}
</svg>
"""


# --- chart: vector scale ---------------------------------------------------
def vector_scale_svg(rows: list[dict], t: dict, run_id: str, w: int, h: int) -> str:
    """Two series, log-x, linear-y. The divergence IS the finding."""
    pad_l, pad_r = int(w * 0.11), int(w * 0.07)
    pad_t, pad_b = int(h * 0.26), int(h * 0.16)
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    xs = [r["vectors"] for r in rows]
    ann = [r.get("ann_warm_p50", 0) for r in rows]
    brute = [r.get("brute_warm_p50", 0) for r in rows]
    # Round the axis top to a readable step — 766/383 are noise; 800/400 read.
    raw_max = max(brute + ann) * 1.18
    step_size = 10 ** (len(str(int(raw_max))) - 1) / 2
    ymax = step_size * (int(raw_max / step_size) + 1)
    scale = h / 1080.0

    def fs(px: float) -> float:  # font size, scaled to canvas
        return round(px * scale, 1)

    def px(i: int) -> float:  # even spacing: corpus sizes are ordinal here
        return pad_l + (pw * i / (len(xs) - 1)) if len(xs) > 1 else pad_l + pw / 2

    def py(v: float) -> float:
        return pad_t + ph - (v / ymax) * ph

    parts: list[str] = []

    # Recessive grid + y labels
    steps = 4
    for i in range(steps + 1):
        v = ymax * i / steps
        y = py(v)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + pw}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 14 * scale:.0f}" y="{y + 5 * scale:.1f}" text-anchor="end" '
            f'fill="{t["muted"]}" font-family="{FONT}" font-size="{fs(20)}">{v:.0f}</text>'
        )
    parts.append(
        f'<text x="{pad_l - 14 * scale:.0f}" y="{pad_t - 22 * scale:.0f}" text-anchor="end" '
        f'fill="{t["muted"]}" font-family="{FONT}" font-size="{fs(19)}">ms</text>'
    )

    # x labels
    for i, xv in enumerate(xs):
        parts.append(
            f'<text x="{px(i):.1f}" y="{pad_t + ph + 34 * scale:.0f}" text-anchor="middle" '
            f'fill="{t["ink2"]}" font-family="{FONT}" font-size="{fs(21)}">{xv:,}</text>'
        )
    parts.append(
        f'<text x="{pad_l + pw / 2:.0f}" y="{pad_t + ph + 70 * scale:.0f}" text-anchor="middle" '
        f'fill="{t["muted"]}" font-family="{FONT}" font-size="{fs(20)}">vectors in the corpus</text>'
    )

    # Series: 2px lines, >=8px markers, 2px surface ring so overlaps stay legible
    for series, colour, label in ((brute, t["series"][1], "full scan"), (ann, t["series"][0], "C-SPANN index")):
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(series))
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="{max(2, 3 * scale):.1f}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for i, v in enumerate(series):
            parts.append(
                f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="{max(5, 7 * scale):.1f}" fill="{colour}" '
                f'stroke="{t["surface"]}" stroke-width="{max(2, 3 * scale):.1f}"/>'
            )
        # Direct label at the last point — identity without relying on colour.
        # BOTH lines sit above the marker: putting the value on the baseline of
        # the point ran the series line straight through the text.
        lx, ly = px(len(series) - 1), py(series[-1])
        parts.append(
            f'<text x="{lx - 20 * scale:.0f}" y="{ly - 56 * scale:.0f}" text-anchor="end" fill="{t["ink"]}" '
            f'font-family="{FONT}" font-size="{fs(26)}" font-weight="700">{label}</text>'
        )
        parts.append(
            f'<text x="{lx - 20 * scale:.0f}" y="{ly - 24 * scale:.0f}" text-anchor="end" fill="{t["ink2"]}" '
            f'font-family="{MONO}" font-size="{fs(23)}">{series[-1]:.0f} ms</text>'
        )

    # Headline
    ratio = brute[-1] / ann[-1] if ann[-1] else 0
    parts.insert(
        0,
        f'<text x="{pad_l}" y="{62 * scale:.0f}" fill="{t["ink"]}" font-family="{FONT}" '
        f'font-size="{fs(42)}" font-weight="700">Vector search stays flat as the corpus grows</text>'
        f'<text x="{pad_l}" y="{104 * scale:.0f}" fill="{t["ink2"]}" font-family="{FONT}" font-size="{fs(25)}">'
        f"At {xs[-1]:,} vectors CockroachDB&#8217;s C-SPANN index is "
        f'<tspan font-weight="700" fill="{t["ink"]}">{ratio:.1f}&#215; faster</tspan> than a full scan'
        f"</text>",
    )
    parts.append(
        f'<text x="{pad_l}" y="{h - 26 * scale:.0f}" fill="{t["muted"]}" font-family="{MONO}" '
        f'font-size="{fs(17)}">warm connection, p50 &#183; run {run_id} &#183; make resilience-bench</text>'
    )
    return _svg(w, h, "\n".join(parts), t, "Vector search latency versus corpus size")


# --- chart: throughput -----------------------------------------------------
def throughput_svg(rows: list[dict], t: dict, run_id: str, w: int, h: int) -> str:
    pad_l, pad_r = int(w * 0.11), int(w * 0.07)
    pad_t, pad_b = int(h * 0.26), int(h * 0.16)
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    scale = h / 1080.0

    def fs(p: float) -> float:
        return round(p * scale, 1)

    vals = [r["throughput"] for r in rows]
    ymax = max(vals) * 1.25
    n = len(rows)
    slot = pw / n
    bw = slot * 0.42

    parts: list[str] = []
    for i in range(5):
        v = ymax * i / 4
        y = pad_t + ph - (v / ymax) * ph
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + pw}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 14 * scale:.0f}" y="{y + 5 * scale:.1f}" text-anchor="end" fill="{t["muted"]}" '
            f'font-family="{FONT}" font-size="{fs(20)}">{v:.0f}</text>'
        )

    for i, r in enumerate(rows):
        cx = pad_l + slot * (i + 0.5)
        bh = (r["throughput"] / ymax) * ph
        y = pad_t + ph - bh
        # 4px rounded data-end, anchored to the baseline
        parts.append(
            f'<path d="M {cx - bw / 2:.1f} {pad_t + ph:.1f} L {cx - bw / 2:.1f} {y + 6 * scale:.1f} '
            f"Q {cx - bw / 2:.1f} {y:.1f} {cx - bw / 2 + 6 * scale:.1f} {y:.1f} "
            f"L {cx + bw / 2 - 6 * scale:.1f} {y:.1f} Q {cx + bw / 2:.1f} {y:.1f} "
            f"{cx + bw / 2:.1f} {y + 6 * scale:.1f} "
            f'L {cx + bw / 2:.1f} {pad_t + ph:.1f} Z" fill="{t["series"][0]}"/>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{y - 18 * scale:.0f}" text-anchor="middle" fill="{t["ink"]}" '
            f'font-family="{FONT}" font-size="{fs(30)}" font-weight="700">{r["throughput"]:.1f}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{pad_t + ph + 36 * scale:.0f}" text-anchor="middle" fill="{t["ink2"]}" '
            f'font-family="{FONT}" font-size="{fs(23)}">{r["agents"]} agents</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{pad_t + ph + 68 * scale:.0f}" text-anchor="middle" fill="{t["muted"]}" '
            f'font-family="{MONO}" font-size="{fs(18)}">{r["failures"]} failures</text>'
        )

    parts.append(
        f'<line x1="{pad_l}" y1="{pad_t + ph:.1f}" x2="{pad_l + pw}" y2="{pad_t + ph:.1f}" '
        f'stroke="{t["axis"]}" stroke-width="1.5"/>'
    )
    parts.insert(
        0,
        f'<text x="{pad_l}" y="{62 * scale:.0f}" fill="{t["ink"]}" font-family="{FONT}" font-size="{fs(42)}" '
        f'font-weight="700">Concurrent agents, zero failures</text>'
        f'<text x="{pad_l}" y="{104 * scale:.0f}" fill="{t["ink2"]}" font-family="{FONT}" font-size="{fs(25)}">'
        f"Agents completing durable checkpoints per second &#183; throughput climbs with concurrency</text>",
    )
    parts.append(
        f'<text x="{pad_l}" y="{h - 26 * scale:.0f}" fill="{t["muted"]}" font-family="{MONO}" font-size="{fs(17)}">'
        f"CockroachDB memory layer only &#183; run {run_id}</text>"
    )
    return _svg(w, h, "\n".join(parts), t, "Concurrent agent throughput")


# --- stat tiles ------------------------------------------------------------
def stat_tiles_svg(title: str, sub: str, tiles: list[tuple], t: dict, run_id: str, w: int, h: int, foot: str) -> str:
    """A hero row. Chosen over a bar chart deliberately: a bar of height zero
    beside one of height fifty says less than the two words do."""
    scale = h / 1080.0

    def fs(p: float) -> float:
        return round(p * scale, 1)

    pad = int(w * 0.08)
    n = len(tiles)
    gap = 28 * scale
    tw = (w - pad * 2 - gap * (n - 1)) / n
    ty = h * 0.34
    th = h * 0.34

    parts = [
        f'<text x="{pad}" y="{h * 0.13:.0f}" fill="{t["ink"]}" font-family="{FONT}" font-size="{fs(46)}" '
        f'font-weight="700">{_esc(title)}</text>',
        f'<text x="{pad}" y="{h * 0.19:.0f}" fill="{t["ink2"]}" font-family="{FONT}" '
        f'font-size="{fs(26)}">{_esc(sub)}</text>',
    ]
    for i, (value, label, emphasis) in enumerate(tiles):
        x = pad + i * (tw + gap)
        colour = t["good"] if emphasis == "good" else t["ink"]
        parts.append(
            f'<rect x="{x:.1f}" y="{ty:.1f}" width="{tw:.1f}" height="{th:.1f}" rx="{18 * scale:.0f}" '
            f'fill="{t["panel"]}" stroke="{t["grid"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + tw / 2:.1f}" y="{ty + th * 0.56:.0f}" text-anchor="middle" fill="{colour}" '
            f'font-family="{FONT}" font-size="{fs(104)}" font-weight="800">{_esc(value)}</text>'
        )
        parts.append(
            f'<text x="{x + tw / 2:.1f}" y="{ty + th * 0.82:.0f}" text-anchor="middle" fill="{t["ink2"]}" '
            f'font-family="{FONT}" font-size="{fs(25)}">{_esc(label)}</text>'
        )
    parts.append(
        f'<text x="{pad}" y="{h - 26 * scale:.0f}" fill="{t["muted"]}" font-family="{MONO}" font-size="{fs(17)}">'
        f"{_esc(foot)} &#183; run {run_id}</text>"
    )
    return _svg(w, h, "\n".join(parts), t, title)


# --- driver ----------------------------------------------------------------
CHROMIUM_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "chromium",
    "google-chrome",
)


def _chromium() -> str | None:
    for candidate in CHROMIUM_CANDIDATES:
        resolved = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if resolved:
            return resolved
    return None


def rasterise(svg_path: Path, width: int, height: int) -> Path | None:
    """Render an SVG to PNG via headless Chromium.

    ffmpeg cannot rasterise SVG (no librsvg in the standard Windows builds) and
    ImageMagick isn't a dependency worth adding for four files, but every machine that
    can edit this video already has Edge or Chrome. Returns None if neither is present —
    the SVGs are still written, and a missing PNG is a smaller problem than a failed build.
    """
    browser = _chromium()
    if not browser:
        print(f"  (no Chromium found — skipped PNG for {svg_path.name})")
        return None

    png_path = svg_path.with_suffix(".png")
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height}",
            f"--screenshot={png_path}",
            svg_path.resolve().as_uri(),
        ],
        capture_output=True,
        check=False,
        timeout=60,
    )
    return png_path if png_path.exists() else None


CHARTABLE_SUITES = ("vector-scale", "agent-throughput", "kill-storm", "lambda-timeout")


def _has_chartable_suite(run: Path) -> bool:
    return any((run / "evidence" / f"{run.name}_{s}.json").exists() for s in CHARTABLE_SUITES)


def newest_run() -> Path:
    """Newest run that actually carries a suite worth charting.

    Not simply the newest folder: a partial run — one suite, or a drill that
    writes its own single result — would otherwise become the source and
    silently regenerate nothing, replacing a full set of charts with none.
    """
    runs = [p for p in RUNS_DIR.iterdir() if p.is_dir()] if RUNS_DIR.exists() else []
    usable = [p for p in runs if _has_chartable_suite(p)]
    if not usable:
        sys.exit(f"no evidence runs with chartable suites under {RUNS_DIR} — run `make resilience-bench` first")
    # Ordered by when the run executed, per its manifest — not by mtime. git
    # does not preserve mtimes, so on a fresh clone "newest folder" is whatever
    # order checkout happened to write, and CI would chart a different run than
    # the machine that generated them. Name breaks ties, so it is total.
    return max(usable, key=lambda p: (_started_utc(p), p.name))


def _started_utc(run: Path) -> str:
    try:
        return str(json.loads((run / "manifest.json").read_text(encoding="utf-8")).get("started_utc") or "")
    except OSError, json.JSONDecodeError:
        return ""


def build(run_dir: Path) -> list[Path]:
    run_id = run_dir.name
    ev = run_dir / "evidence"

    def load(name: str):
        p = ev / f"{run_id}_{name}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    vec, tput, storm, lam = load("vector-scale"), load("agent-throughput"), load("kill-storm"), load("lambda-timeout")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    specs = []
    if vec:
        specs.append(("vector-scale", lambda t, w, h: vector_scale_svg(vec, t, run_id, w, h)))
    if tput:
        specs.append(("throughput", lambda t, w, h: throughput_svg(tput, t, run_id, w, h)))
    if storm:
        specs.append(
            (
                "kill-storm",
                lambda t, w, h: stat_tiles_svg(
                    "Killed mid-incident, fifty times",
                    "Each incident interrupted with a step durably executing, then invoked cold",
                    [
                        (str(storm["n"]), "interrupted", None),
                        (str(storm["resumed"]), "resumed", "good"),
                        (str(storm["duplicated"]), "duplicated actions", "good"),
                        (str(storm["lost"]), "lost steps", "good"),
                    ],
                    t,
                    run_id,
                    w,
                    h,
                    "counted from the durable rows, not from logs",
                ),
            )
        )
    if lam:
        specs.append(
            (
                "lambda-timeout",
                lambda t, w, h: stat_tiles_svg(
                    "AWS killed the function. It still resumed.",
                    "Lambda timeout lowered below the step window — no signal the process can catch",
                    [
                        (str(lam["n"]), "invocations", None),
                        (str(lam["timed_out"]), "killed by AWS", None),
                        (str(lam["resumed"]), "resumed exactly once", "good"),
                        (str(lam["duplicated"]), "duplicated", "good"),
                    ],
                    t,
                    run_id,
                    w,
                    h,
                    "we did not perform these kills",
                ),
            )
        )

    for name, render in specs:
        for mode, theme in THEMES.items():
            for suffix, (w, h) in (("", (1200, 700)), ("-16x9", (1920, 1080))):
                path = OUT_DIR / f"chart-{name}-{mode}{suffix}.svg"
                path.write_text(render(theme, w, h), encoding="utf-8")
                written.append(path)
                # Video editors (Clipchamp, CapCut) cannot import SVG at all, so the
                # 16:9 variants — the ones that go on the timeline — also ship as PNG.
                # The embeddable size stays SVG-only: it is for Markdown, which prefers it.
                if suffix == "-16x9":
                    png = rasterise(path, w, h)
                    if png:
                        written.append(png)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="evidence run id (default: newest)")
    args = ap.parse_args()

    run_dir = (RUNS_DIR / args.run) if args.run else newest_run()
    if not run_dir.exists():
        sys.exit(f"no such run: {run_dir}")

    files = build(run_dir)
    print(f"run {run_dir.name} -> {len(files)} files in {OUT_DIR.relative_to(REPO_ROOT)}")
    for f in sorted(files):
        print(f"  {f.name}")
