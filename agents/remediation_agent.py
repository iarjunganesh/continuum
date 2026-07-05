"""
Remediation Agent — given correlated past incidents, proposes the next
remediation action. Reasoning goes through Claude on Amazon Bedrock; if
Bedrock is unreachable (no credentials, throttling), a deterministic
precedent-replay fallback keeps the control flow demonstrable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

import boto3

from agents.correlation_agent import CorrelationMatch
from config import settings
from observability.structured_logger import get_logger

log = get_logger(__name__)

PROMPT_TEMPLATE = """You are an incident-remediation planner. All data is synthetic (hackathon demo).

Alert: {alert_text}
Current remediation step index: {step_index} (of {max_steps} total steps).
Closest correlated past incidents (nearest first):
{precedents}

Propose exactly ONE next remediation action for this step, as strict JSON:
{{"action": "<snake_case_action>", "rationale": "<one sentence>"}}
Base it on the closest precedent when one exists. Output only the JSON."""


@dataclass
class ProposedAction:
    action: str
    rationale: str
    based_on_incident_id: Optional[str]


class RemediationAgent:
    def __init__(self) -> None:
        self._bedrock = None  # lazy — unit tests never touch AWS

    def _client(self):
        if self._bedrock is None:
            self._bedrock = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        return self._bedrock

    def propose_next_step(self, matches: List[CorrelationMatch], step_index: int,
                          alert_text: str = "") -> ProposedAction:
        if not matches:
            return ProposedAction(
                action="page_on_call_engineer",
                rationale="No correlated precedent found — escalate to human judgement.",
                based_on_incident_id=None,
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
            )
        log.info("remediation_proposed", based_on=proposed.based_on_incident_id,
                 step_index=step_index, action=proposed.action)
        return proposed

    def _propose_via_bedrock(self, matches: List[CorrelationMatch], step_index: int,
                             alert_text: str) -> ProposedAction:
        precedents = "\n".join(
            f"- incident {m.incident_id} (distance {m.distance:.4f}): {m.summary}"
            for m in matches[:3]
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
        )
