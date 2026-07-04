"""
Generates a synthetic corpus of past incidents for seeding incident_embeddings
and incidents. No real service names, no real infra — see ADR 005.

Usage:
    python scripts/generate_synthetic_incidents.py --out data/synthetic/incidents_seed.jsonl --count 40
"""
import argparse
import json
import random
import uuid
from datetime import datetime, timedelta

SERVICES = ["checkout-api", "auth-service", "recommendation-engine", "search-index", "billing-worker"]
REGIONS = ["us-east-1", "eu-west-1", "ap-southeast-1"]
SEVERITIES = ["low", "medium", "high", "critical"]

INCIDENT_TEMPLATES = [
    "Elevated p99 latency on {service} in {region}, likely connection pool exhaustion",
    "Error rate spike on {service} following recent deploy in {region}",
    "{service} memory usage climbing steadily, suspected leak in {region}",
    "Downstream timeout cascading from {service} into dependent services ({region})",
    "{service} autoscaling failed to keep pace with traffic spike in {region}",
    "Database connection saturation affecting {service} in {region}",
]

REMEDIATION_PATHS = [
    ["snapshot_service_metrics", "roll_back_last_deploy", "verify_error_rate_recovered"],
    ["snapshot_service_metrics", "scale_out_replica_count", "verify_latency_recovered"],
    ["drain_connection_pool", "restart_connection_pool", "verify_connections_healthy"],
    ["apply_circuit_breaker_downstream", "scale_out_replica_count", "verify_timeouts_cleared"],
    ["raise_autoscaling_target", "scale_out_replica_count", "verify_capacity_headroom"],
]


def generate(count: int):
    records = []
    for _ in range(count):
        service = random.choice(SERVICES)
        region = random.choice(REGIONS)
        template = random.choice(INCIDENT_TEMPLATES)
        summary = template.format(service=service, region=region)
        opened_at = datetime.utcnow() - timedelta(days=random.randint(1, 180))
        records.append({
            "incident_id": str(uuid.uuid4()),
            "correlation_id": f"synthetic-{uuid.uuid4().hex[:8]}",
            "service": service,
            "region": region,
            "severity": random.choice(SEVERITIES),
            "summary": summary,
            "remediation_steps": random.choice(REMEDIATION_PATHS),
            "state": "resolved",
            "opened_at": opened_at.isoformat(),
            "synthetic": True,
        })
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--count", type=int, default=40)
    args = parser.parse_args()

    records = generate(args.count)
    with open(args.out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(records)} synthetic incidents to {args.out}")
