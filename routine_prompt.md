# Cloud routine prompt

This is the prompt for the scheduled cloud agent. Replace the placeholders —
`<YOUR_EMAIL>`, `<YOUR_ZOTERO_API_KEY>`, `<YOUR_RESEND_API_KEY>`,
`<YOUR_FROM_ADDRESS>` — then paste the whole fenced block below as the
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
pip install feedparser requests pyyaml --quiet
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

## 7. Email the digest via Resend

Gmail strips <style> blocks, so every style must be inline. Build
/tmp/digest.html by copying the templates below EXACTLY. Fill only the
UPPERCASE parts, change nothing else.

Open with (once):

```html
<div style="max-width:640px;font-family:Arial,Helvetica,sans-serif;">
<p style="font-size:14px;color:#24272b;">N relevant of X screened across all feeds.</p>
```

Then one card per paper, score-4 papers first. AUTHORS comes from the
paper's authors field in new_papers.json; omit that div when empty. Omit
the PDF anchor when the Zotero step found no open-access PDF. ID is the
bare DOI or arXiv id from the link; omit the span when there is none.

```html
<div style="border:1px solid #e3e6e9;border-radius:8px;padding:14px 16px;margin-bottom:12px;">
<a href="PAPER_URL" style="color:#1155cc;text-decoration:none;font-weight:bold;font-size:15px;">TITLE</a>
<div style="color:#6b7178;font-size:12px;margin-top:5px;">AUTHORS</div>
<div style="color:#6b7178;font-size:12.5px;margin-top:4px;">JOURNAL &middot; <span style="color:#e8a13c;">STARS</span> &middot; LABELS</div>
<p style="font-size:13px;color:#3d4249;margin:8px 0 10px;line-height:1.45;">SUMMARY</p>
<a href="PAPER_URL" style="background:#e8734a;color:#ffffff;border-radius:6px;padding:4px 13px;font-size:12px;font-weight:bold;text-decoration:none;display:inline-block;">Paper</a>&nbsp;<a href="PDF_URL" style="background:#2b3a55;color:#ffffff;border-radius:6px;padding:4px 13px;font-size:12px;font-weight:bold;text-decoration:none;display:inline-block;">PDF</a>&nbsp;<span style="color:#9aa0a6;font-size:12px;">ID</span>
</div>
```

Close with (once): </div>

- STARS: &#9733;&#9733;&#9733;&#9733; for score 4, &#9733;&#9733;&#9733;&#9734; for score 3
- If more than 25 papers are relevant, include the top 25 by score and
  add one muted <p> noting how many more are in paper_log.csv
- Only append a failure paragraph (muted style) if something failed:
  name the step and quote the exact error

Then write and run _send.py:

```python
import requests, os
html = open('/tmp/digest.html').read()
SUBJECT = 'Morning <YOUR_NAME>! N papers in today\'s round'  # N>0. For zero: 'Morning <YOUR_NAME>! Nothing new in today\'s round'. On failure: 'Morning <YOUR_NAME>! The paper round hit a snag'
r = requests.post('https://api.resend.com/emails',
    headers={'Authorization': f"Bearer {os.environ['RESEND_API_KEY']}", 'Content-Type': 'application/json'},
    json={'from': 'Literature Monitor <YOUR_FROM_ADDRESS>',
          'to': ['<YOUR_EMAIL>'],
          'subject': SUBJECT,
          'html': html})
print(r.status_code, r.text)
```

Delete _send.py afterward. A 200 response with an id means sent.

If Resend returns an error and a Gmail connector is attached, fall back to
creating a Gmail draft with the same content, and report the Resend error.

End the session with a final message that states, verbatim, one of:
- 'Digest EMAILED via Resend to <YOUR_EMAIL>: N relevant papers.'
- 'Resend FAILED (<exact error>); digest saved as Gmail DRAFT: N relevant papers.'
- 'Email FAILED entirely: <errors>. Digest follows:' + the full digest text.
This final message becomes the user's push notification, so it must carry
the true email status.
````
