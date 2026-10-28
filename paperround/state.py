"""What the round remembers between days, as plain text files in the repo.

state/seen.txt           ids of every paper already judged (append only)
state/judgements.jsonl   every paper's probabilities, so thresholds can change without asking Jev again
state/waiting.tsv        papers held back until their abstract appears, with the day each was first seen
paper_log.csv            kept papers, with their Zotero and email status; written only by this code
"""

import csv
import json
from pathlib import Path

from .papers import Paper

LOG_FIELDS = ["date", "title", "authors", "source", "link", "doi", "strands", "probability", "evidence",
              "zotero", "emailed"]


class State:
    def __init__(self, root: Path):
        self.seen_path = root / "state" / "seen.txt"
        self.judgements_path = root / "state" / "judgements.jsonl"
        self.waiting_path = root / "state" / "waiting.tsv"
        self.log_path = root / "paper_log.csv"

    def seen(self) -> set[str]:
        if not self.seen_path.exists():
            return set()
        return {line.strip() for line in self.seen_path.read_text().splitlines() if line.strip()}

    def add_seen(self, papers: list[Paper]) -> None:
        self.seen_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.seen_path, "a") as f:
            for p in papers:
                f.writelines(k + "\n" for k in sorted(p.keys()))

    def add_judgements(self, records: list[dict]) -> None:
        self.judgements_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.judgements_path, "a") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)

    def waiting(self) -> dict[str, str]:
        """Paper id → the date it was first held back."""
        if not self.waiting_path.exists():
            return {}
        return dict(line.split("\t", 1) for line in self.waiting_path.read_text().splitlines() if "\t" in line)

    def write_waiting(self, waiting: dict[str, str]) -> None:
        self.waiting_path.parent.mkdir(parents=True, exist_ok=True)
        self.waiting_path.write_text("".join(f"{k}\t{d}\n" for k, d in sorted(waiting.items())))

    def read_log(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        with open(self.log_path, newline="") as f:
            return list(csv.DictReader(f))

    def write_log(self, rows: list[dict]) -> None:
        with open(self.log_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LOG_FIELDS, extrasaction="raise")
            w.writeheader()
            w.writerows({k: r.get(k, "") for k in LOG_FIELDS} for r in rows)
