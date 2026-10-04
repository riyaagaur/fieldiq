"""Preflight: start from a known-good environment, or find out why not.

    python examples/preflight.py

Prints one line per check and exits non-zero if anything required failed.

This is not part of the pipeline. It exists because the first two days of this
project were lost to environment problems that each looked like a bug in the
code: a package manager installed for the wrong CPU architecture, a TLS
certificate chain the default Python could not verify, and a model that had been
retired out from under the config file and returned 410 Gone.

None of those are interesting problems. All of them are cheaper to find in five
seconds here than in the middle of an 80-case run.
"""

from __future__ import annotations

import json
import os
import sqlite3
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = os.environ.get("MODEL", "nvidia/nemotron-3-super-120b-a12b")

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
COLOUR = {PASS: "\033[32m", FAIL: "\033[31m", WARN: "\033[33m"}
results: list[tuple[str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append((name, status))
    print(f"  {COLOUR[status]}{status}\033[0m  {name}" + (f" — {detail}" if detail else ""))


def load_env(path: str = ".env") -> None:
    """Minimal .env reader, so this script has no dependencies at all."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def check_python() -> None:
    major, minor, patch = sys.version_info[:3]
    version = f"{major}.{minor}.{patch}"
    if (major, minor) >= (3, 11):
        record("Python 3.11+", PASS, version)
    else:
        record("Python 3.11+", FAIL, f"found {version}")


def check_tls() -> None:
    """A verified chain, not a disabled one.

    The default certificate store on a fresh macOS Python install often cannot
    verify this endpoint, which surfaces as SSL: CERTIFICATE_VERIFY_FAILED and is
    very frequently 'fixed' by disabling verification. That is not a fix. If this
    check fails, install certifi and point SSL_CERT_FILE at its bundle.
    """
    try:
        context = ssl.create_default_context()
        try:
            import certifi
            context.load_verify_locations(certifi.where())
            source = "certifi"
        except ImportError:
            source = "system store"
        with urllib.request.urlopen("https://example.com", timeout=10, context=context):
            record("TLS verification", PASS, source)
    except Exception as exc:  # noqa: BLE001
        record("TLS verification", FAIL, f"{type(exc).__name__}: {exc}")


def check_key() -> str | None:
    key = os.environ.get("API_KEY") or os.environ.get("NVIDIA_API_KEY")
    if not key:
        record("API key", FAIL, "set NVIDIA_API_KEY in .env")
        return None
    record("API key", PASS, f"{key[:6]}…{key[-4:]} ({len(key)} chars)")
    return key


def post(url: str, key: str, payload: dict, timeout: int = 30) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def check_model(key: str) -> None:
    """One real call. A reachable endpoint is not a callable model.

    A catalog listing says a model exists, not that this key may invoke it. On
    this project, two thirds of the listed models returned
    '404 Function not found for account' — an access permission, not a typo.
    """
    started = time.perf_counter()
    try:
        # 256 tokens, not 16: a reasoning model spends its first tokens thinking,
        # and a tight budget makes it look mute.
        data = post(f"{BASE_URL}/chat/completions", key, {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Reply with the word ready."}],
            "max_tokens": 256,
            "temperature": 0,
        })
        elapsed = (time.perf_counter() - started) * 1000
        text = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
        if (text or "").strip():
            record("model call", PASS, f"{MODEL} in {elapsed:.0f}ms")
        else:
            record("model call", WARN, "answered with no visible text in 256 tokens")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:160]
        hint = {404: " — this key cannot invoke that model",
                401: " — key rejected",
                403: " — key rejected",
                410: " — model retired; list the catalog and pick a current one"}.get(exc.code, "")
        record("model call", FAIL, f"HTTP {exc.code}{hint}: {body}")
    except Exception as exc:  # noqa: BLE001
        record("model call", FAIL, f"{type(exc).__name__}: {exc}")


def check_tool_calling(key: str) -> None:
    """Can it call a function? An agent that cannot is not a candidate.

    Worth its own check: a model that chats perfectly well may still never emit a
    tool call, and finding that out 80 cases into a run is an expensive way to
    learn it.
    """
    tool = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current temperature for a city.",
            "parameters": {"type": "object",
                           "properties": {"city": {"type": "string"}},
                           "required": ["city"]},
        },
    }]
    try:
        data = post(f"{BASE_URL}/chat/completions", key, {
            "model": MODEL,
            "messages": [{"role": "user", "content": "What is the temperature in Oslo?"}],
            "tools": tool, "max_tokens": 256, "temperature": 0,
        })
        message = (data.get("choices", [{}])[0].get("message", {}) or {})
        if message.get("tool_calls"):
            record("tool calling", PASS, "emitted a tool call")
        else:
            record("tool calling", FAIL, "given a tool, answered in prose instead")
    except Exception as exc:  # noqa: BLE001
        record("tool calling", FAIL, f"{type(exc).__name__}: {str(exc)[:120]}")


def check_sqlite() -> None:
    """WAL mode, because the harness runs cases concurrently."""
    try:
        with tempfile.TemporaryDirectory() as directory:
            conn = sqlite3.connect(Path(directory) / "probe.db")
            mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            conn.execute("CREATE TABLE t (a TEXT)")
            conn.execute("INSERT INTO t VALUES ('x')")
            conn.commit()
            conn.close()
        record("SQLite", PASS, f"{sqlite3.sqlite_version}, journal_mode={mode}")
    except Exception as exc:  # noqa: BLE001
        record("SQLite", FAIL, f"{type(exc).__name__}: {exc}")


def main() -> int:
    load_env()
    print(f"\n  Preflight — {BASE_URL}\n")
    check_python()
    check_tls()
    check_sqlite()
    key = check_key()
    if key:
        check_model(key)
        check_tool_calling(key)

    failed = [name for name, status in results if status == FAIL]
    print(f"\n  {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print(f"  blocking: {', '.join(failed)}\n")
        return 1
    print("  environment is ready\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
