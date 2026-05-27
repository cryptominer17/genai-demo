"""
Smoke tests for the template app.

To run: pytest apps/template_app/tests/

DEVELOPER: add your own test cases below.
"""

import sys
import os

# Add repo root to path so shared imports work in tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


def test_shared_imports():
    """Verify shared modules can be imported without errors."""
    import shared.utils  # noqa: F401
    import shared.llm_client  # noqa: F401


def test_placeholder():
    """DEVELOPER: add your test cases here."""
    # Replace this with real tests for your app's logic.
    # Example: test that your data loading functions return expected columns.
    assert True
