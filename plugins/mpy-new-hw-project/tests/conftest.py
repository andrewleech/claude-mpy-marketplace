import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "skills" / "mpy-new-hw-project" / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def scripts_dir() -> Path:
    return SCRIPTS
