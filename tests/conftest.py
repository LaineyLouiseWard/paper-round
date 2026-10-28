from pathlib import Path

import pytest

from paperround.config import load_scope, load_settings

SCOPE = """
threshold: 0.7
exclude_threshold: 0.7
strands:
  - id: floods
    label: Flood forecasting
    question: Does the paper forecast floods?
    exclude:
      - id: projection
        question: Is it only climate projections?
  - id: drought
    label: Drought monitoring
    question: Does the paper monitor drought?
    threshold: 0.6
"""

CONFIG = """
contact_email: me@example.edu
feeds:
  - name: Journal A
    url: https://example.org/rss
zotero:
  library_id: "123"
  collection: ABCDEFGH
email:
  to: me@example.edu
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "scope.yaml").write_text(SCOPE)
    (tmp_path / "config.yaml").write_text(CONFIG)
    return tmp_path


@pytest.fixture
def scope(root):
    return load_scope(root / "scope.yaml")


@pytest.fixture
def cfg(root):
    return load_settings(root / "config.yaml")
