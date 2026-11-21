"""Local, fail-closed OS sandbox for the Code Mode pilot.

Only a Node binary, its required shared libraries and runner.js are mounted
into a fresh bubblewrap mount/PID/network/user namespace. There is no host
filesystem, inherited environment or direct network path. The host handles
each JSON-line tool request separately and never sends credentials to Node.
"""

from __future__ import annotations

import json
import math
import os
import re
import resource
import selectors
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from code_mode.bridge import BridgeError


@dataclass(frozen=True)
class ExecutionLimits:
    timeout_seconds: float = 5.0
    memory_bytes: int = 128 * 1024 * 1024
    output_bytes: int = 64 * 1024
    cpu_seconds: int = 2
    max_tool_calls: int = 8


@dataclass(frozen=True)
class SandboxResult:
    result: object | None
    duration_ms: int
    peak_memory_bytes: int | None
    tool_calls: tuple[str, ...]
    error_code: str | None


class SandboxUnavailable(RuntimeError):
    """Required OS isolation is unavailable; never fall back to bare Node."""


_RUNNER = Path(__file__).with_name("runner.js")
_LIB_PATTERN = re.compile(r"(?:=>\s*)?(/[^\s()]+)")
_MAX_CODE_BYTES = 32 * 1024
_MAX_PROTOCOL_LINE = 1024 * 1024


