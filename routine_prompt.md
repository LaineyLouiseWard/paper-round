# Cloud routine prompt

This is the prompt for the scheduled cloud agent. Replace the placeholders —
`<YOUR_EMAIL>`, `<YOUR_ZOTERO_API_KEY>`, `<YOUR_RESEND_API_KEY>` — then
set the email block in config.yaml (from, to, greeting_name) and paste the whole fenced block below as the
routine's task. See the README for how to create the routine and configure
the cloud environment.

**Do not delete the integrity rules block.** It exists because a screening
agent whose data pipeline fails will otherwise invent plausible-looking
papers — fabricated titles, DOIs, and journals — rather than report the
failure. The rules make failures loud and honest instead.

**Why Resend and not the Gmail connector:** Google's Gmail connector
exposes no send tool — it can only create drafts, which sit unnoticed in
your Drafts folder. Resend's free tier is ample for one email a day: without
a verified domain use `onboarding@resend.dev` as the from-address (delivers
only to your own Resend account email); with a verified domain use any
address on it. If you attach a Gmail connector to the routine anyway, it
serves as a draft fallback when Resend errors.

---

````
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

```bash
pip install requests pyyaml --quiet
pip install --no-deps feedparser --quiet
export ZOTERO_API_KEY=<YOUR_ZOTERO_API_KEY>
export RESEND_API_KEY=<YOUR_RESEND_API_KEY>
# Only if config.yaml lists openalex_sources:
# export OPENALEX_API_KEY=<YOUR_OPENALEX_API_KEY>
```

(If your cloud environment supports environment variables, set the keys
there instead and delete the export lines.)

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
objects with keys: title, link, source, authors, score, summary, labels (all values
copied verbatim from new_papers.json plus your scores). Then run:

```python
import sys, json
sys.path.insert(0, '.')
import screen
papers = json.load(open('/tmp/scored.json'))
fetched = json.load(open('/tmp/new_papers.json'))
papers, dropped = screen.validate_scored(papers, fetched)
json.dump(papers, open('/tmp/scored.json', 'w'))
if dropped:
    print('INTEGRITY: dropped, not in fetched data:', dropped)
added = screen.add_to_zotero(papers)
print(f'{added} added')
```

The validate_scored line is the integrity gate: papers that are not in
the fetched data are dropped before they can reach Zotero, the log, or
the email. If anything is dropped, record it as a failure for step 7.
If adds fail, note the exact error for the step-7 email and continue.

## 5. Update logs

Get today's date: TODAY=$(date +%Y-%m-%d)

Append each relevant paper to paper_log.csv (create with header row if the
file doesn't exist):
  date,title,source,link,relevance_score,relevance_summary,topic_labels

Mark ALL screened papers (both relevant and irrelevant) as seen by running:

```python
import sys, json
sys.path.insert(0, '.')
import screen
new = json.load(open('/tmp/new_papers.json'))
print(screen.mark_seen(new), 'lines added to seen_papers.txt')
```

## 6. Commit and push

```bash
git config user.email "<YOUR_EMAIL>"
git config user.name "Literature Monitor"
git add paper_log.csv seen_papers.txt
git diff --staged --quiet || git commit -m "Daily screen $(date +%Y-%m-%d): <N> relevant papers"
git push origin main
```

(Replace <N> with actual count of relevant papers.)

## 7. Email the digest

The email is rendered and sent by code, not by you. Run:

```python
import sys, json
sys.path.insert(0, '.')
import screen
try:
    papers = json.load(open('/tmp/scored.json'))
except FileNotFoundError:
    papers = []
failures = []  # add the exact quoted error string for any step that failed
print(screen.send_digest(papers, n_screened=TOTAL_SCREENED, failures=failures))
```

Replace TOTAL_SCREENED with the number of papers screened this run (0 if
the fetch failed) and put any failure messages in the list. A 200
response with an id means sent.

If Resend returns an error and a Gmail connector is attached, fall back to
creating a Gmail draft with the same content, and report the Resend error.

End the session with a final message that states, verbatim, one of:
- 'Digest EMAILED via Resend to <YOUR_EMAIL>: N relevant papers.'
- 'Resend FAILED (<exact error>); digest saved as Gmail DRAFT: N relevant papers.'
- 'Email FAILED entirely: <errors>. Digest follows:' + the full digest text.
This final message becomes the user's push notification, so it must carry
the true email status.
````
