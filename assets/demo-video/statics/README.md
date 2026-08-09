# Static frames for the demo video

Still images cut into the video's beats — console captures, terminal frames, evidence stills — as
opposed to the recorded screen footage itself. `submission/DEMO_SCRIPT.md` owns which beat uses
what.

**Anything that lands here is judge-facing.** A frame on screen in a submitted video is as public
as a file in [`../../provider-evidence/`](../../provider-evidence/), so this folder is covered by
[`scripts/redact_evidence.py`](../../../scripts/redact_evidence.py): every PNG must be declared
there before `make redact-evidence --check` will pass, with an empty region tuple if it genuinely
needs no mask. That is deliberate friction — it means the first capture dropped in here forces a
decision about the browser chrome it carries, rather than shipping because nobody looked.

Raw window captures on this machine carry two things worth deciding about:

- the signed-in user's **profile photograph** in the browser toolbar, at a fixed position in any
  1920×1080 Edge window;
- on AWS console pages, the **account id**, both in the top-right account tooltip and inside any
  ARN the page prints.

Neither is load-bearing for anything the video claims. Terminal captures carry neither.