def _sandbox_command(limits: ExecutionLimits) -> list[str]:
    bwrap = shutil.which("bwrap")
    node = shutil.which("node")
    if not bwrap or not node or not _RUNNER.is_file():
        raise SandboxUnavailable("bubblewrap, Node.js or runner missing")
    try:
        listed = subprocess.run(["ldd", node], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SandboxUnavailable("Node shared libraries could not be resolved") from exc
    libraries = set(_LIB_PATTERN.findall(listed.stdout))
    if not libraries or not all(Path(lib).is_file() for lib in libraries):
        raise SandboxUnavailable("Node shared libraries unavailable")
    # / is a fresh tmpfs. Only named files are visible; no host directory is bound.
    mounted = {Path("/lib"), Path("/lib64"), Path("/work")}
    for lib in libraries:
        mounted.update(Path(lib).parents)
    mounted.discard(Path("/"))
    args = [
        bwrap, "--unshare-all", "--uid", "65534", "--gid", "65534",
        "--cap-drop", "ALL", "--die-with-parent", "--as-pid-1", "--new-session",
        "--clearenv", "--unsetenv", "PWD", "--tmpfs", "/",
    ]
    for directory in sorted(mounted, key=lambda path: (len(path.parts), str(path))):
        args += ["--dir", str(directory)]
    args += ["--ro-bind", node, "/node", "--ro-bind", str(_RUNNER), "/work/runner.js"]
    for lib in sorted(libraries):
        args += ["--ro-bind", lib, lib]
    # /proc shows only the new PID namespace. /dev contains standard safe nodes.
    heap_mb = max(16, min(64, limits.memory_bytes // (2 * 1024 * 1024)))
    args += [
        "--proc", "/proc", "--dev", "/dev", "--chdir", "/work",
        "/node", "--permission", "--allow-fs-read=/work/runner.js",
        f"--max-old-space-size={heap_mb}",
        "--max-semi-space-size=4", "/work/runner.js",
    ]
    return args


def _set_limits(limits: ExecutionLimits) -> None:
    # V8 reserves far more virtual address space than its resident set. RSS is
    # monitored below; this ceiling still prevents unbounded address mapping.
    address_space = max(2 * 1024**3, limits.memory_bytes * 8)
    resource.setrlimit(resource.RLIMIT_AS, (address_space, address_space))
    cpu = max(1, math.ceil(limits.cpu_seconds))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    # Node and bubblewrap need several helper threads/processes at startup.
    resource.setrlimit(resource.RLIMIT_NPROC, (512, 512))


def _process_table() -> dict[int, tuple[int, int]]:
    """Map host PIDs to parent PID and RSS; /proc may race with process exit."""
    processes: dict[int, tuple[int, int]] = {}
    try:
        with os.scandir("/proc") as entries:
            for entry in entries:
                if not entry.name.isdecimal():
                    continue
                try:
                    status = Path(entry.path, "status").read_text()
                except OSError:
                    continue
                parent = re.search(r"^PPid:\s+(\d+)$", status, re.MULTILINE)
                rss = re.search(r"^VmRSS:\s+(\d+) kB$", status, re.MULTILINE)
                if parent:
                    processes[int(entry.name)] = (
                        int(parent.group(1)), int(rss.group(1)) * 1024 if rss else 0
                    )
    except OSError:
        return {}
    return processes


def _descendants(pid: int, processes: dict[int, tuple[int, int]]) -> set[int]:
    descendants = {pid}
    while True:
        size = len(descendants)
        descendants.update(
            child for child, (parent, _) in processes.items() if parent in descendants
        )
        if len(descendants) == size:
            return descendants


def _rss_bytes(pid: int) -> int | None:
    """Sum the bubblewrap process tree, including the namespaced Node child."""
    processes = _process_table()
    if pid not in processes:
        return None
    descendants = _descendants(pid, processes)
    return sum(processes[child][1] for child in descendants)


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        # Successful runs normally exit themselves. Let bubblewrap reap its
        # namespace helper, otherwise PID 1 would retain orphaned zombies.
        process.wait(timeout=0.2)
        return
    except subprocess.TimeoutExpired:
        pass
    processes = _process_table()
    descendants = _descendants(process.pid, processes)
    for child in sorted(descendants - {process.pid}, reverse=True):
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        # Last resort; --die-with-parent kills any remaining namespace child.
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=1)


def run_code(
    code: str,
    tool_handler: Callable[[str, dict], object],
    limits: ExecutionLimits = ExecutionLimits(),
    cancel_event: threading.Event | None = None,
) -> SandboxResult:
    """Execute JavaScript with server-mediated tool calls only.

    `tool_handler` must validate the requested tool and arguments; this layer
    enforces tool-count and process/resource limits. Errors have stable codes
    and never return raw child stderr or arbitrary exception messages.
    """
    if not isinstance(code, str) or len(code.encode("utf-8")) > _MAX_CODE_BYTES:
        raise ValueError("code exceeds pilot limit")
    if (limits.timeout_seconds <= 0 or limits.memory_bytes < 64 * 1024 * 1024
            or limits.output_bytes <= 0 or limits.cpu_seconds <= 0
            or limits.max_tool_calls < 0):
        raise ValueError("invalid execution limits")
    command = _sandbox_command(limits)
    started = time.monotonic()
    peak: int | None = None
    tool_calls: list[str] = []
    error_code: str | None = None
    result: object | None = None
    finished = False
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=True,
            preexec_fn=lambda: _set_limits(limits), env={},
        )
    except OSError as exc:
        raise SandboxUnavailable("bubblewrap could not start") from exc
    assert process.stdin and process.stdout and process.stderr
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    output_total = 0
    try:
        try:
            process.stdin.write(json.dumps({"code": code}, ensure_ascii=False).encode() + b"\n")
            process.stdin.flush()
        except BrokenPipeError:
            error_code = "sandbox_error"
        while error_code is None:
            if cancel_event is not None and cancel_event.is_set():
                error_code = "cancelled"
                break
            if time.monotonic() - started >= limits.timeout_seconds:
                error_code = "timeout"
                break
            rss = _rss_bytes(process.pid)
            if rss is not None:
                peak = max(peak or 0, rss)
                if rss > limits.memory_bytes:
                    error_code = "memory_limit"
                    break
            events = selector.select(timeout=0.01)
            for key, _ in events:
                stream = key.data
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                output_total += len(chunk)
                if (
                    output_total > limits.output_bytes
                    or len(buffers[stream]) + len(chunk) > _MAX_PROTOCOL_LINE
                ):
                    error_code = "output_limit"
                    break
                buffers[stream].extend(chunk)
                if stream == "stderr":
                    # Never send child stderr to the caller or audit log.
                    buffers[stream].clear()
                    continue
                while b"\n" in buffers["stdout"]:
                    line, _, rest = buffers["stdout"].partition(b"\n")
                    buffers["stdout"] = bytearray(rest)
                    try:
                        frame = json.loads(line)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        error_code = "protocol_error"
                        break
                    kind = frame.get("kind") if isinstance(frame, dict) else None
                    if kind == "call":
                        name, args, call_id = frame.get("name"), frame.get("args"), frame.get("id")
                        if (not isinstance(name, str) or not isinstance(args, dict)
                                or not isinstance(call_id, int)):
                            error_code = "protocol_error"
                            break
                        tool_calls.append(name)
                        if len(tool_calls) > limits.max_tool_calls:
                            error_code = "tool_limit"
                            break
                        try:
                            value = tool_handler(name, args)
                            reply = {"kind": "reply", "id": call_id, "ok": True, "value": value}
                        except BridgeError as exc:
                            error_code = exc.code if exc.code in {
                                "tool_denied", "invalid_tool_arguments",
                                "tool_response_limit", "tool_response_invalid",
                            } else "sandbox_error"
                            break
                        except PermissionError:
                            error_code = "tool_denied"
                            break
                        except Exception:
                            error_code = "sandbox_error"
                            break
                        try:
                            payload = json.dumps(
                                reply, ensure_ascii=False, allow_nan=False
                            ).encode()
                            if len(payload) > _MAX_PROTOCOL_LINE:
                                raise ValueError("tool response too large")
                            process.stdin.write(payload + b"\n")
                            process.stdin.flush()
                        except (ValueError, TypeError, BrokenPipeError):
                            error_code = "tool_error"
                            break
                    elif kind == "result":
                        result = frame.get("value")
                        finished = True
                        break
                    elif kind == "error":
                        error_code = "timeout" if frame.get("code") == "timeout" else "code_error"
                        break
                    else:
                        error_code = "protocol_error"
                        break
                if error_code is not None or finished:
                    break
            if error_code is not None or finished:
                break
            if process.poll() is not None and not selector.get_map():
                error_code = "runtime_error"
                break
    finally:
        selector.close()
        _stop(process)
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                stream.close()
            except BrokenPipeError:
                pass
    duration_ms = int((time.monotonic() - started) * 1000)
    return SandboxResult(result, duration_ms, peak, tuple(tool_calls), error_code)
