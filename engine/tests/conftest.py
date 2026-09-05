from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "golden" / "fixtures" / "2026-08-30"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURES
