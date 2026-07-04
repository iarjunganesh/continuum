# ADR 005: Fully Synthetic Incident and Alert Data

## Status
Accepted

## Context
A realistic incident-response demo benefits from realistic-looking data, but Continuum has no real production system to monitor and must not imply it does.

## Decision
All incidents, alerts, services, and remediation actions are synthetically generated (`scripts/generate_synthetic_incidents.py`) and clearly labeled (`incidents.synthetic = true` in schema). No real company names, real infrastructure, or real credentials appear anywhere in the repo, seed data, or demo video.

## Consequences
- Removes any ambiguity about third-party data rights (hackathon rule: entrant must be authorized to use any third-party data)
- Keeps the demo reproducible for judges without needing access to any live system
- Synthetic data is designed to be varied enough (multiple services, severities, regions) that correlation results look meaningfully different across incidents, avoiding an obviously toy dataset
