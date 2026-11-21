"""Behavioral boundary tests for the local Code Mode process sandbox."""

from __future__ import annotations

import shutil
import threading
import time

import pytest

from code_mode.bridge import BridgeError
from code_mode.sandbox import ExecutionLimits, SandboxUnavailable, run_code


@pytest.fixture
def limits() -> ExecutionLimits:
    return ExecutionLimits(timeout_seconds=2, memory_bytes=128 * 1024 * 1024,
                           output_bytes=4096, cpu_seconds=2, max_tool_calls=2)


def test_runtime_fails_closed_without_bubblewrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(SandboxUnavailable):
        run_code("return 1;", lambda _name, _args: None)


def test_tool_rpc_and_null_result(limits: ExecutionLimits) -> None:
    calls = []

    def handler(name: str, args: dict) -> object:
        calls.append((name, args))
        return {"issues": [{"number": 1}]}

    result = run_code(
        "const data = await tools.github.listIssues({state:'open'}); return data.issues[0].number;",
        handler, limits,
    )
    assert result.error_code is None
    assert result.result == 1
    assert result.tool_calls == ("github.list_issues",)
    assert calls == [("github.list_issues", {"state": "open"})]
    assert result.peak_memory_bytes is not None
    assert run_code("return null;", handler, limits).error_code is None


def test_denied_tool_does_not_continue(limits: ExecutionLimits) -> None:
    def denied(_name: str, _args: dict) -> object:
        raise PermissionError("private credential text must not be returned")

    result = run_code("await tools.call('github.write_issue', {}); return 'unreachable';",
                      denied, limits)
    assert result.error_code == "tool_denied"
    assert result.result is None
    assert result.tool_calls == ("github.write_issue",)


def test_invalid_tool_response_is_classified(limits: ExecutionLimits) -> None:
    def malformed(_name: str, _args: dict) -> object:
        raise BridgeError("tool_response_invalid")

    result = run_code("await tools.github.listIssues({}); return 'unreachable';",
                      malformed, limits)
    assert result.error_code == "tool_response_invalid"
    assert result.result is None


def test_no_host_environment_filesystem_network_or_imports(limits: ExecutionLimits) -> None:
    code = """
      const escape = this.constructor.constructor('return process')();
      return {
        env: Object.keys(escape.env),
        directProcess: typeof process,
        require: typeof require,
        fetch: typeof fetch,
        cwd: escape.cwd(),
      };
    """
    result = run_code(code, lambda _name, _args: None, limits)
    assert result.error_code is None
    assert result.result == {
        "env": [], "directProcess": "undefined", "require": "undefined",
        "fetch": "undefined", "cwd": "/work",
    }
    assert run_code("return await import('node:fs');", lambda _n, _a: None,
                    limits).error_code == "code_error"


def test_os_boundary_survives_vm_escape(limits: ExecutionLimits) -> None:
    # Node's vm is not a security boundary. Deliberately escape it and verify
    # the outer permission model, mount namespace and net namespace instead.
    prelude = "const p=this.constructor.constructor('return process')();"
    host_file = run_code(
        prelude + "try{p.mainModule.require('node:fs').readFileSync("
        "'/workspace/gmv-foundation/README.md');return 'read';}catch(e){return e.code;}",
        lambda _n, _a: None, limits,
    )
    assert host_file.result == "ERR_ACCESS_DENIED"
    process = run_code(
        prelude + "try{p.mainModule.require('node:child_process').spawnSync("
        "'/node',['-e','process.exit(0)']);return 'spawned';}catch(e){return e.code;}",
        lambda _n, _a: None, limits,
    )
    assert process.result == "ERR_ACCESS_DENIED"
    # TEST-NET-3 is reserved for documentation; the isolated namespace has no
    # route, so this cannot reach any external host even if net is imported.
    network = run_code(
        prelude + "const net=p.mainModule.require('node:net');"
        "return await new Promise(resolve=>{const s=net.connect({host:'203.0.113.1',port:9});"
        "s.on('error',e=>resolve(e.code));s.setTimeout(500,()=>resolve('socket_timeout'));});",
        lambda _n, _a: None, limits,
    )
    assert network.result == "ENETUNREACH"


def test_timeout_memory_output_and_cancel(limits: ExecutionLimits) -> None:
    assert run_code("while(true){}", lambda _n, _a: None,
                    limits).error_code == "timeout"
    assert run_code("return 'x'.repeat(100000);", lambda _n, _a: None,
                    limits).error_code == "output_limit"
    small_memory = ExecutionLimits(timeout_seconds=2, memory_bytes=64 * 1024 * 1024,
                                   output_bytes=4096, cpu_seconds=2)
    memory = run_code("const a=new Uint8Array(256*1024*1024); a.fill(7); return a.length;",
                      lambda _n, _a: None, small_memory)
    assert memory.error_code == "memory_limit"
    cancel = threading.Event()
    timer = threading.Timer(0.1, cancel.set)
    timer.start()
    try:
        cancelled = run_code("await new Promise(()=>{});", lambda _n, _a: None,
                             limits, cancel)
    finally:
        timer.join()
    assert cancelled.error_code == "cancelled"
    assert cancelled.duration_ms < 1000


def test_tool_count_limit(limits: ExecutionLimits) -> None:
    code = """
      await tools.github.listIssues({});
      await tools.github.listIssues({});
      await tools.github.listIssues({});
      return true;
    """
    result = run_code(code, lambda _n, _a: {}, limits)
    assert result.error_code == "tool_limit"
    assert len(result.tool_calls) == 3


def test_parallel_runs_do_not_share_context(limits: ExecutionLimits) -> None:
    outcomes = []

    def worker(value: int) -> None:
        outcomes.append(run_code(f"return {value};", lambda _n, _a: None, limits).result)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(4)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == list(range(4))
    assert time.monotonic() - started < 2
