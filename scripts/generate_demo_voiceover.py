"""
Demo narration: text, audio, measured durations, and captions (`make voiceover`).

**This file is the source of truth for the narration text.** The table in
`submission/DEMO_SCRIPT.md`, the MP3s in `assets/demo-voiceover/`, and the caption
track are all generated from `NARRATION` below — edit the words here, re-run, and
paste the emitted table back into the shooting script. Editing the text in the doc
instead is how the script and the committed audio drift apart, which is worse than
either being wrong on its own: the recording session trusts the doc and the timeline
trusts the audio.

Synthesised with **Amazon Polly** (generative engine) rather than a third-party TTS —
same account and same region as the rest of the AWS integration, and one less vendor
in a submission whose whole claim is that it runs on the sponsors' stack. Cost is
~$0.06 for a full regeneration at generative rates, billed per character.

Captions are cut from Polly **speech marks** rather than estimated from word counts,
so cues land on real sentence boundaries. One wrinkle worth knowing before you trust
the numbers: the generative engine does not emit speech marks at all, so the marks are
taken from the *neural* engine reading the same text and then scaled to the generative
clip's measured duration. Neural and generative phrase a sentence in the same order at
slightly different speeds, so this is accurate to well under the ~200 ms a viewer can
notice on a caption — but it is a scaled measurement, not a direct one.

Usage:
    python scripts/generate_demo_voiceover.py              # synthesise all clips + captions
    python scripts/generate_demo_voiceover.py --table      # measure existing clips, print the table
    python scripts/generate_demo_voiceover.py --clip kill  # re-do one clip after a wording change
    python scripts/generate_demo_voiceover.py --audition   # one line in every candidate voice
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "demo-voiceover"
SRT_PATH = REPO_ROOT / "assets" / "demo-video" / "continuum.srt"
# Committed sentence timings, keyed by voice + text + clip duration. This is what makes
# continuum.srt reproducible: Polly returns a slightly different neural duration on each
# call, so without it every regeneration rewrites the captions with jittered timestamps.
MARKS_PATH = REPO_ROOT / "assets" / "demo-voiceover" / "speech-marks.json"

# Generative Polly, matching the Lambda's region. Ruth reads level and unhurried,
# which is what the kill-and-recover beats need — the tension is in the silence after
# "nothing gets a chance to clean up", and a bright delivery talks over it. Joanna is
# the more familiar choice and deliberately not taken: she is Polly's console default,
# so she reads as stock TTS to anyone who has watched an AWS tutorial.
# Re-audition with --audition; changing this re-synthesises every clip, so pick once.
VOICE_ID = "Ruth"
ENGINE = "generative"
REGION = "eu-central-1"

AUDITION_LINE = "The process is gone. The step is still there, sitting in executing, with nothing alive that owns it."
AUDITION_VOICES = ["Ruth", "Joanna", "Danielle", "Salli", "Tiffany"]


@dataclass(frozen=True)
class Beat:
    """One narration clip. `starts_at` is its position on the final timeline, in
    seconds, and is what turns per-clip speech marks into absolute caption times."""

    index: int
    slug: str
    starts_at: float
    text: str

    @property
    def stem(self) -> str:
        return f"vo_{self.index:02d}-{self.slug}"


# Beat 1 (the opening card, 0:00-0:03) is deliberately silent — the card has to land
# before anyone is asked to listen. `starts_at` values are the timeline in
# submission/DEMO_SCRIPT.md; if a beat moves there, move it here and re-emit the SRT.
NARRATION: list[Beat] = [
    Beat(
        0,
        "problem",
        3.0,
        "The conditions that cause a production incident — a node failure, a bad deploy, "
        "memory exhaustion — are the same conditions that kill the agent responding to it. "
        "And an agent that holds its state in memory doesn't degrade gracefully. It stops. "
        "Then a human restarts the incident from zero, with no idea which remediation actions already ran.",
    ),
    Beat(
        1,
        "reveal",
        24.5,
        # "every invocation starts cold" was here and was false: Lambda reuses a warm
        # environment between back-to-back calls, and the filtered CloudWatch query that
        # seemed to support the claim returns only cold starts by construction. The
        # replacement states what ADR 002 actually guarantees — and is the stronger
        # sentence anyway, because re-reading state is the behaviour, not a side effect
        # of a config setting nobody in the audience can see.
        "Continuum is an incident-response agent whose memory lives in CockroachDB, "
        "not in the process. On AWS Lambda, it never trusts what's in memory — every "
        "invocation re-reads its state from the database first. So the process is "
        "allowed to die.",
    ),
    Beat(
        2,
        "architecture",
        41.0,
        # Was "Five agents, one write path" plus a restatement of the recovery read.
        # "One write path" is our internal shorthand and means nothing to a first-time
        # viewer, and the recovery read now lands in vo_01 where it belongs. This beat
        # earns its time by explaining *why* single-writer matters: it is what makes
        # anything read back trustworthy, which is the precondition for the whole demo.
        "Five agents, and only one of them is allowed to write. Every fact about an "
        "incident goes through a single module into one database — so whatever picks "
        "that incident up next can trust everything it reads.",
    ),
    Beat(
        3,
        "normal",
        53.5,
        # The last clause is the mechanism the entire video depends on, and it used to
        # arrive as a trailing subclause after three proper nouns. Moved to its own
        # sentence and flagged ("and here's the part that matters"), because a viewer
        # who misses *written down before it runs* cannot understand why beat 7 works.
        "An alert fires. Bedrock turns it into a vector, CockroachDB finds the closest "
        "incident it's seen before, Claude proposes the next step. And here's what "
        "matters — the step is written down as executing before it runs, not after.",
    ),
    Beat(
        4,
        "kill",
        72.1,
        "Now watch. The process is killed mid-step. No graceful shutdown. No checkpoint. "
        "Nothing gets a chance to clean up.",
    ),
    Beat(
        5,
        "survives",
        82.8,
        "The process is gone. The step is still there — sitting in executing, with nothing "
        "alive that owns it. That row is the agent's memory, and it outlived the agent.",
    ),
    Beat(
        6,
        "resume",
        95.1,
        # The take is a genuine hybrid — a local process is killed, and the deployed
        # Lambda in eu-central-1 resumes the row it left behind. "A different machine,
        # in a different region, with no memory of this" is the strongest true sentence
        # in the video and it was going unsaid. Do not soften it to "a new invocation":
        # the crossing of an execution-environment boundary is the point.
        "A cold Lambda invocation — a different machine, in a different region, with no "
        "memory of this. It reads CockroachDB first, finds the interrupted step, and "
        "re-runs it. Not from scratch. Not skipped. Not duplicated.",
    ),
    Beat(
        7,
        "scale",
        111.1,
        "That isn't one lucky take. Fifty interrupted incidents. Fifty clean resumes. "
        "Zero duplicated actions, zero lost steps — counted from the durable rows, not from a log.",
    ),
    Beat(
        8,
        "aws",
        123.4,
        "And it isn't only our own kill switch. Here, AWS terminates the function itself, "
        "mid-step, with no signal the process can catch. All fifteen recovered, exactly once.",
    ),
    Beat(
        9,
        "vector",
        135.5,
        # "Six times faster" understated the measured result. docs/RESILIENCE.md and
        # docs/BENCHMARKS.md both record 7.5x at 10,000 vectors (43 -> 77 ms against a
        # full scan's 40 -> 582 ms). Spelled out rather than written "7.5x" so Polly
        # reads it as words; a numeral here comes out clipped.
        "And the memory scales with it. From one hundred incidents to ten thousand, "
        "CockroachDB's vector index stays flat while a full scan climbs away — "
        "seven and a half times faster.",
    ),
    Beat(
        10,
        "mcp",
        147.3,
        # The weakest beat in the original: "queryable live, read-only, called by the
        # application itself" is three facts and no reason to care. Leading with the
        # consequence — one database, so you can just ask it — gives a viewer who has
        # never heard of MCP something to hold on to before the proper noun arrives.
        "And because it's all one database, you can simply ask it — the app querying "
        "its own memory, live, through CockroachDB's managed MCP server.",
    ),
    Beat(
        11,
        "production",
        157.0,
        "Type-checked, linted and gated in CI, with the recovery contract pinned by tests "
        "that hard-kill a real process on every push.",
    ),
    Beat(
        12,
        "close",
        168.0,
        "Agents will keep dying mid-task. Continuum is the one that picks up exactly where it left off.",
    ),
]


def _polly():
    return boto3.client("polly", region_name=REGION)


def _duration(path: Path) -> float:
    """Measured, not estimated — a word-count estimate is exactly the kind of number
    that reads as fact in a doc and is wrong by two seconds on the timeline."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def synthesize(beat: Beat) -> Path:
    """Write the clip's MP3 and return its path."""
    response = _polly().synthesize_speech(Text=beat.text, VoiceId=VOICE_ID, Engine=ENGINE, OutputFormat="mp3")
    path = OUT_DIR / f"{beat.stem}.mp3"
    path.write_bytes(response["AudioStream"].read())
    return path


