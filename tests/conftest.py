from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Point to a temp DB before importing app so all test modules share one client
os.environ["TELEMETRY_DB"] = str(Path(tempfile.mkdtemp()) / "conftest_telemetry.db")

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
