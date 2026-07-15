#!/usr/bin/env python3
"""
Literature monitor — daily screening workflow.

Fetches RSS feeds, deduplicates against previously seen papers,
screens new papers with Claude, logs relevant ones, and
optionally adds them to Zotero.

Usage:
    python screen.py              # normal run
    python screen.py --dry-run    # fetch and dedup only, no API call
    python screen.py --no-zotero  # skip Zotero upload

Requires: feedparser, requests (anthropic only for local screening runs)
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import xml.etree.ElementTree as ET

import feedparser
import requests
import yaml

# ---------------------------------------------------------------------------
# Paths — everything relative to this script's directory
# ---------------------------------------------------------------------------
DIR = Path(__file__).resolve().parent
SOURCE_LIST = DIR / "source_list.md"
RESEARCH_SCOPE = DIR / "research_scope.md"
RELEVANCE_RULES = DIR / "relevance_rules.md"
PAPER_LOG = DIR / "paper_log.csv"
SEEN_PAPERS = DIR / "seen_papers.txt"


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from .env into the environment (no override)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(DIR / ".env")

# ---------------------------------------------------------------------------
# Config — user settings live in config.yaml, keys in .env
# ---------------------------------------------------------------------------
_cfg = yaml.safe_load((DIR / "config.yaml").read_text())
CONTACT_EMAIL = _cfg["contact_email"]
ZOTERO_LIBRARY_ID = str(_cfg["zotero"]["library_id"])
ZOTERO_LIBRARY_TYPE = _cfg["zotero"]["library_type"]
ZOTERO_INBOX_KEY = _cfg["zotero"]["inbox_collection"]
ARXIV_SEARCH_TERMS = _cfg.get("arxiv_search_terms") or []
CROSSREF_FALLBACKS = {k: str(v) for k, v in (_cfg.get("crossref_fallbacks") or {}).items()}
OPENALEX_SOURCES = {k: str(v) for k, v in (_cfg.get("openalex_sources") or {}).items()}
OPENALEX_DAYS = _cfg.get("openalex_days", 14)
MODEL = _cfg.get("model", "claude-haiku-4-5-20251001")

MAX_BATCH = 50  # max papers per API call
CROSSREF_ROWS = 30  # max papers to fetch per Crossref query
ARXIV_MAX_RESULTS = 50  # max papers from arXiv keyword search

CSV_FIELDS = [
    "date", "title", "source", "link",
    "relevance_score", "relevance_summary", "topic_labels",
]

# Browser-like User-Agent for RSS fetching
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
)


# ---------------------------------------------------------------------------
# 1. Parse feed URLs from source_list.md
# ---------------------------------------------------------------------------
def load_feeds(path: Path) -> list[dict]:
    """Extract feed name and URL from source_list.md.

    Looks for lines matching:
        ### N. Name
        - **Feed:** `url`
    """
    text = path.read_text()
    feeds = []
    name = None
    for line in text.splitlines():
        m = re.match(r"^###\s+\d+\.\s+(.+)$", line)
        if m:
            name = m.group(1).strip()
            continue
        m = re.match(r"^-\s+\*\*Feed:\*\*\s+`(.+)`", line)
        if m and name:
            feeds.append({"name": name, "url": m.group(1).strip()})
            name = None
    return feeds


# ---------------------------------------------------------------------------
# 2. Fetch papers — RSS with Crossref fallback
# ---------------------------------------------------------------------------
def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def fetch_rss(name: str, url: str) -> list[dict]:
    """Parse a single RSS feed and return paper entries."""
    feed = feedparser.parse(url, agent=USER_AGENT)
    papers = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        # Skip non-article entries
        skip = {"untitled", "full text pdf", "pdf", "snapshot",
                "journal information and table of contents"}
        if title.lower() in skip:
            continue

        # Try to get an abstract from available fields
        abstract = ""
        for field in ("summary", "description"):
            raw = entry.get(field, "")
            if raw:
                abstract = strip_html(raw)
                break
        if not abstract and entry.get("content"):
            abstract = strip_html(entry.content[0].get("value", ""))

        link = entry.get("link", "")
        papers.append({
            "title": title,
            "abstract": abstract,
            "link": link,
            "source": name,
        })
    return papers


def fetch_crossref(name: str, issn: str) -> list[dict]:
    """Fetch recent articles from a journal via the Crossref API.

    Used as a fallback when RSS feeds are blocked by bot protection.
    Free, no auth required, returns titles + abstracts.
    """
    since = (date.today() - timedelta(days=14)).isoformat()
    url = (
        f"https://api.crossref.org/journals/{issn}/works"
        f"?rows={CROSSREF_ROWS}"
        f"&sort=published&order=desc"
        f"&filter=type:journal-article,from-pub-date:{since}"
    )
    headers = {
        "User-Agent": f"LiteratureMonitor/1.0 ({CONTACT_EMAIL})",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    papers = []
    for item in data["message"]["items"]:
        title = (item.get("title") or [""])[0].strip()
        if not title:
            continue
        # Skip non-article items (covers, errata, etc.)
        if len(title) < 10:
            continue

        abstract = strip_html(item.get("abstract", ""))
        link = item.get("URL", "")
        papers.append({
            "title": title,
            "abstract": abstract,
            "link": link,
            "source": name,
        })
    return papers


def fetch_arxiv_keyword_search() -> list[dict]:
    """Search arXiv across all categories for the configured keywords.

    Uses the arXiv API (free, no auth) with a broad OR query so relevant
    papers are caught regardless of which category they land in.
    """
    query_parts = [f'all:"{t}"' for t in ARXIV_SEARCH_TERMS]
    query = " OR ".join(query_parts)

    url = (
        "https://export.arxiv.org/api/query"
        f"?search_query={requests.utils.quote(query)}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={ARXIV_MAX_RESULTS}"
    )

    headers = {"User-Agent": f"LiteratureMonitor/1.0 ({CONTACT_EMAIL})"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    # Parse Atom XML response
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)

    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns)
        summary = entry.find("atom:summary", ns)
        link = entry.find("atom:id", ns)

        if title is None:
            continue

        title_text = re.sub(r"\s+", " ", title.text or "").strip()
        abstract_text = re.sub(r"\s+", " ", (summary.text if summary is not None else "") or "").strip()
        link_text = (link.text if link is not None else "").strip()

        category = entry.find("{http://arxiv.org/schemas/atom}primary_category")
        cat_label = category.attrib.get("term", "") if category is not None else ""

        papers.append({
            "title": title_text,
            "abstract": abstract_text,
            "link": link_text,
            "source": f"arXiv keyword search ({cat_label})",
        })

    return papers


def fetch_openalex(name: str, issn: str) -> list[dict]:
    """Fetch recent works for a journal ISSN via the OpenAlex API.

    Covers journals whose RSS feeds are broken or blocked entirely.
    Anonymous access is heavily rate-limited; set OPENALEX_API_KEY in .env
    (free key from openalex.org) for reliable daily use.
    """
    since = (date.today() - timedelta(days=OPENALEX_DAYS)).isoformat()
    url = (
        "https://api.openalex.org/works"
        f"?filter=primary_location.source.issn:{issn},from_publication_date:{since}"
        f"&per-page=50&mailto={CONTACT_EMAIL}"
    )
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    papers = []
    for item in resp.json().get("results", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        # OpenAlex stores abstracts as an inverted index; rebuild the text
        abstract = ""
        inv = item.get("abstract_inverted_index")
        if inv:
            pos = {}
            for word, idxs in inv.items():
                for i in idxs:
                    pos[i] = word
            abstract = " ".join(pos[i] for i in sorted(pos))
        link = item.get("doi") or item.get("id", "")
        papers.append({
            "title": title,
            "abstract": abstract,
            "link": link,
            "source": name,
        })
    return papers


def fetch_all(feeds: list[dict]) -> list[dict]:
    """Fetch papers from all feeds. Falls back to Crossref for blocked feeds."""
    all_papers = []
    for f in feeds:
        name = f["name"]
        try:
            papers = fetch_rss(name, f["url"])

            # If RSS returned nothing, try Crossref fallback
            if not papers:
                issn = None
                for key, val in CROSSREF_FALLBACKS.items():
                    if key in name:
                        issn = val
                        break
                if issn:
                    papers = fetch_crossref(name, issn)
                    print(f"  {name}: {len(papers)} entries (via Crossref)")
                else:
                    print(f"  {name}: 0 entries")
            else:
                print(f"  {name}: {len(papers)} entries")

            all_papers.extend(papers)
        except Exception as e:
            print(f"  {name}: FAILED ({e})")

    # OpenAlex sources — journals with no workable RSS
    for name, issn in OPENALEX_SOURCES.items():
        try:
            papers = fetch_openalex(name, issn)
            print(f"  {name}: {len(papers)} entries (via OpenAlex)")
            all_papers.extend(papers)
        except Exception as e:
            print(f"  {name}: FAILED ({e})")

    # arXiv keyword search — catches papers across all categories
    if ARXIV_SEARCH_TERMS:
        try:
            arxiv_papers = fetch_arxiv_keyword_search()
            print(f"  arXiv keyword search: {len(arxiv_papers)} entries")
            all_papers.extend(arxiv_papers)
        except Exception as e:
            print(f"  arXiv keyword search: FAILED ({e})")

    return all_papers


# ---------------------------------------------------------------------------
# 3. Deduplicate
# ---------------------------------------------------------------------------
def normalise_title(title: str) -> str:
    """Lowercase and strip punctuation for dedup comparison."""
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def extract_paper_id(link: str) -> str | None:
    """Return a stable id line ('doi:...' or 'arxiv:...') for a paper link.

    Title-only dedup double-alerts when a preprint is later published with a
    slightly different title; the DOI or arXiv id catches that.
    """
    m = re.match(r"https?://(?:dx\.)?doi\.org/(10\.\S+)", link or "")
    if m:
        return f"doi:{m.group(1).lower()}"
    m = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", link or "")
    if m:
        return f"arxiv:{m.group(1)}"
    return None


def load_seen(path: Path) -> set[str]:
    """Load set of normalised titles already seen."""
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def mark_seen(papers: list[dict], path: Path = None) -> int:
    """Append each paper's normalised title (and id line, when the link has
    a DOI or arXiv id) to the seen file. Returns the number of lines added."""
    path = path or SEEN_PAPERS
    lines = []
    for p in papers:
        lines.append(normalise_title(p["title"]))
        pid = extract_paper_id(p.get("link", ""))
        if pid:
            lines.append(pid)
    with open(path, "a") as f:
        for line in lines:
            f.write(line + "\n")
    return len(lines)


def deduplicate(papers: list[dict], seen: set[str]) -> list[dict]:
    """Remove papers already seen, by normalised title or DOI/arXiv id.

    Also deduplicates within the current batch (same paper from multiple feeds).
    """
    new = []
    seen_this_run = set()
    for p in papers:
        keys = {normalise_title(p["title"])}
        pid = extract_paper_id(p.get("link", ""))
        if pid:
            keys.add(pid)
        if keys & (seen | seen_this_run):
            continue
        seen_this_run |= keys
        new.append(p)
    return new


# ---------------------------------------------------------------------------
# 4. Build prompt and call Claude
# ---------------------------------------------------------------------------
def build_system_prompt() -> str:
    """Concatenate research_scope.md and relevance_rules.md."""
    scope = RESEARCH_SCOPE.read_text()
    rules = RELEVANCE_RULES.read_text()
    return scope + "\n\n---\n\n" + rules


def build_user_prompt(papers: list[dict]) -> str:
    """Format papers as a numbered list for screening."""
    lines = [
        "Score each paper below using the relevance rules in your system prompt.",
        "Return ONLY a JSON array. For each paper:",
        '  - score >= 3: {"id": <n>, "score": <0-4>, "summary": "<1-2 sentences>", "labels": "<comma-separated>"}',
        '  - score < 3:  {"id": <n>, "score": <0-4>}',
        "Do not include any text outside the JSON array.",
        "",
    ]
    for i, p in enumerate(papers, 1):
        lines.append(f"[{i}]")
        lines.append(f"Title: {p['title']}")
        lines.append(f"Source: {p['source']}")
        if p["abstract"]:
            # Truncate very long abstracts to ~500 words
            words = p["abstract"].split()
            abstract = " ".join(words[:500])
            lines.append(f"Abstract: {abstract}")
        else:
            lines.append("Abstract: (not available — score on title only)")
        lines.append("")
    return "\n".join(lines)


def screen_papers(papers: list[dict]) -> list[dict]:
    """Send papers to Claude for relevance scoring. Returns parsed results."""
    import anthropic

    client = anthropic.Anthropic()
    system_prompt = build_system_prompt()
    results = []

    for batch_start in range(0, len(papers), MAX_BATCH):
        batch = papers[batch_start : batch_start + MAX_BATCH]
        user_prompt = build_user_prompt(batch)

        print(f"  Screening papers {batch_start + 1}-{batch_start + len(batch)}...")
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()

        # Parse JSON — handle possible markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        try:
            scored = json.loads(text)
        except json.JSONDecodeError:
            print(f"  WARNING: failed to parse Claude response as JSON.")
            print(f"  Raw response:\n{text[:500]}")
            continue

        for item in scored:
            idx = item["id"] - 1 + batch_start
            if 0 <= idx < len(papers):
                papers[idx]["score"] = item.get("score", 0)
                papers[idx]["summary"] = item.get("summary", "")
                papers[idx]["labels"] = item.get("labels", "")
                results.append(papers[idx])

    return results


# ---------------------------------------------------------------------------
# 5. Save results
# ---------------------------------------------------------------------------
def save_results(papers: list[dict], today: str) -> int:
    """Append papers with score >= 3 to paper_log.csv. Returns count saved."""
    relevant = [p for p in papers if p.get("score", 0) >= 3]
    if not relevant:
        return 0

    write_header = not PAPER_LOG.exists()
    with open(PAPER_LOG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        for p in relevant:
            writer.writerow({
                "date": today,
                "title": p["title"],
                "source": p["source"],
                "link": p["link"],
                "relevance_score": p["score"],
                "relevance_summary": p["summary"],
                "topic_labels": p["labels"],
            })
    return len(relevant)


# ---------------------------------------------------------------------------
# 6. Add relevant papers to Zotero
# ---------------------------------------------------------------------------
def zotero_api_base() -> str:
    kind = "groups" if ZOTERO_LIBRARY_TYPE == "group" else "users"
    return f"https://api.zotero.org/{kind}/{ZOTERO_LIBRARY_ID}"


def get_crossref_metadata(doi: str) -> dict:
    """Fetch full bibliographic metadata from Crossref for a given DOI."""
    url = f"https://api.crossref.org/works/{requests.utils.quote(doi, safe='')}"
    headers = {"User-Agent": f"LiteratureMonitor/1.0 ({CONTACT_EMAIL})"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()["message"]

        creators = [
            {"creatorType": "author", "firstName": a.get("given", ""), "lastName": a.get("family", "")}
            for a in data.get("author", [])
        ]

        date_parts = (
            data.get("published", data.get("created", {}))
            .get("date-parts", [[None]])
        )
        year = str(date_parts[0][0]) if date_parts and date_parts[0][0] else ""

        return {
            "title": (data.get("title") or [""])[0],
            "creators": creators,
            "publicationTitle": (data.get("container-title") or [""])[0],
            "volume": data.get("volume", ""),
            "issue": data.get("issue", ""),
            "pages": data.get("page", ""),
            "date": year,
            "DOI": doi,
            "ISSN": (data.get("ISSN") or [""])[0],
            "abstractNote": strip_html(data.get("abstract", "")),
        }
    except Exception:
        return {}


def get_unpaywall_pdf_url(doi: str) -> str | None:
    """Return the best OA PDF URL from Unpaywall, or None if not available."""
    url = f"https://api.unpaywall.org/v2/{requests.utils.quote(doi, safe='')}?email={CONTACT_EMAIL}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        best = resp.json().get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url_for_landing_page")
    except Exception:
        return None


def extract_doi(link: str) -> str | None:
    """Extract a bare DOI from a URL like https://doi.org/10.1175/..."""
    m = re.match(r"https?://(?:dx\.)?doi\.org/(10\..+)", link)
    return m.group(1) if m else None


