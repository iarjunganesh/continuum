"""
The resilience demo's centerpiece (see docs/DEMO_RUNBOOK.md).

Kills the running orchestrator process mid-incident, WITHOUT any graceful
shutdown or checkpoint call, to prove the next invocation recovers purely
from CockroachDB state — not from anything this process tried to save on
its way out.

Cross-platform (Windows/macOS/Linux) via psutil.

Usage:
    python scripts/chaos_kill.py --port 8000     # kill whatever listens on :8000
    python scripts/chaos_kill.py --pid 12345     # kill a specific PID
"""
import argparse
import os
import sys

import psutil

# Running as `python scripts/chaos_kill.py` puts scripts/ (not the repo root)
# on sys.path, so observability won't import otherwise.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)


def kill_by_port(port: int) -> int:
    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            for conn in proc.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    log.info("killing_process", pid=proc.pid, name=proc.info["name"],
                             port=port, note="no graceful shutdown — hard kill")
                    proc.kill()
                    killed += 1
                    break
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    if killed == 0:
        log.warning("no_process_found", port=port)
    return killed


def kill_by_pid(pid: int) -> None:
    try:
        proc = psutil.Process(pid)
        log.info("killing_process", pid=pid, name=proc.name(),
                 note="no graceful shutdown — hard kill")
        proc.kill()
    except psutil.NoSuchProcess:
        log.warning("no_process_found", pid=pid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--pid", type=int)
    args = parser.parse_args()
    if args.pid:
        kill_by_pid(args.pid)
    else:
        kill_by_port(args.port)
