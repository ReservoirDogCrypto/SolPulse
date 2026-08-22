"""Minimal HTTP helpers built on urllib.

Every network call in SolPulse goes through here so that timeouts, retries and
failure handling behave identically no matter which source is being read.
Sources are third-party and go down; a source failing must never abort the run,
so callers get an explicit Result rather than an exception.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

USER_AGENT = "SolPulse/1.0 (+https://github.com/topics/solana)"
DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 2


@dataclass
class Result:
    """Outcome of a single fetch: either data, or the reason there is none."""

    ok: bool
    data: Any = None
    error: Optional[str] = None
    source: str = ""
    elapsed_ms: int = 0

    @classmethod
    def failure(cls, source: str, error: str) -> "Result":
        return cls(ok=False, error=error, source=source)


@dataclass
class SourceLog:
    """Records what happened with every source, for the report's status panel."""

    entries: list = field(default_factory=list)

    def record(self, result: Result) -> Result:
        self.entries.append({
            "source": result.source,
            "ok": result.ok,
            "error": result.error,
            "elapsed_ms": result.elapsed_ms,
        })
        return result

    @property
    def healthy(self) -> int:
        return sum(1 for e in self.entries if e["ok"])

    @property
    def total(self) -> int:
        return len(self.entries)


def _request(url: str, payload: Optional[bytes], headers: dict, timeout: int) -> bytes:
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(
    url: str,
    source: str,
    payload: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Result:
    """GET or POST a JSON endpoint, retrying transient failures.

    A POST is made when `payload` is given, which is how the Solana RPC is
    addressed; everything else is a plain GET.
    """
    import time

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last_error = "unknown error"
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            raw = _request(url, body, headers, timeout)
            elapsed = int((time.monotonic() - started) * 1000)
            return Result(ok=True, data=json.loads(raw), source=source,
                          elapsed_ms=elapsed)
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            # Client errors will not fix themselves on retry.
            if 400 <= exc.code < 500 and exc.code != 429:
                break
        except urllib.error.URLError as exc:
            last_error = f"network: {exc.reason}"
        except json.JSONDecodeError:
            last_error = "malformed JSON in response"
            break
        except Exception as exc:  # noqa: BLE001 - a source must never crash the run
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))

    return Result.failure(source, last_error)