def speech_marks(beat: Beat, clip_duration: float) -> list[tuple[float, str]]:
    """Cached wrapper around `_fetch_marks`, keyed by voice + text + clip duration.

    Without the cache this file is not reproducible: Polly returns a marginally
    different neural duration on each call, the scale factor moves with it, and every
    run rewrites `continuum.srt` with jittered timestamps even when nothing changed.
    A generated file that changes on every regeneration makes "is this current?"
    unanswerable — which is the whole failure mode `make check-drift` exists to stop.

    The key includes the clip duration, so re-synthesising the audio correctly
    invalidates the cached offsets rather than silently keeping stale ones.
    """
    digest = hashlib.sha256(f"{VOICE_ID}|{ENGINE}|{beat.text}|{clip_duration:.3f}".encode()).hexdigest()
    cache = json.loads(MARKS_PATH.read_text(encoding="utf-8")) if MARKS_PATH.exists() else {}

    entry = cache.get(beat.stem)
    if entry and entry.get("key") == digest:
        return [(offset, sentence) for offset, sentence in entry["offsets"]]

    offsets = _fetch_marks(beat, clip_duration)
    cache[beat.stem] = {"key": digest, "offsets": offsets}
    MARKS_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return offsets


def _fetch_marks(beat: Beat, clip_duration: float) -> list[tuple[float, str]]:
    """Sentence start offsets within the clip, in seconds, paired with their text.

    The generative engine emits no speech marks, so the offsets come from the *neural*
    engine reading the same text and are then scaled by the generative clip's measured
    duration. Both engines phrase the sentences in the same order at slightly different
    speeds, so the scaled offsets land well inside the ~200 ms a viewer would notice —
    but they are a scaled measurement, not a direct one.

    Voices with no neural engine at all (Tiffany, currently) fall back to weighting by
    character count, which is a genuine estimate: fine for a caption, not something to
    quote as timing data.
    """
    try:
        response = _polly().synthesize_speech(
            Text=beat.text, VoiceId=VOICE_ID, Engine="neural", OutputFormat="json", SpeechMarkTypes=["sentence"]
        )
        marks = [json.loads(line) for line in response["AudioStream"].read().decode().splitlines() if line.strip()]
    except ClientError:
        marks = []

    if marks:
        # Measure the neural rendering too, so the two clips are related by a real
        # ratio rather than by an assumption about relative speaking rate.
        neural_audio = _polly().synthesize_speech(Text=beat.text, VoiceId=VOICE_ID, Engine="neural", OutputFormat="mp3")
        scratch = OUT_DIR / f".neural-{beat.slug}.mp3"
        scratch.write_bytes(neural_audio["AudioStream"].read())
        scale = clip_duration / _duration(scratch)
        scratch.unlink()
        return [(mark["time"] / 1000.0 * scale, mark["value"]) for mark in marks]

    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", beat.text) if s.strip()]
    total = sum(len(s) for s in sentences) or 1
    offsets, elapsed = [], 0.0
    for sentence in sentences:
        offsets.append((elapsed, sentence))
        elapsed += clip_duration * len(sentence) / total
    return offsets


