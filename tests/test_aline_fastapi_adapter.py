"""Run the isolated Aline API checks in the repository's standard CI pytest suite.

The root pytest configuration only scans tests/, so the prototype's own test
folder is not otherwise exercised during the required Backend job.
"""
import importlib.util
from pathlib import Path

PROTOTYPE_TEST = (
    Path(__file__).resolve().parents[1]
    / "prototypes"
    / "aline-openai-worker"
    / "tests"
    / "test_api.py"
)
SPEC = importlib.util.spec_from_file_location("aline_fastapi_prototype_test", PROTOTYPE_TEST)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

# unittest.TestCase subclass, discovered by pytest in this root test module.
TestAlineFastAPIAdapter = MODULE.AlineApiTests
