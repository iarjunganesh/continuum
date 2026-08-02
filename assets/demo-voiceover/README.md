# Demo Voiceover

Narration for the ≤ 3-minute submission video, synthesised with **Amazon Polly** —
generative engine, voice **`Ruth`**, region **`eu-central-1`**.

Polly rather than a third-party TTS on purpose: it's the same AWS account and the same
region as the Lambda and the Bedrock calls, so the narration doesn't introduce a vendor
that appears nowhere else in a submission whose claim is that it runs on the sponsors'
stack. `Ruth` over the more familiar `Joanna` for one reason — Joanna is Polly's console
default and reads as stock TTS to anyone who has watched an AWS tutorial.

## Files

- `vo_00-problem … vo_12-close.mp3` — one clip per beat, **2:27.7 total** (147.7 s measured
  via ffprobe). Per-beat files rather than one track: the timeline stays deterministic, and
  re-cutting a single beat doesn't force a full re-record.
- `audition-*.mp3` — scratch, from `--audition`. **Delete before committing**; they are a
  decision aid, not evidence.

## Regenerating

```bash
make voiceover                                          # all clips + captions
python scripts/generate_demo_voiceover.py --clip kill    # one clip after a wording change
python scripts/generate_demo_voiceover.py --table        # re-measure, re-emit the table
python scripts/generate_demo_voiceover.py --audition     # one line in every candidate voice
```

Needs AWS credentials with `polly:SynthesizeSpeech` — `AWS_PROFILE=continuum-admin`. The
default `continuum-bedrock` identity is Bedrock-invoke only and gets `AccessDenied`.

A full regeneration costs roughly **$0.06** at generative rates, billed per character.

## Where the text lives

**[`scripts/generate_demo_voiceover.py`](../../scripts/generate_demo_voiceover.py) is the
source of truth for the narration text** — not the table in
[`submission/DEMO_SCRIPT.md`](../../submission/DEMO_SCRIPT.md). Edit the words in the script,
re-run, and paste the emitted table back into the shooting script.

Editing the doc instead is how the two drift apart, which is worse than either being wrong
alone: the recording session trusts the doc while the timeline trusts the audio, and the
mismatch surfaces in the export.

## Captions

The same command writes [`../demo-video/continuum.srt`](../demo-video/continuum.srt), cut to
sentence boundaries and offset onto the final timeline. Sentence offsets come from Polly
speech marks, with one wrinkle worth knowing: the generative engine emits no speech marks, so
the marks are taken from the *neural* engine reading the same text and scaled by the ratio of
the two measured durations. That lands well inside the ~200 ms a viewer would notice — but it
is a scaled measurement, not a direct one.

Ship the authored track. Auto-generated captions mangle exactly the words that matter here:
*CockroachDB*, *C-SPANN*, *structlog*, *SIGKILL*.