def _timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


MAX_CUE_CHARS = 84  # two lines of ~42, the usual subtitle ceiling
MAX_LINE_CHARS = 42
MIN_CUE_SECONDS = 0.7  # below this a cue is gone before it can be read


def _split_cue(start: float, end: float, text: str) -> list[tuple[float, float, str]]:
    """Break an over-long sentence into readable cues at clause boundaries.

    A 160-character cue is legal SRT and unreadable in practice — it fills the lower
    third and changes before a viewer finishes it. Splits land on em-dashes and commas
    (where the voice already pauses), and the time is divided by character share so the
    text keeps pace with the audio.
    """
    # Wrap to real lines first, then pair them. Grouping by character count instead
    # would let two lines of 42 become three when the words don't divide evenly —
    # which is precisely how a 3-line cue shipped once already.
    lines: list[str] = []
    for clause in re.split(r"(?<=[—,;:])\s+", text):
        lines.extend(textwrap.wrap(clause, MAX_LINE_CHARS))
    parts = ["\n".join(lines[i : i + 2]) for i in range(0, len(lines), 2)]

    if len(parts) <= 1:
        return [(start, end, parts[0] if parts else text)]

    out, elapsed = [], start
    shares = _allocate(end - start, [len(p) for p in parts])
    for part, share in zip(parts, shares, strict=True):
        out.append((elapsed, elapsed + share, part))
        elapsed += share
    return out


