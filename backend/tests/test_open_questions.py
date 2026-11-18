"""Open questions about the manual live in the graph and in docs/OPEN_QUESTIONS.md."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.graphs.loader import DEFAULT_GRAPHS_DIR, load_graphs

REPO_ROOT = Path(__file__).resolve().parents[2]
OPEN_QUESTIONS_DOC = REPO_ROOT / "docs" / "OPEN_QUESTIONS.md"
# Built from parts so this file does not contain the marker it searches for.
RETIRED_MARKER = "TODO" + "(roota)"


def test_every_shipped_open_question_is_listed_in_the_doc() -> None:
    doc = OPEN_QUESTIONS_DOC.read_text(encoding="utf-8")
    graphs = load_graphs(DEFAULT_GRAPHS_DIR)
    listed = 0
    for graph in graphs.values():
        for cause in graph.causes:
            for item in cause.open_questions:
                assert item.question in doc, f"{cause.id}: question missing from doc"
                assert f"Depends on: {item.depends_on}" in doc, (
                    f"{cause.id}: manual reference missing from doc"
                )
                listed += 1
    assert listed > 0
    assert doc.count("Depends on:") == listed, "doc lists a question the graphs do not"


def test_no_retired_todo_marker_anywhere_in_the_repo() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    paths = [p for p in result.stdout.decode("utf-8").split("\0") if p]
    assert paths, "git listed no files; cannot check for the marker"
    offenders = []
    for relative in paths:
        path = REPO_ROOT / relative
        if not path.is_file():
            continue  # deleted in the working tree but still in the index
        if RETIRED_MARKER.encode() in path.read_bytes():
            offenders.append(relative)
    assert offenders == []
