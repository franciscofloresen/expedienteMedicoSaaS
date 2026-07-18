"""Local-only concurrent load harness for Fase 8.

It never creates traffic unless the target host is localhost/127.0.0.1. Use a
migrated ``*_phase8`` database populated with synthetic data and pass a local
development token. The process exits non-zero when the roadmap SLO gate fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class LoadSummary:
    requests: int
    errors: int
    error_rate: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    elapsed_seconds: float
    requests_per_second: float
    passed: bool


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def summarize(latencies_ms: list[float], errors: int, elapsed: float) -> LoadSummary:
    requests = len(latencies_ms)
    error_rate = errors / requests if requests else 1.0
    p95 = percentile(latencies_ms, 0.95)
    p99 = percentile(latencies_ms, 0.99)
    return LoadSummary(
        requests=requests,
        errors=errors,
        error_rate=round(error_rate, 6),
        p50_ms=round(percentile(latencies_ms, 0.50), 2),
        p95_ms=round(p95, 2),
        p99_ms=round(p99, 2),
        elapsed_seconds=round(elapsed, 2),
        requests_per_second=round(requests / elapsed if elapsed else 0.0, 2),
        passed=error_rate < 0.01 and p95 < 1500 and p99 < 3000,
    )


def _local_target(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}


async def run_load(args: argparse.Namespace) -> LoadSummary:
    if not _local_target(args.base_url):
        raise ValueError("Fase-8 load tests are local-only; production traffic is forbidden")
    headers = {"Authorization": f"Bearer {args.token}"}
    scenarios = [
        "/api/v1/pacientes/?limit=50",
        "/api/v1/pacientes/?q=Paciente&limit=50",
        "/api/v1/cie10?q=diabetes&limit=20",
        "/api/v1/cie10?q=E11&limit=20",
    ]
    if args.expediente_id:
        scenarios.extend(
            [
                f"/api/v1/notas/expediente/{args.expediente_id}?limit=100",
                f"/api/v1/consentimientos/expediente/{args.expediente_id}?limit=100",
            ]
        )

    queue: asyncio.Queue[int] = asyncio.Queue()
    for index in range(args.requests):
        queue.put_nowait(index)
    latencies: list[float] = []
    errors = 0

    async with httpx.AsyncClient(
        base_url=args.base_url,
        headers=headers,
        timeout=httpx.Timeout(args.timeout),
    ) as client:

        async def worker() -> None:
            nonlocal errors
            while not queue.empty():
                try:
                    index = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                started = time.perf_counter()
                try:
                    response = await client.get(scenarios[index % len(scenarios)])
                    if response.status_code >= 400:
                        errors += 1
                except httpx.HTTPError:
                    errors += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)
                    queue.task_done()

        started = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(args.concurrency)))
        elapsed = time.perf_counter() - started
    return summarize(latencies, errors, elapsed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="Local development JWT; never a prod token")
    parser.add_argument("--expediente-id")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "Concurrent requests per local application worker. Keep 1 to model Lambda, "
            "which handles one invocation at a time per execution environment."
        ),
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        summary = asyncio.run(run_load(args))
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
