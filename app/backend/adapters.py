"""Adapters wrap subscription-backed CLIs (claude, aas) so the UI never needs an API key.

Each adapter is an async generator that yields events:
    {"type": "delta",  "text": "..."}      partial text
    {"type": "meta",   "data": {...}}      side info (claude_session_id, model, ...)
    {"type": "error",  "message": "..."}   adapter-level failure
    {"type": "done",   "text": "..."}      final assembled text
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import random
import shutil
import termios
from typing import AsyncIterator


class AdapterError(Exception):
    pass


# StreamReader line-buffer cap for the stream-json reader. claude/grok emit one
# JSON event per line; a single event can be large when the model writes a whole
# file in one tool block (e.g. a LaTeX manuscript or two big TikZ figures). The
# old 1 MiB cap made readline() drop the line AND raise ValueError ("Separator is
# not found, and chunk exceed the limit") — which crashed the whole turn. We raise
# the cap and, in the read loop, recover from an oversized line instead of raising.
_READER_LIMIT = 64 * 2 ** 20  # 64 MiB


# ---------------------------------------------------------------------------
# Claude adapter — wraps `claude -p` (Claude Code CLI, subscription auth).
# ---------------------------------------------------------------------------

async def claude_stream(
    message: str,
    system_prompt: str,
    cwd: str,
    model: str = "claude-sonnet-4-6",
    effort: str | None = None,
    resume_session_id: str | None = None,
    extra_env: dict | None = None,
) -> AsyncIterator[dict]:
    if shutil.which("claude") is None:
        yield {"type": "error", "message": "claude CLI not found on PATH"}
        return

    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose",
           "--include-partial-messages", "--permission-mode", "bypassPermissions",
           "--model", model]
    if effort:
        cmd += ["--effort", effort]
    if resume_session_id:
        cmd += ["--resume", resume_session_id]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    cmd += [message]

    # PTY trick: Node CLIs (claude is Node) block-buffer stdout when piped.
    # Routing stdout through a pty makes claude think it's a terminal so it
    # line-buffers each JSON event, which is what we need for real streaming.
    master_fd, slave_fd = pty.openpty()
    # Raw mode on slave: no \n -> \r\n translation, no echo, no canonicalization.
    try:
        attrs = termios.tcgetattr(slave_fd)
        attrs[1] &= ~termios.OPOST  # no output post-processing
        attrs[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
    except termios.error:
        pass
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=slave_fd,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        # extra_env (per-subprocess only — never mutate the global os.environ) is
        # how the DeepSeek adapter points THIS claude -p at a local Anthropic-
        # compatible proxy without touching the user's normal Claude CLI / OAuth.
        env={**os.environ, "FORCE_COLOR": "0", "NO_COLOR": "1", "TERM": "dumb",
             **(extra_env or {})},
    )
    os.close(slave_fd)

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(limit=_READER_LIMIT)
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_read_pipe(
        lambda: protocol, os.fdopen(master_fd, "rb", buffering=0)
    )

    assembled: list[str] = []
    claude_session_id: str | None = None

    try:
        while True:
            try:
                raw_line = await reader.readline()
            except (ValueError, asyncio.LimitOverrunError):
                # A single stream-json event exceeded the reader buffer (e.g. a
                # whole file written in one tool block). readline() has already
                # dropped the oversized line; skip it and keep streaming instead
                # of letting the exception crash the entire turn.
                yield {"type": "status", "status": "responding"}
                continue
            if not raw_line:
                break  # EOF
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = evt.get("type")
            if etype == "system" and evt.get("subtype") == "init":
                claude_session_id = evt.get("session_id")
                yield {
                    "type": "meta",
                    "data": {
                        "claude_session_id": claude_session_id,
                        "model": evt.get("model"),
                    },
                }
            elif etype == "stream_event":
                ev = evt.get("event") or {}
                ev_type = ev.get("type")
                if ev_type == "content_block_start":
                    block = ev.get("content_block") or {}
                    btype = block.get("type")
                    if btype == "thinking":
                        yield {"type": "status", "status": "thinking"}
                    elif btype == "text":
                        yield {"type": "status", "status": "responding"}
                elif ev_type == "content_block_delta":
                    delta = ev.get("delta") or {}
                    dtype = delta.get("type")
                    if dtype == "thinking_delta":
                        chunk = delta.get("thinking") or ""
                        if chunk:
                            yield {"type": "thinking", "text": chunk}
                    elif dtype == "text_delta":
                        text = delta.get("text") or ""
                        if text:
                            assembled.append(text)
                            yield {"type": "delta", "text": text}
            elif etype == "assistant":
                msg = evt.get("message") or {}
                for block in msg.get("content", []):
                    if block.get("type") == "text" and not assembled:
                        text = block.get("text", "")
                        if text:
                            assembled.append(text)
                            yield {"type": "delta", "text": text}
            elif etype == "result":
                final = evt.get("result") or "".join(assembled)
                # Real token usage for this turn. For a resumed session the bulk
                # of the prompt lands in cache_read_input_tokens, so the context
                # window occupancy is the SUM of all input buckets + output.
                usage = evt.get("usage") or {}
                if usage:
                    yield {"type": "meta", "data": {"usage": usage}}
                yield {"type": "done", "text": final, "meta": {
                    "duration_ms": evt.get("duration_ms"),
                    "total_cost_usd": evt.get("total_cost_usd"),
                    "claude_session_id": claude_session_id,
                    "usage": usage,
                }}
                return
    finally:
        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        try:
            await proc.wait()
        except Exception:
            pass
        try:
            transport.close()
        except Exception:
            pass

    if proc.returncode and proc.returncode != 0:
        stderr = (await proc.stderr.read()).decode("utf-8", errors="replace") if proc.stderr else ""
        yield {"type": "error", "message": f"claude exited {proc.returncode}: {stderr[:500]}"}
        return

    # If we reached EOF without a "result" event, emit assembled as done.
    yield {"type": "done", "text": "".join(assembled), "meta": {"claude_session_id": claude_session_id}}


# ---------------------------------------------------------------------------
# Grok adapter — wraps user's `aas` CLI which already uses Grok subscription.
# ---------------------------------------------------------------------------

async def grok_stream(
    message: str,
    system_prompt: str,
    cwd: str,
    model: str = "grok-build",
    effort: str | None = None,
    resume_session_id: str | None = None,
    best_of_n: int | None = None,
    check_loop: bool = False,
    memory_mode: str | None = None,
) -> AsyncIterator[dict]:
    grok_bin = shutil.which("grok")
    if not grok_bin:
        candidate = os.path.expanduser("~/.grok/bin/grok")
        if os.path.exists(candidate):
            grok_bin = candidate
        else:
            yield {"type": "error", "message": "grok CLI not found on PATH or in ~/.grok/bin"}
            return

    cmd = [
        grok_bin,
        "--output-format", "streaming-json",
        "--no-alt-screen",
        "--permission-mode", "bypassPermissions",
        "--model", model,
    ]
    if effort:
        cmd += ["--effort", effort]
    if resume_session_id:
        cmd += ["--resume", resume_session_id]
    if best_of_n and best_of_n > 1:
        cmd += ["--best-of-n", str(int(best_of_n))]
    if check_loop:
        cmd += ["--check"]
    if memory_mode == "on":
        cmd += ["--experimental-memory"]
    elif memory_mode == "off":
        cmd += ["--no-memory"]
    if system_prompt:
        cmd += ["--system-prompt-override", system_prompt]
    # `-p / --single` takes the prompt as its value; put it last so all flags parse cleanly.
    cmd += ["-p", message]

    # PTY trick: same reason as claude_stream — defeat Node/Rust CLI block buffering.
    master_fd, slave_fd = pty.openpty()
    try:
        attrs = termios.tcgetattr(slave_fd)
        attrs[1] &= ~termios.OPOST
        attrs[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
    except termios.error:
        pass
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=slave_fd,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env={**os.environ, "FORCE_COLOR": "0", "NO_COLOR": "1", "TERM": "dumb"},
    )
    os.close(slave_fd)

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(limit=_READER_LIMIT)
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_read_pipe(
        lambda: protocol, os.fdopen(master_fd, "rb", buffering=0)
    )

    assembled: list[str] = []
    grok_session_id: str | None = None
    in_text = False

    try:
        while True:
            try:
                raw_line = await reader.readline()
            except (ValueError, asyncio.LimitOverrunError):
                # A single stream-json event exceeded the reader buffer (e.g. a
                # whole file written in one tool block). readline() has already
                # dropped the oversized line; skip it and keep streaming instead
                # of letting the exception crash the entire turn.
                yield {"type": "status", "status": "responding"}
                continue
            if not raw_line:
                break  # EOF
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = evt.get("type")
            if etype == "thought":
                yield {"type": "thinking", "text": evt.get("data") or ""}
            elif etype == "text":
                if not in_text:
                    yield {"type": "status", "status": "responding"}
                    in_text = True
                t = evt.get("data") or ""
                if t:
                    assembled.append(t)
                    yield {"type": "delta", "text": t}
            elif etype == "end":
                grok_session_id = evt.get("sessionId")
                # main.py persists session id via meta event using key claude_session_id
                # (shared db column for both adapters)
                if grok_session_id:
                    yield {"type": "meta", "data": {"claude_session_id": grok_session_id}}
                final = "".join(assembled)
                yield {"type": "done", "text": final, "meta": {
                    "claude_session_id": grok_session_id,
                    "stop_reason": evt.get("stopReason"),
                }}
                return
    finally:
        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        try:
            await proc.wait()
        except Exception:
            pass
        try:
            transport.close()
        except Exception:
            pass

    if proc.returncode and proc.returncode != 0:
        stderr = (await proc.stderr.read()).decode("utf-8", errors="replace") if proc.stderr else ""
        yield {"type": "error", "message": f"grok exited {proc.returncode}: {stderr[:500]}"}
        return

    yield {"type": "done", "text": "".join(assembled), "meta": {"claude_session_id": grok_session_id}}


# ---------------------------------------------------------------------------
# DeepSeek adapter — drives the SAME `claude -p` harness, pointed at DeepSeek's
# NATIVE Anthropic-compatible endpoint (https://api.deepseek.com/anthropic).
# DeepSeek V4 is officially integrated with Claude Code: it speaks the Anthropic
# Messages API directly, supports 1M context, thinking mode, function calling,
# and auto-sets reasoning effort to "max" for Claude-Code-style agent requests.
# So a DeepSeek node inherits the full agent harness for free — file tools,
# permission mode, --resume memory, thinking, --effort, dispatch parsing, PTY
# streaming — with NO translation proxy in between.
#
# The override is injected via extra_env so it applies ONLY to this subprocess.
# The user's normal `claude` CLI and the Claude nodes are untouched — they keep
# using subscription OAuth. Do NOT set ANTHROPIC_BASE_URL globally anywhere.
#
# DEEPSEEK_BASE_URL can override the endpoint (e.g. to route via a local proxy
# instead), but the default needs no extra process running.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Overload retry for the API-key adapters (deepseek, glm).
#
# api.z.ai (and api.deepseek.com) return HTTP 529 "overloaded" (Z.ai code 1305)
# when the ACCOUNT'S CONCURRENCY LIMIT is exceeded — NOT a global outage. A
# single sequential request always succeeds; only concurrent bursts trip it
# (reproduced: 6 concurrent glm-5.2 requests → 3×529). The AEC system dispatches
# up to 5 agents at once, so this fires regularly under multi-agent load.
#
# The 529 is transient — a slot frees the moment another agent's request lands.
# So re-running the same `claude -p` turn after a short backoff almost always
# succeeds. This wrapper inspects the terminal event of each attempt; if it
# carries an overload signature, it backs off and retries the whole turn,
# preserving live streaming for the eventual success. Live deltas from a
# successful attempt are yielded as they arrive; only the terminal event is
# held back until we know it is not a retryable error.
# ---------------------------------------------------------------------------

# substrings (lower-cased) that mark a terminal event as a retryable overload
_OVERLOAD_PATTERNS = (
    "529", "1305", "overloaded", "temporarily overloaded",
    "429", "rate limit", "rate_limit", "too many requests",
    "service may be temporarily",
)
# backoff seconds before each retry (index 0 → before retry #1)
_OVERLOAD_BACKOFF = (5.0, 12.0, 25.0)


def _event_is_overload(ev: dict) -> bool:
    """True if a terminal event (agent_done / error) carries an overload
    signature in its text/message (529 / 429 / overloaded)."""
    if not isinstance(ev, dict):
        return False
    txt = ev.get("text") or ev.get("message") or ""
    if not txt:
        return False
    low = txt.lower()
    return any(p in low for p in _OVERLOAD_PATTERNS)


async def _claude_stream_with_overload_retry(
    *,
    message: str,
    system_prompt: str,
    cwd: str,
    model: str,
    effort: str | None,
    resume_session_id: str | None,
    extra_env: dict | None,
    label: str = "model",
) -> AsyncIterator[dict]:
    """Run claude_stream, retrying the whole turn when the terminal event is an
    overload error (529/429). Live events stream through; only the terminal
    agent_done/error is buffered per attempt so an overload can be swallowed and
    the turn re-attempted without the UI seeing a dead error bubble."""
    max_retries = len(_OVERLOAD_BACKOFF)
    agent_id = None
    for attempt in range(max_retries + 1):
        terminal = None
        async for ev in claude_stream(
            message=message,
            system_prompt=system_prompt,
            cwd=cwd,
            model=model,
            effort=effort,
            resume_session_id=resume_session_id,
            extra_env=extra_env,
        ):
            if agent_id is None and isinstance(ev, dict) and ev.get("agent"):
                agent_id = ev.get("agent")
            if isinstance(ev, dict) and ev.get("type") in ("agent_done", "error"):
                terminal = ev  # hold back until we know it's not overload
                continue
            yield ev
        if terminal is None:
            return  # stream ended without a terminal event — nothing to retry
        if not _event_is_overload(terminal) or attempt >= max_retries:
            yield terminal
            return
        # overload → backoff + retry
        delay = _OVERLOAD_BACKOFF[attempt] + random.uniform(0.0, 2.0)
        yield {"type": "thinking", "agent": agent_id,
               "text": f"⚠ {label} gateway overloaded (529) — retry {attempt + 1}/{max_retries} in {delay:.0f}s" }
        await asyncio.sleep(delay)


async def deepseek_stream(
    message: str,
    system_prompt: str,
    cwd: str,
    model: str = "deepseek-v4-flash",
    effort: str | None = None,
    resume_session_id: str | None = None,
) -> AsyncIterator[dict]:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        yield {"type": "error",
               "message": "DEEPSEEK_API_KEY not set in the environment"}
        return
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/anthropic")
    extra_env = {
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_API_KEY": key,
        "ANTHROPIC_AUTH_TOKEN": key,
    }
    async for ev in _claude_stream_with_overload_retry(
        message=message,
        system_prompt=system_prompt,
        cwd=cwd,
        model=model,
        effort=effort,
        resume_session_id=resume_session_id,
        extra_env=extra_env,
        label="deepseek",
    ):
        yield ev


# ---------------------------------------------------------------------------
# GLM adapter (Zhipu) — identical strategy to DeepSeek: drive the SAME `claude -p`
# harness, pointed at GLM's NATIVE Anthropic-compatible endpoint. Z.ai / Zhipu
# officially integrate GLM with Claude Code (the CLI speaks the Anthropic Messages
# API directly), so a GLM node inherits the full agent harness for free — file
# tools, permission mode, --resume memory, thinking, --effort, dispatch parsing,
# PTY streaming — with NO translation proxy in between.
#
# Default endpoint is Z.ai (international). Inside China, set GLM_BASE_URL to
# https://open.bigmodel.cn/api/anthropic. Override is injected via extra_env so it
# applies ONLY to this subprocess — Claude nodes + the user's terminal `claude`
# keep using subscription OAuth, fully unaffected. Never set ANTHROPIC_BASE_URL
# globally. GLM is billed per-token (API), unlike the Claude subscription.
# ---------------------------------------------------------------------------

async def glm_stream(
    message: str,
    system_prompt: str,
    cwd: str,
    model: str = "glm-4.6",
    effort: str | None = None,
    resume_session_id: str | None = None,
) -> AsyncIterator[dict]:
    key = os.environ.get("GLM_API_KEY")
    if not key:
        yield {"type": "error",
               "message": "GLM_API_KEY not set in the environment"}
        return
    base_url = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
    extra_env = {
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_API_KEY": key,
        "ANTHROPIC_AUTH_TOKEN": key,
    }
    async for ev in _claude_stream_with_overload_retry(
        message=message,
        system_prompt=system_prompt,
        cwd=cwd,
        model=model,
        effort=effort,
        resume_session_id=resume_session_id,
        extra_env=extra_env,
        label="glm",
    ):
        yield ev


# ---------------------------------------------------------------------------

def get_stream(model: str):
    if model == "claude":
        return claude_stream
    if model == "grok":
        return grok_stream
    if model == "deepseek":
        return deepseek_stream
    if model == "glm":
        return glm_stream
    if model in ("antigravity", "gemini"):
        return antigravity_stream
    raise AdapterError(f"unknown model adapter: {model}")


# ---------------------------------------------------------------------------
# Antigravity Multi-Account Pool Adapter
# Automatically rotates across Antigravity Pro keys on 429/Quota limit
# ---------------------------------------------------------------------------

from pathlib import Path
import time


class AntigravityKeyPool:
    def __init__(self):
        self._keys: list[str] = []
        self._current_idx = 0
        self._cooldowns: dict[int, float] = {}
        self._reload_keys()

    def _reload_keys(self):
        keys = []
        env_file = Path(__file__).resolve().parent.parent / ".antigravity_keys.env"
        if env_file.exists():
            with env_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ANTIGRAVITY_KEY_") and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val and val not in keys:
                            keys.append(val)
        for i in range(1, 10):
            k = os.environ.get(f"ANTIGRAVITY_KEY_{i}") or os.environ.get(f"GEMINI_API_KEY_{i}")
            if k and k not in keys:
                keys.append(k)
        if not keys and os.environ.get("GEMINI_API_KEY"):
            keys.append(os.environ["GEMINI_API_KEY"])
        self._keys = keys

    @property
    def total_keys(self) -> int:
        self._reload_keys()
        return len(self._keys)

    def get_key(self) -> tuple[str | None, int, int]:
        self._reload_keys()
        if not self._keys:
            return None, 0, 0
        now = time.time()
        n = len(self._keys)
        for offset in range(n):
            idx = (self._current_idx + offset) % n
            cool = self._cooldowns.get(idx, 0)
            if now >= cool:
                self._current_idx = idx
                return self._keys[idx], idx + 1, n
        earliest_idx = min(range(n), key=lambda i: self._cooldowns.get(i, 0))
        self._current_idx = earliest_idx
        return self._keys[earliest_idx], earliest_idx + 1, n

    def mark_rate_limited(self, idx_1_based: int, cooldown_seconds: float = 60.0):
        idx = idx_1_based - 1
        if 0 <= idx < len(self._keys):
            self._cooldowns[idx] = time.time() + cooldown_seconds
            self._current_idx = (idx + 1) % len(self._keys)


_ag_pool = AntigravityKeyPool()


_MODEL_CASCADE = [
    "gemini-3.7-flash",           # 1. Gemini 3.7 Flash High (Chạy chính)
    "claude-opus-4-6",            # 2. Claude Opus 4.6 Thinking
    "claude-sonnet-4-6",          # 2b. Claude Sonnet 4.6 Thinking
    "gemma-4-31b-it",             # 3. GPT-OSS 120B
]


async def antigravity_stream(
    message: str,
    system_prompt: str,
    cwd: str,
    model: str = "gemini-3.7-flash",
    effort: str | None = None,
    resume_session_id: str | None = None,
) -> AsyncIterator[dict]:
    import httpx

    # Build model trial list starting with the requested/default model
    trial_models = [model] + [m for m in _MODEL_CASCADE if m != model]
    max_account_retries = max(1, _ag_pool.total_keys)
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    for acc_attempt in range(max_account_retries):
        key, acc_num, total_accs = _ag_pool.get_key()
        if not key:
            yield {
                "type": "error",
                "message": "Chưa tìm thấy Antigravity Key nào trong app/.antigravity_keys.env",
            }
            return

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        account_exhausted = True

        for current_model in trial_models:
            payload = {
                "model": current_model,
                "messages": messages,
                "stream": True,
            }

            yield {
                "type": "meta",
                "data": {
                    "model": current_model,
                    "account_index": acc_num,
                    "total_accounts": total_accs,
                },
            }

            assembled: list[str] = []
            switch_to_next_model = False
            model_error_reason = ""

            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as resp:
                        if resp.status_code in (404, 429, 500, 503, 529):
                            switch_to_next_model = True
                            err_body = await resp.aread()
                            model_error_reason = f"HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')[:80]}"
                        elif resp.status_code != 200:
                            switch_to_next_model = True
                            err_body = await resp.aread()
                            model_error_reason = f"HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')[:80]}"
                        else:
                            yield {"type": "status", "status": "responding"}
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    delta = chunk["choices"][0]["delta"].get("content", "")
                                    if delta:
                                        assembled.append(delta)
                                        yield {"type": "delta", "text": delta}
                                except Exception:
                                    pass

            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
                switch_to_next_model = True
                model_error_reason = f"Timeout/Connection: {e}"

            if switch_to_next_model:
                yield {
                    "type": "thinking",
                    "text": f"⚡ [Acc #{acc_num}] {current_model} tạm bận ({model_error_reason[:35]}) -> Chuyển sang model dự phòng tiếp theo...",
                }
                await asyncio.sleep(0.5)
                continue  # try next model in trial_models

            # Successfully streamed response
            account_exhausted = False
            final_text = "".join(assembled)
            yield {"type": "agent_done", "status": "ok", "text": final_text}
            return

        if account_exhausted:
            _ag_pool.mark_rate_limited(acc_num, cooldown_seconds=60.0)
            next_key, next_acc_num, _ = _ag_pool.get_key()
            yield {
                "type": "thinking",
                "text": f"🔄 Toàn bộ model trên Antigravity Acc #{acc_num} đã chạm hạn mức. Tự động chuyển sang Acc #{next_acc_num}/{total_accs}...",
            }
            await asyncio.sleep(1.0)
            continue  # try next account

    yield {
        "type": "error",
        "message": f"Tất cả {total_accs} tài khoản Antigravity Pro đều đang chạm hạn mức hoặc tạm nghỉ. Vui lòng đợi trong giây lát.",
    }