def add_to_zotero(papers: list[dict]) -> int:
    """Add scored papers to the Zotero inbox collection via the Web API.

    Uses plain HTTP requests (no pyzotero — it does not build in some
    sandboxed environments). For papers with a DOI: fetches full metadata
    from Crossref, then checks Unpaywall for an OA PDF and attaches it as a
    linked URL. Returns count of papers successfully added.
    """
    api_key = os.environ.get("ZOTERO_API_KEY")
    if not api_key:
        print("WARNING: ZOTERO_API_KEY not set — skipping Zotero upload.")
        return 0

    headers = {"Zotero-API-Key": api_key, "Content-Type": "application/json"}
    added = 0

    def already_in_library(doi: str) -> bool:
        r = requests.get(
            f"{zotero_api_base()}/items",
            headers=headers,
            params={"q": doi, "qmode": "everything", "limit": 1},
            timeout=15,
        )
        return r.ok and bool(r.json())

    for p in papers:
        if p.get("score", 0) < 3:
            continue

        tags = [{"tag": t.strip()} for t in p.get("labels", "").split(",") if t.strip()]
        title = p["title"]
        link = p.get("link", "")
        doi = extract_doi(link)

        if doi and already_in_library(doi):
            print(f"  = already in Zotero, skipping: {title[:60]}...")
            continue

        try:
            item = {
                "itemType": "journalArticle",
                "title": title,
                "url": link,
                "collections": [ZOTERO_INBOX_KEY],
                "tags": tags,
            }
            if doi:
                meta = get_crossref_metadata(doi)
                item.update({k: v for k, v in meta.items() if v})
                item["DOI"] = doi
            if p.get("summary"):
                item["extra"] = f"Monitor note: {p['summary']}"

            resp = requests.post(
                f"{zotero_api_base()}/items",
                headers=headers, data=json.dumps([item]), timeout=30,
            )
            keys = resp.ok and resp.json().get("success", {})
            item_key = list(keys.values())[0] if keys else None
            if not item_key:
                print(f"  ! Zotero failed for '{title[:50]}...': "
                      f"HTTP {resp.status_code} {resp.text[:200]}")
                continue

            # Attach OA PDF as a linked URL if available
            if doi:
                pdf_url = get_unpaywall_pdf_url(doi)
                if pdf_url:
                    attachment = {
                        "itemType": "attachment",
                        "linkMode": "linked_url",
                        "title": "Open Access PDF",
                        "url": pdf_url,
                        "contentType": "application/pdf",
                        "parentItem": item_key,
                    }
                    requests.post(
                        f"{zotero_api_base()}/items",
                        headers=headers, data=json.dumps([attachment]), timeout=30,
                    )
                    print(f"    PDF attached: {pdf_url[:70]}...")

            added += 1
            print(f"  + Zotero: {title[:70]}...")
        except Exception as e:
            print(f"  ! Zotero failed for '{title[:50]}...': {e}")

    return added


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Literature monitor screening")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and dedup only — skip the Claude API call",
    )
    parser.add_argument(
        "--no-zotero", action="store_true",
        help="Skip adding papers to Zotero",
    )
    args = parser.parse_args()
    today = date.today().isoformat()

    print(f"=== Literature screening: {today} ===\n")

    feeds = load_feeds(SOURCE_LIST)
    print(f"Loaded {len(feeds)} feeds from source_list.md\n")

    print("Fetching papers...")
    papers = fetch_all(feeds)
    print(f"\nTotal entries fetched: {len(papers)}")

    seen = load_seen(SEEN_PAPERS)
    new_papers = deduplicate(papers, seen)
    print(f"New papers after dedup: {len(new_papers)} "
          f"(seen before: {len(papers) - len(new_papers)})\n")

    if not new_papers:
        print("Nothing new to screen. Done.")
        return

    if args.dry_run:
        print("--dry-run: skipping Claude API call.")
        print(f"\nPapers that would be screened:")
        for i, p in enumerate(new_papers, 1):
            has_abstract = "yes" if p["abstract"] else "no"
            print(f"  {i}. [{p['source']}] {p['title']} "
                  f"(abstract: {has_abstract})")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. "
              "Export it before running:\n"
              "  export ANTHROPIC_API_KEY='sk-ant-...'\n")
        sys.exit(1)

    print("Screening with Claude...")
    results = screen_papers(new_papers)

    score_counts = {s: 0 for s in range(5)}
    for r in results:
        score_counts[r.get("score", 0)] += 1
    print(f"\nScore distribution: {dict(score_counts)}")

    saved = save_results(results, today)
    print(f"Saved {saved} relevant papers to paper_log.csv")

    if not args.no_zotero and saved > 0:
        print("\nAdding to Zotero...")
        zot_added = add_to_zotero(results)
        print(f"Added {zot_added} papers to Zotero")
    elif args.no_zotero:
        print("Skipping Zotero upload (--no-zotero)")

    # Mark all papers as seen (both accepted and rejected)
    n_lines = mark_seen(new_papers)
    print(f"Added {n_lines} lines to seen_papers.txt")

    print("\nDone.")


if __name__ == "__main__":
    main()
