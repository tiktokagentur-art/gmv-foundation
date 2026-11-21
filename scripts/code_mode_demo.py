"""Run the isolated read-only pilot entirely against synthetic fixtures."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from code_mode.bridge import READ_TOOLS
from code_mode.fixtures import PILOT_CODE, fixture_client
from code_mode.gateway import (
    ExecutionRequest,
    Gateway,
    JsonlAuditSink,
    Mandate,
    TrustedPrincipal,
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gmv-code-mode-") as temporary:
        audit_path = Path(temporary) / "audit.jsonl"
        gateway = Gateway(
            mandates=(Mandate("pilot-agent", "SYNTHETIC-001", "fixture-read", READ_TOOLS),),
            client=fixture_client(),
            audit_sink=JsonlAuditSink(audit_path),
        )
        output = gateway.execute(
            ExecutionRequest("SYNTHETIC-001", "fixture-read", PILOT_CODE, READ_TOOLS),
            TrustedPrincipal("pilot-agent", active=True),
        )
        print(
            json.dumps(
                {
                    "execution_id": output.execution_id,
                    "status": output.status,
                    "error_code": output.error_code,
                    "result": output.result,
                },
                ensure_ascii=False,
            )
        )
        print(
            json.dumps(
                {"audit": json.loads(audit_path.read_text(encoding="utf-8"))}, ensure_ascii=False
            )
        )


if __name__ == "__main__":
    main()