def _allocate(span: float, weights: list[float]) -> list[float]:
    """Split `span` by weight, but never below `MIN_CUE_SECONDS` for any share.

    Purely proportional allocation produced a 0.34 s fragment — legal SRT, and gone
    from the screen before a viewer registers it. Each cue is floored first and only
    the remainder is distributed, so a short trailing clause borrows from its
    neighbours instead of vanishing.
    """
    count = len(weights)
    if span < count * MIN_CUE_SECONDS:  # too tight to floor — split evenly
        return [span / count] * count
    total = sum(weights) or 1
    remainder = span - count * MIN_CUE_SECONDS
    return [MIN_CUE_SECONDS + remainder * weight / total for weight in weights]


def _wrap(text: str) -> str:
    """At most two lines, each within the per-line ceiling, balanced by word count."""
    if len(text) <= MAX_LINE_CHARS:
        return text
    lines = textwrap.wrap(text, MAX_LINE_CHARS)
    return "\n".join(lines)


def _validate(cues: list[tuple[float, float, str]]) -> list[str]:
    """Structural checks on the finished track, run before it is written.

    Every one of these corresponds to a defect that actually shipped: a cue wider
    than two readable lines, cues overlapping because a beat's `starts_at` moved
    without its predecessor's pad moving, and cues too brief to read. Reasoning about
    the split logic did not catch them; checking the output did.
    """
    problems = []
    previous_end = 0.0
    for number, (start, end, text) in enumerate(cues, start=1):
        if start < previous_end - 1e-3:
            problems.append(f"cue {number}: starts {previous_end - start:.2f}s before the previous one ends")
        if end <= start:
            problems.append(f"cue {number}: non-positive duration")
        elif end - start < MIN_CUE_SECONDS - 1e-3:
            problems.append(f"cue {number}: {end - start:.2f}s is too brief to read")
        lines = text.split("\n")
        if len(lines) > 2:
            problems.append(f"cue {number}: {len(lines)} lines, max 2")
        for line in lines:
            if len(line) > MAX_LINE_CHARS + 3:
                problems.append(f"cue {number}: line is {len(line)} chars — {line[:40]!r}")
        previous_end = end
    return problems


def build_srt(cues: list[tuple[float, float, str]]) -> str:
    """Judges may watch muted, and auto-generated captions mangle the words that
    matter most here — CockroachDB, C-SPANN, structlog. Ship an authored track."""
    split = [piece for cue in cues for piece in _split_cue(*cue)]
    problems = _validate(split)
    if problems:
        raise ValueError("caption track failed validation:\n  " + "\n  ".join(problems))
    blocks = []
    for number, (start, end, text) in enumerate(split, start=1):
        blocks.append(f"{number}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n")
    return "\n".join(blocks)


