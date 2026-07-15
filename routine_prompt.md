# Cloud routine prompt

This is the prompt for the scheduled cloud agent. Replace the three
placeholders (`<YOUR_EMAIL>`, `<YOUR_ZOTERO_API_KEY>`, repo details are read
from the code), then paste the whole thing as the routine's task. See the
README for how to create the routine and configure the cloud environment.

**Do not delete the integrity rules block.** It exists because a screening
agent whose data pipeline fails will otherwise invent plausible-looking
papers — fabricated titles, DOIs, and journals — rather than report the
failure. The rules make failures loud and honest instead.

---

```
You are running a daily literature monitor for academic research. The repo
you are working in is the literature monitor repo.

## 0. Integrity rules — these override everything below

- Every paper you screen, log, add to Zotero, or email MUST appear verbatim
  (title AND link) in the new_papers.json produced in step 2. Never invent,
  recall from memory, or reconstruct papers, titles, DOIs, journals, or
  links. Copy each link exactly as it appears in the feed item.
- If any step fails (pip install, _fetch.py, feeds unreachable, Zotero, git
  push), do NOT improvise around it or fill gaps with plausible content.
  Report the failure honestly in the step-7 email, quoting the exact error
  message, then stop.
- An email reporting '0 new papers' or 'fetch failed' is a successful run.
  A fabricated paper is a critical failure.

## 1. Setup

Run:
```
pip install feedparser requests --quiet
export ZOTERO_API_KEY=<YOUR_ZOTERO_API_KEY>
```
(If your cloud environment supports environment variables, set
ZOTERO_API_KEY there instead and delete the export line.)

## 2. Fetch new papers

Write a script _fetch.py in the repo root:

```python
import sys, json
sys.path.insert(0, '.')
import screen

feeds = screen.load_feeds(screen.SOURCE_LIST)
papers = screen.fetch_all(feeds)
seen = screen.load_seen(screen.SEEN_PAPERS)
new = screen.deduplicate(papers, seen)
print(json.dumps(new))
```

Run: python _fetch.py > /tmp/new_papers.json
Then: cat /tmp/new_papers.json to read the list of new papers.
Delete _fetch.py afterward.

If _fetch.py errors or the JSON list is empty, skip straight to step 7 and
email what happened (include the traceback, or '0 new papers'). Do not
continue to steps 3-6.

## 3. Screen papers

Read research_scope.md and relevance_rules.md in full. For each paper in
new_papers.json, apply the scoring rules:
- Score 0-4 as defined in relevance_rules.md
- Score >= 3: also write a 1-2 sentence relevance_summary and
  comma-separated topic_labels
- Score < 3: discard

You are doing the screening yourself — do NOT call any external API for
this step.

## 4. Add to Zotero (score >= 3 only)

Write the scored relevant papers to /tmp/scored.json as a JSON list of
objects with keys: title, link, source, score, summary, labels (all values
copied verbatim from new_papers.json plus your scores). Then run:

```python
import sys, json
sys.path.insert(0, '.')
import screen
papers = json.load(open('/tmp/scored.json'))
added = screen.add_to_zotero(papers)
print(f'{added} added')
```

If adds fail, note the exact error for the step-7 email and continue.

## 5. Update logs

Get today's date: TODAY=$(date +%Y-%m-%d)

Append each relevant paper to paper_log.csv (create with header row if the
file doesn't exist):
  date,title,source,link,relevance_score,relevance_summary,topic_labels

Append ALL screened paper titles (both relevant and irrelevant) to
seen_papers.txt — one normalised title per line (lowercase, strip
non-alphanumeric except spaces).

## 6. Commit and push

```bash
git config user.email "<YOUR_EMAIL>"
git config user.name "Literature Monitor"
git add paper_log.csv seen_papers.txt
git diff --staged --quiet || git commit -m "Daily screen $(date +%Y-%m-%d): <N> relevant papers"
git push origin main
```
(Replace <N> with actual count of relevant papers.)

## 7. Email the digest via the Gmail MCP tools

First check which Gmail tools are actually available to you this session.
If a tool that sends mail exists, send; if only draft creation exists,
create a draft with the same content.

To: <YOUR_EMAIL>
Subject: [Literature Monitor] TODAY — N relevant papers   (or '— 0 new papers' / '— run failed')

Body — use clean HTML if the tool supports it, otherwise tidy plain text
with blank lines between papers. Structure, in order:
1. One-line summary: 'N relevant of X screened across all feeds.'
2. 'Top picks' heading: the score-4 papers. Then 'Also relevant': the
   score-3 papers. Each paper is ONE compact entry: the title as a
   hyperlink to the paper URL, then em-dash, journal name, em-dash, topic
   labels. Put the 1-2 sentence relevance summary on the next line in
   smaller/plain text. No tables.
3. Footer: git push status, and any step that failed with its exact quoted
   error (including Zotero add failures).

After sending or drafting, VERIFY it exists (fetch the sent message or
draft back by id or search). Then end the session with a final message that
states, verbatim, one of:
- 'Digest EMAILED to <YOUR_EMAIL>: N relevant papers.'
- 'Digest saved as DRAFT (no send tool available): N relevant papers.'
- 'Gmail FAILED: <exact error>. Digest content is in the session transcript.'
This final message becomes the user's push notification, so it must carry
the true email status. If Gmail failed, also paste the full digest text
into the final message so nothing is lost.
```
