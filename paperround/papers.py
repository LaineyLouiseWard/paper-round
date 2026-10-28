"""A fetched paper, and the ids that recognise it when it turns up again."""

import re
from dataclasses import dataclass

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>?#&]+)", re.I)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.I)


def normalise_title(title: str) -> str:
    """Lowercase, spaces collapsed, punctuation stripped: the form titles are compared in."""
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", title.lower())).strip()


def find_doi(*texts: str | None) -> str | None:
    """First DOI found in any of the texts (a feed field or a link), lowercased."""
    for text in texts:
        m = DOI_RE.search(text or "")
        if m:
            return m.group(1).rstrip(".,;)").lower()
    return None


def arxiv_id(link: str) -> str | None:
    m = ARXIV_RE.search(link or "")
    return m.group(1) if m else None


MIN_ABSTRACT_WORDS = 25


@dataclass
class Paper:
    title: str
    link: str
    source: str
    abstract: str = ""
    authors: str = ""
    doi: str | None = None

    def has_abstract(self) -> bool:
        """Feeds sometimes put the journal name or a citation where the abstract belongs."""
        return len(self.abstract.split()) >= MIN_ABSTRACT_WORDS

    def key(self) -> str:
        """One stable id: the DOI, else the arXiv id, else the title."""
        if self.doi:
            return f"doi:{self.doi}"
        if aid := arxiv_id(self.link):
            return f"arxiv:{aid}"
        return normalise_title(self.title)

    def keys(self) -> set[str]:
        """Every id this paper can be recognised by: title, DOI, arXiv id."""
        keys = {normalise_title(self.title)}
        if self.doi:
            keys.add(f"doi:{self.doi}")
        if aid := arxiv_id(self.link):
            keys.add(f"arxiv:{aid}")
        return keys


def drop_seen(papers: list[Paper], seen: set[str]) -> list[Paper]:
    """Papers whose ids are all new, keeping the first copy of any repeat within the batch."""
    new, taken = [], set()
    for p in papers:
        keys = p.keys()
        if keys & (seen | taken):
            continue
        taken |= keys
        new.append(p)
    return new
