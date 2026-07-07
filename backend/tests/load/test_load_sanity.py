import asyncio
import time
import httpx

API_BASE = "http://127.0.0.1:8000/api/v1"
CONCURRENT_REQUESTS = 20
MAX_DURATION_S = 5.0


async def test_tickets_concurrent():
    url = f"{API_BASE}/tickets"
    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def fetch(client: httpx.AsyncClient):
        async with sem:
            start = time.monotonic()
            response = await client.get(url)
            elapsed = time.monotonic() - start
            return response, elapsed

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        tasks = [fetch(client) for _ in range(CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)

    responses = [r for r, _ in results]
    durations = [d for _, d in results]

    for r in responses:
        assert r.status_code < 500, f"5xx error on /tickets: {r.status_code}"

    max_duration = max(durations)
    p50 = sorted(durations)[len(durations) // 2]
    p95 = sorted(durations)[int(len(durations) * 0.95)]

    print(
        f"/tickets — {CONCURRENT_REQUESTS} concurrent → max={max_duration:.3f}s p50={p50:.3f}s p95={p95:.3f}s"
    )
    assert max_duration < MAX_DURATION_S, (
        f"/tickets max duration {max_duration:.3f}s exceeds {MAX_DURATION_S}s"
    )


async def test_monitoring_health_concurrent():
    url = f"{API_BASE}/monitoring/health"
    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def fetch(client: httpx.AsyncClient):
        async with sem:
            start = time.monotonic()
            response = await client.get(url)
            elapsed = time.monotonic() - start
            return response, elapsed

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        tasks = [fetch(client) for _ in range(CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)

    responses = [r for r, _ in results]
    durations = [d for _, d in results]

    for r in responses:
        assert r.status_code < 500, f"5xx error on /monitoring/health: {r.status_code}"

    max_duration = max(durations)
    p50 = sorted(durations)[len(durations) // 2]
    p95 = sorted(durations)[int(len(durations) * 0.95)]

    print(
        f"/monitoring/health — {CONCURRENT_REQUESTS} concurrent → max={max_duration:.3f}s p50={p50:.3f}s p95={p95:.3f}s"
    )
    assert max_duration < MAX_DURATION_S, (
        f"/monitoring/health max duration {max_duration:.3f}s exceeds {MAX_DURATION_S}s"
    )


def test_load_sanity():
    asyncio.run(test_tickets_concurrent())
    asyncio.run(test_monitoring_health_concurrent())
