#!/usr/bin/env python3
"""Poll service health endpoints; exit nonzero on HTTP error or exhaustion."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request


def wait_for(url: str, attempts: int, sleep_seconds: float) -> None:
    last_error = "unreachable"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if 200 <= response.status < 300:
                    print(f"ready: {url}")
                    return
                last_error = f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 — surface final failure only
            last_error = str(exc)
        time.sleep(sleep_seconds)
        print(f"waiting ({attempt}/{attempts}): {url} ({last_error})", flush=True)
    print(f"ERROR: health check exhausted for {url}: {last_error}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+", help="Health URLs to wait for")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()
    for url in args.urls:
        wait_for(url, args.attempts, args.sleep)


if __name__ == "__main__":
    main()
