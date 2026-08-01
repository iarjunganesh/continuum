// k6 smoke test — read-path load characterisation for the Continuum API.
//
//   k6 run tests/load/k6_smoke.js
//   k6 run -e BASE_URL=https://<host> tests/load/k6_smoke.js
//
// Scope is deliberately the READ path only (`/health`, `/incidents/open`).
// POST /alert drives real remediation state into CockroachDB through the
// memory agent — the single write path (ADR 001/003). Hammering it under load
// would fabricate incident state and, worse, exercise concurrent forward-step
// claims outside the controlled conditions
// tests/integration/test_recovery_e2e.py::test_forward_step_claim_is_exactly_once
// asserts them under. Exactly-once is proven there, not here.
//
// `/incidents/open` is the interesting target: every request is a live
// CockroachDB Managed MCP Server round trip (ADR 003), so this measures the
// MCP hop, not just FastAPI.

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

const failures = new Rate('failed_requests');

export const options = {
  stages: [
    { duration: '20s', target: 5 },   // ramp
    { duration: '40s', target: 5 },   // steady
    { duration: '10s', target: 0 },   // drain
  ],
  thresholds: {
    // The MCP round trip dominates; these are smoke-level, not SLOs.
    'http_req_duration{endpoint:health}': ['p(95)<300'],
    'http_req_duration{endpoint:open_incidents}': ['p(95)<2500'],
    failed_requests: ['rate<0.01'],
  },
};

export default function () {
  group('health', () => {
    const res = http.get(`${BASE_URL}/api/v1/health`, {
      tags: { endpoint: 'health' },
    });
    const ok = check(res, {
      'health 200': (r) => r.status === 200,
      'health reports ok': (r) => r.json('status') === 'ok',
    });
    failures.add(!ok);
  });

  group('open_incidents', () => {
    const res = http.get(`${BASE_URL}/api/v1/incidents/open`, {
      tags: { endpoint: 'open_incidents' },
    });
    // 503 is a legitimate response here: the MCP server is an external
    // dependency and the endpoint surfaces its failure rather than masking it.
    // Count it as a failure for the smoke run, but don't treat it as a crash.
    const ok = check(res, {
      'open_incidents responded': (r) => r.status === 200 || r.status === 503,
      'open_incidents 200': (r) => r.status === 200,
    });
    failures.add(!ok);
  });

  sleep(1);
}
