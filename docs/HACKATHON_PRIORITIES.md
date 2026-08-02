# Hackathon Priorities

## Goal

Win the CockroachDB × AWS Hackathon by proving one thing:

> AI agents can survive failures without losing memory.

Everything below should strengthen that message.

---

# P0 (Must Have)

## 1. Never Miss Benchmark ⭐⭐⭐⭐⭐

This is the most important benchmark.

### Story

An agent is executing a long-running workflow.

While running:

- kill the process
- terminate Lambda
- restart container
- simulate deployment
- interrupt execution

The agent resumes exactly where it stopped.

No duplicated work.

No missing work.

No corrupted memory.

---

### Metrics

Record:

- recovery time
- checkpoint restore latency
- duplicate operations
- missed operations
- failed recoveries

Ideal table:

| Scenario | Success | Resume Time | Duplicate Tasks | Lost Tasks |
|-----------|---------|-------------|-----------------|------------|
| SIGKILL | ✅ | 850 ms | 0 | 0 |
| Lambda timeout | ✅ | 1.1 s | 0 | 0 |
| Container restart | ✅ | 920 ms | 0 | 0 |
| Deployment restart | ✅ | 1.3 s | 0 | 0 |

---

### Demo

Start workflow.

Kill process.

Restart.

Agent immediately continues from checkpoint.

This should be the centerpiece of the demo.

---

# 2. Concurrent Agent Benchmark

Run

- 10 agents
- 50 agents
- 100 agents

simultaneously writing checkpoints.

Measure

- throughput
- latency
- conflicts
- failures

Show CockroachDB handling concurrent agent memory safely.

---

# 3. Memory Retrieval Benchmark

Measure

- checkpoint lookup
- semantic memory lookup
- vector retrieval
- workflow restoration

Charts should include

P50

P95

P99 latency

---

# 4. End-to-End Demo

Build a polished demo that tells one story.

Incident begins.

↓

Agent investigates.

↓

Agent stores memory.

↓

Crash.

↓

Restart.

↓

Agent resumes.

↓

Incident solved.

The demo should require almost no explanation.

---

# P1 (High Value)

## Benchmark Dashboard

Simple dashboard showing

- checkpoint count
- recovery latency
- memory size
- active agents
- resume success rate

Even static charts help.

---

## Recovery Timeline Visualization

Timeline:

```
Agent starts
↓

Checkpoint #17

↓

Crash

↓

Restart

↓

Checkpoint restored

↓

Execution resumes
```

Very judge-friendly.

---

## Regional Resilience (Stretch)

If possible:

- two CockroachDB regions
- failover test
- continue execution

Only implement if straightforward.

---

## Vector Memory Demo

Show

question

↓

embedding search

↓

previous memories returned

↓

agent reasons using recovered context

This demonstrates long-term semantic memory.

---

## AWS Architecture Diagram

Simple and clean.

Lambda

↓

Bedrock

↓

CockroachDB

↓

Vector Memory

↓

Checkpoint Store

Avoid clutter.

---

# P2 (Nice to Have)

- live observability
- Grafana
- CloudWatch dashboards
- multi-agent collaboration
- MCP live demo
- stress test beyond 100 agents

Only pursue if P0 is complete.

---

# Demo Order

1. Introduce problem
2. Show architecture
3. Start agent
4. Force crash
5. Resume from memory
6. Show benchmark results
7. Explain why CockroachDB made this possible

---

# What Judges Should Remember

> "Continuum is the project where the AI agent was killed, restarted, and resumed exactly where it left off."

If judges remember only one sentence, this should be it.