# Demo Video

Final cut and its source material. Beat-by-beat script: [`../../submission/DEMO_SCRIPT.md`](../../submission/DEMO_SCRIPT.md).

| File | Use | State |
| --- | --- | --- |
| `continuum.mp4` | The submitted cut — **must be under 3:00** per hackathon rules | pending |
| `continuum.srt` | Captions, timed to the measured narration clips | **generated** — `make voiceover` |
| `kill-recover-take.mp4` | Recording #1: the one continuous take covering beats 6–8 | pending |
| `mcp-query-take.mp4` | Recording #2: the live MCP query, beat 12 | pending |
| `statics/` | Still frames — README top, console, `EXPLAIN` plan, CI badges, ADR list, Lambda console | pending |

**Never hand-edit `continuum.srt`.** It is regenerated from
[`scripts/generate_demo_voiceover.py`](../../scripts/generate_demo_voiceover.py), which owns the
narration text; an edit here is destroyed on the next run and, worse, silently desynchronises the
captions from the committed audio.

**Status:** pending. `README.md`'s Live Demo table says *"Not yet recorded"* and the YouTube badge
renders unlinked — both deliberately, so nothing claims a video that doesn't exist. Update the table
and re-link the badge in the same commit that lands the video, not before.

## Hard requirements (hackathon rules)

- Under 3 minutes, public on YouTube or Vimeo
- Shows the project functioning on its intended platform
- Shows the CockroachDB memory layer at work — the kill-and-resume beat is non-negotiable
- No third-party trademarks or unlicensed music
