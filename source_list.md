# Monitoring Sources

The feeds your monitor screens every day. Replace the examples below with
the journals in your field, keeping the exact format — `screen.py` parses
this file looking for:

```
### N. Journal Name
- **Feed:** `https://feed-url`
```

Everything else (the **Why** and **Expected noise** lines) is documentation
for you, not the parser. Aim for 6–10 feeds: enough for coverage, few enough
that screening stays cheap and the digest stays readable.

---

## Feeds (3 examples — replace with your own)

### 1. Hydrology and Earth System Sciences (Copernicus/EGU)
- **Feed:** `https://hess.copernicus.org/xml/rss2_0.xml`
- **Why:** Example of a Copernicus/EGU journal — their `/xml/rss2_0.xml` feeds work reliably from scripts.
- **Expected noise:** Depends on your scope.

### 2. Geophysical Research Letters (AGU/Wiley)
- **Feed:** `https://agupubs.onlinelibrary.wiley.com/feed/19448007/most-recent`
- **Why:** Example of a Wiley journal — use the ISSN-based `/feed/{issn}/most-recent` pattern (the human-facing `showFeed` URLs return 404 from scripts).
- **Expected noise:** High for broad journals; abstract screening handles it.

### 3. arXiv — Atmospheric and Oceanic Physics
- **Feed:** `https://export.arxiv.org/rss/physics.ao-ph`
- **Why:** Example of an arXiv category feed — catches preprints weeks to months before journal publication. Pick your category from arxiv.org.
- **Expected noise:** Moderate.

---

## Finding working feed URLs by publisher

| Publisher | Pattern | Notes |
|---|---|---|
| Copernicus/EGU | `https://<journal>.copernicus.org/xml/rss2_0.xml` | Works directly |
| Wiley (AGU, RMetS, …) | `https://<domain>/feed/{ISSN}/most-recent` | Use the ISSN, not the journal code |
| IOP | `https://iopscience.iop.org/journal/rss/{ISSN}` | Works directly |
| arXiv | `https://export.arxiv.org/rss/{category}` | Works directly |
| AMS | RSS is blocked by CloudFront bot protection | Add the journal to `CROSSREF_FALLBACKS` in `screen.py` instead (name substring → ISSN); articles then come from the free Crossref API |
| Elsevier | RSS unreliable from scripts | Prefer a Copernicus/Wiley journal covering the same niche, or a Crossref fallback |

Verify a candidate feed with `python screen.py --dry-run` before keeping it.

---

## Considered but excluded

Keep a record of feeds you evaluated and rejected, and why — it stops you
re-evaluating the same source in six months. Example:

| Source | Reason for exclusion |
|---|---|
| (journal) | (covered elsewhere / broken feed / low yield) |
