"""Fetch recent papers: journal RSS, Crossref for feeds behind bot protection, OpenAlex, arXiv search."""

import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from html import unescape

import feedparser
import requests

from .config import Settings
from .papers import Paper, find_doi

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
SKIP_TITLES = {"untitled", "full text pdf", "pdf", "snapshot", "journal information and table of contents"}


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def author_string(names: list[str]) -> str:
    names = [n for n in names if n]
    return ", ".join(names[:4]) + (" et al." if len(names) > 4 else "")


def _polite(cfg: Settings) -> dict:
    return {"User-Agent": f"PaperRound/2 ({cfg.contact_email})"}


def fetch_rss(name: str, url: str) -> list[Paper]:
    feed = feedparser.parse(url, agent=USER_AGENT)
    papers = []
    for e in feed.entries:
        title = strip_html(e.get("title") or "")
        if not title or title.lower() in SKIP_TITLES:
            continue
        abstract = strip_html(e.get("summary") or e.get("description") or "")
        if not abstract and e.get("content"):
            abstract = strip_html(e.content[0].get("value", ""))
        link = e.get("link", "")
        papers.append(Paper(
            title=title, link=link, source=name, abstract=abstract,
            authors=(e.get("author") or "").strip(),
            doi=find_doi(e.get("prism_doi"), e.get("dc_identifier"), link, e.get("id")),
        ))
    return papers


def fetch_crossref(cfg: Settings, name: str, issn: str) -> list[Paper]:
    since = (date.today() - timedelta(days=14)).isoformat()
    resp = requests.get(
        f"https://api.crossref.org/journals/{issn}/works",
        params={"rows": cfg.crossref_rows, "sort": "published", "order": "desc",
                "filter": f"type:journal-article,from-pub-date:{since}"},
        headers=_polite(cfg), timeout=30,
    )
    resp.raise_for_status()
    papers = []
    for item in resp.json()["message"]["items"]:
        title = strip_html((item.get("title") or [""])[0])
        if len(title) < 10:  # covers, errata, tables of contents
            continue
        papers.append(Paper(
            title=title, link=item.get("URL", ""), source=name, abstract=strip_html(item.get("abstract", "")),
            authors=author_string([f"{a.get('given', '')} {a.get('family', '')}".strip()
                                   for a in item.get("author", [])]),
            doi=(item.get("DOI") or "").lower() or None,
        ))
    return papers


def _openalex(cfg: Settings, api_key: str | None, source: str | None, filters: str) -> list[Paper]:
    """Recent articles from OpenAlex matching the filters; source=None labels each paper with its own journal."""
    since = (date.today() - timedelta(days=cfg.openalex_days)).isoformat()
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = requests.get(
        "https://api.openalex.org/works",
        params={"filter": f"{filters},from_publication_date:{since},type:article", "per-page": 100,
                "mailto": cfg.contact_email},
        headers=headers, timeout=30,
    )
    resp.raise_for_status()
    papers = []
    for item in resp.json().get("results", []):
        title = strip_html(item.get("title") or "")
        if not title:
            continue
        words = {}
        for word, positions in (item.get("abstract_inverted_index") or {}).items():
            for i in positions:
                words[i] = word
        journal = ((item.get("primary_location") or {}).get("source") or {}).get("display_name") or "OpenAlex"
        papers.append(Paper(
            title=title, link=item.get("doi") or item.get("id", ""), source=source or journal,
            abstract=" ".join(words[i] for i in sorted(words)),
            authors=author_string([a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])]),
            doi=find_doi(item.get("doi")),
        ))
    return papers


def fetch_openalex(cfg: Settings, name: str, issn: str, api_key: str | None) -> list[Paper]:
    return _openalex(cfg, api_key, name, f"primary_location.source.issn:{issn}")


def fetch_openalex_search(cfg: Settings, api_key: str | None) -> list[Paper]:
    """Articles in any journal whose title or abstract contains one of the search phrases."""
    query = " OR ".join(f'"{t}"' for t in cfg.openalex_search)
    return _openalex(cfg, api_key, None, f"title_and_abstract.search:{query},primary_location.source.type:journal")


def fetch_arxiv(cfg: Settings) -> list[Paper]:
    query = " OR ".join(f'all:"{t}"' for t in cfg.arxiv_search_terms)
    resp = requests.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": query, "sortBy": "submittedDate", "sortOrder": "descending",
                "max_results": cfg.arxiv_max_results},
        headers=_polite(cfg), timeout=30,
    )
    resp.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    papers = []
    for entry in ET.fromstring(resp.text).findall("a:entry", ns):
        title = entry.findtext("a:title", "", ns)
        if not title.strip():
            continue
        authors = [n.findtext("a:name", "", ns) for n in entry.findall("a:author", ns)]
        papers.append(Paper(
            title=re.sub(r"\s+", " ", title).strip(), link=entry.findtext("a:id", "", ns).strip(),
            source="arXiv search", abstract=re.sub(r"\s+", " ", entry.findtext("a:summary", "", ns)).strip(),
            authors=author_string(authors),
        ))
    return papers


def fill_elsevier_abstracts(papers: list[Paper], api_key: str) -> int:
    """Elsevier withholds abstracts from OpenAlex and Crossref; its own API gives them. Returns how many were filled."""
    filled = 0
    for p in papers:
        if p.abstract or not (p.doi or "").startswith("10.1016/"):
            continue
        try:
            resp = requests.get(f"https://api.elsevier.com/content/article/doi/{p.doi}", params={"view": "META_ABS"},
                                headers={"X-ELS-APIKey": api_key, "Accept": "application/json"}, timeout=20)
            core = resp.json().get("full-text-retrieval-response", {}).get("coredata", {}) if resp.ok else {}
        except Exception:  # a missing abstract only means judging on the title
            continue
        if text := strip_html(core.get("dc:description") or ""):
            p.abstract = text
            filled += 1
    return filled


def fetch_all(cfg: Settings, openalex_key: str | None = None) -> tuple[list[Paper], list[str]]:
    """Every source in turn. Returns the papers and one line per source that failed."""
    papers, failures = [], []

    def take(label: str, fn):
        try:
            got = fn()
            print(f"  {label}: {len(got)}")
            papers.extend(got)
        except Exception as e:  # one broken source must not stop the round
            print(f"  {label}: FAILED ({e})")
            failures.append(f"{label}: {e}")

    for f in cfg.feeds:
        def rss_then_crossref(f=f):
            got = fetch_rss(f.name, f.url)
            return got or (fetch_crossref(cfg, f.name, f.crossref_issn) if f.crossref_issn else [])
        take(f.name, rss_then_crossref)
    for name, issn in cfg.openalex.items():
        take(f"{name} (OpenAlex)", lambda name=name, issn=issn: fetch_openalex(cfg, name, issn, openalex_key))
    if cfg.openalex_search:
        take("OpenAlex search", lambda: fetch_openalex_search(cfg, openalex_key))
    if cfg.arxiv_search_terms:
        take("arXiv search", lambda: fetch_arxiv(cfg))
    return papers, failures
