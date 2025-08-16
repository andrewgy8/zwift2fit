"""
Configuration and fixtures for pytest.
"""

import pytest
from pathlib import Path


@pytest.fixture
def test_files_dir():
    """Get the path to test files directory"""
    return Path(__file__).parent