def _cues_for(beat: Beat, offsets: list[tuple[float, str]], clip_duration: float) -> list[tuple[float, float, str]]:
    """One cue per sentence, offset onto the final timeline.

    Each cue runs until the next sentence starts, so captions never overlap; the last
    one runs to the end of the clip rather than to a guessed reading speed.
    """
    if not offsets:
        return [(beat.starts_at, beat.starts_at + clip_duration, beat.text)]

    cues = []
    for position, (offset, sentence) in enumerate(offsets):
        is_last = position == len(offsets) - 1
        end_offset = clip_duration if is_last else offsets[position + 1][0]
        cues.append((beat.starts_at + offset, beat.starts_at + end_offset, sentence))
    return cues


def emit_table(rows: list[tuple[Beat, float]]) -> str:
    lines = [
        "| Clip | Text | Words | Measured | Starts at |",
        "| --- | --- | --- | --- | --- |",
    ]
    for beat, duration in rows:
        words = len(beat.text.split())
        lines.append(
            f"| `{beat.stem}` | {beat.text} | {words} | {duration:.1f}s | "
            f"{int(beat.starts_at // 60)}:{int(beat.starts_at % 60):02d} |"
        )
    total = sum(duration for _, duration in rows)
    lines.append("")
    lines.append(f"**Narration spine {int(total // 60)}:{total % 60:04.1f}** ({total:.1f}s measured via ffprobe).")
    return "\n".join(lines)


def audition() -> None:
    """Synthesise the same line in every candidate voice so the choice is made by
    listening rather than by reading a voice name in the AWS docs."""
    client = _polly()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for voice in AUDITION_VOICES:
        response = client.synthesize_speech(Text=AUDITION_LINE, VoiceId=voice, Engine=ENGINE, OutputFormat="mp3")
        path = OUT_DIR / f"audition-{voice}.mp3"
        path.write_bytes(response["AudioStream"].read())
        print(f"  {voice:10s} {_duration(path):5.1f}s  {path.relative_to(REPO_ROOT)}")
    print("\nListen, pick one, set VOICE_ID at the top of this script, then re-run without --audition.")
    print("Delete the audition files before committing — they are scratch, not evidence.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", help="regenerate a single clip by slug (e.g. kill)")
    parser.add_argument("--table", action="store_true", help="measure existing clips and print the table only")
    parser.add_argument("--audition", action="store_true", help="synthesise one line in every candidate voice")
    args = parser.parse_args()

    if args.audition:
        audition()
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected = [b for b in NARRATION if args.clip in (None, b.slug)]
    if not selected:
        print(f"No clip with slug {args.clip!r}. Known: {', '.join(b.slug for b in NARRATION)}")
        return 1

    rows: list[tuple[Beat, float]] = []
    cues: list[tuple[float, float, str]] = []

    for beat in NARRATION:
        path = OUT_DIR / f"{beat.stem}.mp3"
        if beat in selected and not args.table:
            path = synthesize(beat)
            print(f"  {beat.stem:22s} {_duration(path):5.1f}s  {len(beat.text.split()):3d} words")
        elif not path.exists():
            # A --clip or --table run still needs every other clip on disk: the table
            # and the caption track cover the whole timeline, not the one clip changed.
            print(f"  {beat.stem:22s} MISSING — run without --clip/--table to synthesise every clip")
            return 1
        duration = _duration(path)
        rows.append((beat, duration))
        cues.extend(_cues_for(beat, speech_marks(beat, duration), duration))

    SRT_PATH.parent.mkdir(parents=True, exist_ok=True)
    srt = build_srt(cues)
    SRT_PATH.write_text(srt, encoding="utf-8")
    # Count what was written, not the pre-split sentence count — they differ, and
    # reporting the wrong one makes the file look unchanged when it isn't.
    written_cues = sum(1 for block in srt.strip().split("\n\n") if block.strip())
    print(f"\nCaptions -> {SRT_PATH.relative_to(REPO_ROOT)} ({written_cues} cues)")
    print("\nPaste into submission/DEMO_SCRIPT.md:\n")
    print(emit_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
