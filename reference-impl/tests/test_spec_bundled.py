"""Guard against drift between the canonical spec file and the copy
bundled with the package.

`ail/reference_card.md` is shipped inside the wheel so `ail ask` can
load the full language reference at runtime on pip installs (where
the repo's `spec/` directory isn't available). The single source of
truth remains `spec/08-reference-card.ai.md`; the bundled copy is a
release artifact, not a second source.

If this test fails, the fix is to refresh the bundled copy:

    cp spec/08-reference-card.ai.md reference-impl/ail/reference_card.md

The RELEASING.md checklist includes this step before every build.
"""
from __future__ import annotations

from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SPEC = _REPO_ROOT / "spec" / "08-reference-card.ai.md"
_BUNDLED = _REPO_ROOT / "reference-impl" / "ail" / "reference_card.md"


@pytest.mark.skipif(not _SPEC.exists(), reason="canonical spec not present "
                    "(happens when tests are run from an sdist without the "
                    "full repo checked out)")
def test_bundled_reference_card_matches_canonical_spec():
    assert _BUNDLED.exists(), (
        f"{_BUNDLED.relative_to(_REPO_ROOT)} is missing. Refresh it with "
        f"`cp spec/08-reference-card.ai.md reference-impl/ail/reference_card.md`."
    )
    canonical = _SPEC.read_text(encoding="utf-8")
    bundled = _BUNDLED.read_text(encoding="utf-8")
    assert bundled == canonical, (
        "The bundled reference card has drifted from the canonical spec. "
        "Refresh with `cp spec/08-reference-card.ai.md "
        "reference-impl/ail/reference_card.md` and re-run tests."
    )
