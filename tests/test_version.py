"""Tests that the declared version stays consistent across the project.

const.VERSION is the single source of truth: it is also what builds the
cache-busting query string on the frontend card's script URL, so a stale
copy elsewhere means an update that browsers never re-fetch.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.flight_tracker.const import (
    FRONTEND_CARD_FILENAME,
    FRONTEND_STATIC_PATH,
    VERSION,
)

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / "flight_tracker"


def test_version_is_semver() -> None:
    """The version must be a plain semver string usable in a URL query."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION


def test_manifest_version_matches_const() -> None:
    """manifest.json is what Home Assistant reports for the integration."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["version"] == VERSION


def test_hacs_version_matches_const() -> None:
    """hacs.json drives what HACS offers as an update."""
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["version"] == VERSION


def test_pyproject_version_matches_const() -> None:
    """pyproject.toml is what the built wheel/sdist carries."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == VERSION


def test_uv_lock_matches_project_version() -> None:
    """uv.lock records the project's own version; a bump must regenerate it.

    Without this the lockfile drifts silently - it sat at 1.1.3 while
    pyproject.toml reached 1.1.7 - and `uv sync` rewrites it mid-session.
    Run `uv lock` after bumping the version.
    """
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    entry = next(p for p in lock["package"] if p["name"] == "flight-tracker")
    assert entry["version"] == VERSION


def test_uv_lock_python_floor_matches_pyproject() -> None:
    """The lockfile must be resolved against the declared Python floor.

    The floor is >=3.12 because the integration uses StaticPathConfig /
    async_register_static_paths, which need Home Assistant >=2024.7, which
    needs Python 3.12. A lockfile resolved for an older floor carries
    dependency branches that can never be installed.
    """
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert lock["requires-python"] == pyproject["project"]["requires-python"]


def test_changelog_documents_current_version() -> None:
    """Every released version needs its own CHANGELOG entry."""
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert f"## [{VERSION}]" in changelog


def test_bundled_card_file_exists() -> None:
    """The card registered with add_extra_js_url must actually be shipped.

    __init__.py serves the integration's www/ directory at
    FRONTEND_STATIC_PATH, so that is where the card file has to be.
    """
    card = INTEGRATION / "www" / FRONTEND_CARD_FILENAME
    assert card.is_file(), card
    assert FRONTEND_STATIC_PATH.startswith("/"), FRONTEND_STATIC_PATH
