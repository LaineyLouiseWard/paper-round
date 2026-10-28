"""Add kept papers to a Zotero collection: Crossref metadata, an open-access PDF link, never the same DOI twice."""

import requests

from .config import Settings
from .sources import strip_html


def _base(cfg: Settings) -> str:
    kind = "groups" if cfg.zotero_library_type == "group" else "users"
    return f"https://api.zotero.org/{kind}/{cfg.zotero_library_id}"


def crossref_metadata(cfg: Settings, doi: str) -> dict:
    try:
        resp = requests.get(f"https://api.crossref.org/works/{requests.utils.quote(doi, safe='')}",
                            headers={"User-Agent": f"PaperRound/2 ({cfg.contact_email})"}, timeout=15)
        resp.raise_for_status()
        d = resp.json()["message"]
    except Exception:
        return {}
    parts = (d.get("published") or d.get("created") or {}).get("date-parts", [[None]])
    return {
        "title": (d.get("title") or [""])[0],
        "creators": [{"creatorType": "author", "firstName": a.get("given", ""), "lastName": a.get("family", "")}
                     for a in d.get("author", [])],
        "publicationTitle": (d.get("container-title") or [""])[0],
        "volume": d.get("volume", ""), "issue": d.get("issue", ""), "pages": d.get("page", ""),
        "date": str(parts[0][0]) if parts and parts[0][0] else "",
        "ISSN": (d.get("ISSN") or [""])[0],
        "abstractNote": strip_html(d.get("abstract", "")),
    }


def open_access_pdf(cfg: Settings, doi: str) -> str | None:
    try:
        resp = requests.get(f"https://api.unpaywall.org/v2/{requests.utils.quote(doi, safe='')}",
                            params={"email": cfg.contact_email}, timeout=15)
        if not resp.ok:
            return None
        best = resp.json().get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url_for_landing_page")
    except Exception:
        return None


def add(cfg: Settings, api_key: str, row: dict, tags: list[str]) -> str:
    """Add one log row. Returns 'added:KEY', 'exists' or 'failed: why'."""
    headers = {"Zotero-API-Key": api_key, "Content-Type": "application/json"}
    doi = row.get("doi") or ""
    try:
        if doi:
            hit = requests.get(f"{_base(cfg)}/items", headers=headers, timeout=15,
                               params={"q": doi, "qmode": "everything", "limit": 1})
            if hit.ok and hit.json():
                return "exists"
        item = {"itemType": "journalArticle", "title": row["title"], "url": row["link"],
                "collections": [cfg.zotero_collection] if cfg.zotero_collection else [],
                "tags": [{"tag": t} for t in tags],
                "extra": f"Paper Round: {row.get('evidence', '')}".strip()}
        if doi:
            item.update({k: v for k, v in crossref_metadata(cfg, doi).items() if v})
            item["DOI"] = doi
        resp = requests.post(f"{_base(cfg)}/items", headers=headers, json=[item], timeout=30)
        keys = resp.json().get("success", {}) if resp.ok else {}
        if not keys:
            return f"failed: HTTP {resp.status_code} {resp.text[:120]}"
        key = next(iter(keys.values()))
        if doi and (pdf := open_access_pdf(cfg, doi)):
            requests.post(f"{_base(cfg)}/items", headers=headers, timeout=30, json=[{
                "itemType": "attachment", "linkMode": "linked_url", "title": "Open Access PDF",
                "url": pdf, "contentType": "application/pdf", "parentItem": key}])
        return f"added:{key}"
    except Exception as e:
        return f"failed: {e}"
