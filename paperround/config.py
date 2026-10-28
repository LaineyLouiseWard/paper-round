"""Settings (config.yaml) and research strands (scope.yaml), read and checked once at start."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


@dataclass
class Feed:
    name: str
    url: str
    crossref_issn: str | None = None


@dataclass
class Settings:
    contact_email: str
    feeds: list[Feed]
    openalex: dict[str, str] = field(default_factory=dict)
    openalex_search: list[str] = field(default_factory=list)
    openalex_days: int = 14
    crossref_rows: int = 30
    arxiv_search_terms: list[str] = field(default_factory=list)
    arxiv_max_results: int = 50
    zotero_library_id: str | None = None
    zotero_library_type: str = "group"
    zotero_collection: str | None = None
    email_from: str = "Paper Round <onboarding@resend.dev>"
    email_to: str = ""
    greeting_name: str = "there"
    send_when_empty: bool = True
    model: str = "jev-latest"


@dataclass
class Exclusion:
    id: str
    question: str
    yes: str = ""
    no: str = ""


@dataclass
class Strand:
    id: str
    label: str
    question: str
    yes: str = ""
    no: str = ""
    threshold: float = 0.7
    exclude: list[Exclusion] = field(default_factory=list)


@dataclass
class Scope:
    strands: list[Strand]
    exclude_threshold: float = 0.7

    def strand(self, sid: str) -> Strand:
        return next(s for s in self.strands if s.id == sid)

    def label(self, sid: str) -> str:
        """The strand's label, or its id if the strand has since been removed from scope.yaml."""
        return next((s.label for s in self.strands if s.id == sid), sid)


def _yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"{path.name} not found in {path.parent}; run `paperround init` first")
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must be a mapping of settings")
    return data


def _probability(value, name: str) -> float:
    if not isinstance(value, (int, float)) or not 0 < value < 1:
        raise ConfigError(f"{name} must be a number between 0 and 1, got {value!r}")
    return float(value)


def load_settings(path: Path) -> Settings:
    d = _yaml(path)
    if not d.get("contact_email"):
        raise ConfigError("config.yaml needs contact_email (sent to Crossref and Unpaywall)")
    feeds = []
    for f in d.get("feeds") or []:
        if not f.get("name") or not f.get("url"):
            raise ConfigError(f"each feed needs a name and a url: {f!r}")
        feeds.append(Feed(f["name"], f["url"], str(f["crossref_issn"]) if f.get("crossref_issn") else None))
    zot = d.get("zotero") or {}
    mail = d.get("email") or {}
    return Settings(
        contact_email=d["contact_email"],
        feeds=feeds,
        openalex={k: str(v) for k, v in (d.get("openalex") or {}).items()},
        openalex_search=list(d.get("openalex_search") or []),
        openalex_days=int(d.get("openalex_days", 14)),
        crossref_rows=int(d.get("crossref_rows", 30)),
        arxiv_search_terms=list(d.get("arxiv_search_terms") or []),
        arxiv_max_results=int(d.get("arxiv_max_results", 50)),
        zotero_library_id=str(zot["library_id"]) if zot.get("library_id") else None,
        zotero_library_type=zot.get("library_type", "group"),
        zotero_collection=zot.get("collection"),
        email_from=mail.get("from", "Paper Round <onboarding@resend.dev>"),
        email_to=mail.get("to") or d["contact_email"],
        greeting_name=mail.get("greeting_name", "there"),
        send_when_empty=bool(mail.get("send_when_empty", True)),
        model=d.get("model", "jev-latest"),
    )


def load_scope(path: Path) -> Scope:
    d = _yaml(path)
    default = _probability(d.get("threshold", 0.7), "threshold")
    exclude_threshold = _probability(d.get("exclude_threshold", 0.7), "exclude_threshold")
    strands, ids = [], set()
    for s in d.get("strands") or []:
        for key in ("id", "label", "question"):
            if not s.get(key):
                raise ConfigError(f"each strand needs {key}: {s!r}")
        if s["id"] in ids:
            raise ConfigError(f"strand id {s['id']!r} is used twice")
        ids.add(s["id"])
        exclusions = []
        for e in s.get("exclude") or []:
            if not e.get("id") or not e.get("question"):
                raise ConfigError(f"each exclusion in {s['id']} needs an id and a question: {e!r}")
            exclusions.append(Exclusion(e["id"], e["question"], e.get("yes", ""), e.get("no", "")))
        if len({e.id for e in exclusions}) != len(exclusions):
            raise ConfigError(f"exclusion ids repeat in strand {s['id']}")
        strands.append(Strand(
            id=s["id"], label=s["label"], question=s["question"], yes=s.get("yes", ""), no=s.get("no", ""),
            threshold=_probability(s.get("threshold", default), f"{s['id']} threshold"), exclude=exclusions,
        ))
    if not strands:
        raise ConfigError("scope.yaml needs at least one strand")
    return Scope(strands, exclude_threshold)


def load_dotenv(path: Path) -> None:
    """KEY=VALUE lines from a local .env into the environment, never overriding what is set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())
