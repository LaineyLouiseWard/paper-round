"""paperround init | run | judge"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .config import ConfigError, load_dotenv, load_scope, load_settings
from .judge import Jev, paper_state, relevance_questions
from .papers import Paper
from .run import require, run

STARTER = Path(__file__).parent / "starter"
STARTER_FILES = {"config.yaml": "config.yaml", "scope.yaml": "scope.yaml", "gitignore": ".gitignore",
                 "AGENTS.md": "AGENTS.md", "CLAUDE.md": "CLAUDE.md",
                 "paper-round.yml": ".github/workflows/paper-round.yml"}


def cmd_init(root: Path) -> int:
    for src, dest in STARTER_FILES.items():
        target = root / dest
        if target.exists():
            print(f"kept your {dest}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(STARTER / src, target)
        print(f"wrote {dest}")
    return 0


def cmd_judge(root: Path, path: Path) -> int:
    """Relevance probabilities for papers in a JSON lines file (title, abstract, source, optional id)."""
    cfg, scope = load_settings(root / "config.yaml"), load_scope(root / "scope.yaml")
    jev = Jev(require(os.environ, "TYPESAFE_API_KEY"), cfg.model)
    questions = relevance_questions(scope)
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        paper = Paper(title=d["title"], link=d.get("link", ""), source=d.get("source", ""),
                      abstract=d.get("abstract", ""))
        probs, model = jev.ask(paper_state(paper), questions)
        print(json.dumps({"id": d.get("id", d["title"]), "model": model, "probs": probs}), flush=True)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="paperround", description="A daily email of new papers that match your research.")
    parser.add_argument("--dir", type=Path, default=Path("."), help="folder holding config.yaml and scope.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="write starter settings, tuning notes for AI assistants, and the daily GitHub workflow")
    r = sub.add_parser("run", help="fetch, judge, add to Zotero, email, save state")
    r.add_argument("--dry-run", action="store_true", help="fetch and list the new papers only (no keys needed)")
    r.add_argument("--no-zotero", action="store_true")
    r.add_argument("--no-email", action="store_true")
    j = sub.add_parser("judge", help="print relevance probabilities for papers in a JSON lines file")
    j.add_argument("file", type=Path)
    args = parser.parse_args(argv)

    root = args.dir.resolve()
    load_dotenv(root / ".env")
    try:
        if args.cmd == "init":
            return cmd_init(root)
        if args.cmd == "judge":
            return cmd_judge(root, args.file)
        cfg, scope = load_settings(root / "config.yaml"), load_scope(root / "scope.yaml")
        return run(root, cfg, scope, dry_run=args.dry_run, use_zotero=not args.no_zotero, use_email=not args.no_email)
    except ConfigError as e:
        print(f"Settings problem: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
