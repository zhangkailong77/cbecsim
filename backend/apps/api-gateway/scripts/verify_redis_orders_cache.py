#!/usr/bin/env python3
"""One-click verification for Shopee orders Redis cache behavior.

Flow:
1) login and get token
2) get current run_id
3) flush redis db (optional)
4) call orders API to build cache
5) inspect redis keys and ttl
6) call simulate API to invalidate cache
7) call orders API again to rebuild cache
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def http_json(method: str, url: str, *, headers: dict[str, str] | None = None, body: dict | None = None):
    data = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        msg = raw or exc.reason
        raise RuntimeError(f"HTTP {exc.code} {url}: {msg}") from exc
    except Exception as exc:
        raise RuntimeError(f"HTTP request failed {url}: {exc}") from exc


def run_redis_cli(args: list[str]) -> str:
    cmd = ["docker", "exec", "redis", "redis-cli", *args]
    proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"redis-cli failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify shopee orders redis cache end-to-end")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base url")
    parser.add_argument("--username", required=True, help="login username")
    parser.add_argument("--password", required=True, help="login password")
    parser.add_argument("--type", default="all", help="orders query type")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--redis-pattern", default="cbec:cache:shopee:orders:list:*")
    parser.add_argument("--no-flush", action="store_true", help="do not FLUSHDB before verify")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print("[1/8] Login...")
    _, login_data = http_json(
        "POST",
        f"{base_url}/auth/login",
        body={"username": args.username, "password": args.password},
    )
    token = (login_data or {}).get("access_token")
    if not token:
        raise RuntimeError(f"login failed, response: {login_data}")
    auth_header = {"Authorization": f"Bearer {token}"}
    print("  -> token acquired")

    print("[2/8] Get current run...")
    _, run_data = http_json("GET", f"{base_url}/game/runs/current", headers=auth_header)
    run_payload = run_data.get("run") if isinstance(run_data, dict) else None
    run_id = None
    if isinstance(run_payload, dict):
        run_id = run_payload.get("id")
    elif isinstance(run_data, dict):
        run_id = run_data.get("id")
    if not run_id:
        raise RuntimeError(f"no current run found, response: {run_data}")
    print(f"  -> run_id={run_id}")

    if not args.no_flush:
        print("[3/8] FLUSHDB...")
        run_redis_cli(["FLUSHDB"])
        print("  -> ok")
    else:
        print("[3/8] Skip FLUSHDB (--no-flush)")

    query = urllib.parse.urlencode({"type": args.type, "page": args.page, "page_size": args.page_size})
    orders_url = f"{base_url}/shopee/runs/{run_id}/orders?{query}"

    print("[4/8] First orders request (build cache)...")
    _, orders1 = http_json("GET", orders_url, headers=auth_header)
    print(f"  -> total={orders1.get('total')} page={orders1.get('page')}")

    print("[5/8] Scan cache keys...")
    keys_out = run_redis_cli(["--scan", "--pattern", args.redis_pattern])
    keys = [line.strip() for line in keys_out.splitlines() if line.strip()]
    if not keys:
        raise RuntimeError("no cache keys found after first request")
    key = keys[0]
    ttl = run_redis_cli(["TTL", key])
    print(f"  -> key_count={len(keys)}")
    print(f"  -> sample_key={key}")
    print(f"  -> ttl={ttl}")

    print("[6/8] Simulate orders (invalidate cache)...")
    _, sim_data = http_json("POST", f"{base_url}/shopee/runs/{run_id}/orders/simulate", headers=auth_header)
    print(f"  -> generated_order_count={sim_data.get('generated_order_count')}")

    print("[7/8] Scan keys after simulate (expect invalidated/changed)...")
    keys_after_sim_out = run_redis_cli(["--scan", "--pattern", args.redis_pattern])
    keys_after_sim = [line.strip() for line in keys_after_sim_out.splitlines() if line.strip()]
    print(f"  -> key_count_after_sim={len(keys_after_sim)}")

    print("[8/8] Second orders request (rebuild cache)...")
    _, orders2 = http_json("GET", orders_url, headers=auth_header)
    keys_after_rebuild_out = run_redis_cli(["--scan", "--pattern", args.redis_pattern])
    keys_after_rebuild = [line.strip() for line in keys_after_rebuild_out.splitlines() if line.strip()]
    print(f"  -> total={orders2.get('total')} page={orders2.get('page')}")
    print(f"  -> key_count_after_rebuild={len(keys_after_rebuild)}")

    if not keys_after_rebuild:
        raise RuntimeError("cache was not rebuilt after second orders request")

    print("\n✅ Redis orders-cache verification passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n❌ Verification failed: {exc}")
        raise SystemExit(1)
