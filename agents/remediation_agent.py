"""
Remediation Agent — given correlated past incidents, proposes the next
remediation action. Reasoning goes through Claude on Amazon Bedrock; if
Bedrock is unreachable (no credentials, throttling), a deterministic
precedent-replay fallback keeps the control flow demonstrable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import boto3
from botocore.config import Config

from agents.correlation_agent import CorrelationMatch
from config import settings
from observability.structured_logger import get_logger

log = get_logger(__name__)

# Same rationale as agents/correlation_agent.py: botocore defaults (60s read
# timeout, backoff retries) can eat the whole Lambda budget under throttling.
_BEDROCK_CLIENT_CONFIG = Config(
    connect_timeout=5,
    read_timeout=15,
    retries={"max_attempts": 2, "mode": "standard"},
)

# Loaded at import time, deliberately. propose_next_step() wraps its Bedrock
# call in a broad `except Exception` that falls back to deterministic
# precedent-replay — a missing prompt file caught there would be
# indistinguishable from a Bedrock outage and would degrade silently. Failing
# at import makes it loud. See prompts/README.md.
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "remediation_agent.txt"
PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8").strip()


# Which reasoning path produced a step. Both Bedrock paths degrade *silently*
# by design (see propose_next_step), so without an explicit marker a throttled
# account is indistinguishable from a healthy one in the output — the demo
# would look identical either way. This is what makes "Claude reasoned about
# this step" a checkable fact rather than a claim.
SOURCE_BEDROCK = "bedrock"
SOURCE_PRECEDENT_REPLAY = "precedent_replay"
SOURCE_NO_PRECEDENT = "no_precedent"


@dataclass
class ProposedAction:
    action: str
    rationale: str
    based_on_incident_id: Optional[str]
    source: str


class RemediationAgent:
    def __init__(self) -> None:
        self._bedrock = None  # lazy — unit tests never touch AWS

    def _client(self):
        if self._bedrock is None:
            self._bedrock = boto3.client(
                "bedrock-runtime",
                region_name=settings.bedrock_region,
                config=_BEDROCK_CLIENT_CONFIG,
            )
        return self._bedrock

    def propose_next_step(
        self, matches: List[CorrelationMatch], step_index: int, alert_text: str = ""
    ) -> ProposedAction:
        if not matches:
            return ProposedAction(
                action="page_on_call_engineer",
                rationale="No correlated precedent found — escalate to human judgement.",
                based_on_incident_id=None,
                source=SOURCE_NO_PRECEDENT,
            )

        best = matches[0]
        try:
            proposed = self._propose_via_bedrock(matches, step_index, alert_text)
        except Exception as exc:  # credentials, throttling, model access — fall back
            log.warning("bedrock_reasoning_fallback", error=str(exc))
            proposed = ProposedAction(
                action=f"replay_remediation_from_incident_{best.incident_id}_step_{step_index}",
                rationale=f"Closest precedent (distance={best.distance:.4f}) previously resolved via this path.",
                based_on_incident_id=best.incident_id,
                source=SOURCE_PRECEDENT_REPLAY,
            )
        log.info(
            "remediation_proposed",
            based_on=proposed.based_on_incident_id,
            step_index=step_index,
            action=proposed.action,
            source=proposed.source,
        )
        return proposed

    def _propose_via_bedrock(self, matches: List[CorrelationMatch], step_index: int, alert_text: str) -> ProposedAction:
        precedents = "\n".join(
            f"- incident {m.incident_id} (distance {m.distance:.4f}): {m.summary}" for m in matches[:3]
        )
        prompt = PROMPT_TEMPLATE.format(
            alert_text=alert_text or "(not provided)",
            step_index=step_index,
            max_steps=settings.max_remediation_steps,
            precedents=precedents,
        )
        response = self._client().converse(
            modelId=settings.bedrock_reasoning_model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 300},
        )
        text = response["output"]["message"]["content"][0]["text"].strip()
        if text.startswith("```"):
            text = text.strip("`").removeprefix("json").strip()
        parsed = json.loads(text)
        return ProposedAction(
            action=parsed["action"],
            rationale=parsed["rationale"],
            based_on_incident_id=matches[0].incident_id,
            source=SOURCE_BEDROCK,
        )
