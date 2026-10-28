"""The morning email, rendered by code with inline styles (Gmail strips style blocks) and sent through Resend."""

from html import escape

import requests

from .config import Scope, Settings
from .zotero import open_access_pdf

MAX_CARDS = 25


def _card(cfg: Settings, scope: Scope, row: dict) -> str:
    link = escape(row["link"], quote=True)
    labels = " · ".join(scope.label(s) for s in row["strands"].split(";") if s)
    out = ['<div style="border:1px solid #e3e6e9;border-radius:8px;padding:14px 16px;margin-bottom:12px;">',
           f'<a href="{link}" style="color:#1155cc;text-decoration:none;font-weight:bold;font-size:15px;">'
           f'{escape(row["title"])}</a>']
    if row.get("authors"):
        out.append(f'<div style="color:#6b7178;font-size:12px;margin-top:5px;">{escape(row["authors"])}</div>')
    out.append(f'<div style="color:#6b7178;font-size:12.5px;margin-top:4px;">{escape(row["source"])} &middot; '
               f'<span style="color:#b5651d;">{escape(labels)}</span></div>')
    if row.get("evidence"):
        out.append(f'<p style="font-size:13px;color:#3d4249;margin:8px 0 10px;line-height:1.45;font-style:italic;">'
                   f'&ldquo;{escape(row["evidence"])}&rdquo;</p>')
    else:
        out.append('<p style="font-size:12.5px;color:#7a8087;margin:8px 0 10px;">Judged on the title: no abstract '
                   'was available after a week.</p>')
    buttons = (f'<a href="{link}" style="background:#e8734a;color:#ffffff;border-radius:6px;padding:4px 13px;'
               f'font-size:12px;font-weight:bold;text-decoration:none;display:inline-block;">Paper</a>')
    doi = row.get("doi")
    if doi and (pdf := open_access_pdf(cfg, doi)):
        buttons += (f'&nbsp;<a href="{escape(pdf, quote=True)}" style="background:#2b3a55;color:#ffffff;'
                    f'border-radius:6px;padding:4px 13px;font-size:12px;font-weight:bold;text-decoration:none;'
                    f'display:inline-block;">PDF</a>')
    if doi:
        buttons += f'&nbsp;<span style="color:#9aa0a6;font-size:12px;">{escape(doi)}</span>'
    out += [buttons, "</div>"]
    return "".join(out)


def build_html(cfg: Settings, scope: Scope, rows: list[dict], n_screened: int, failures: list[str]) -> str:
    rows = sorted(rows, key=lambda r: -float(r.get("probability") or 0))
    head = (f"{len(rows)} new paper{'s' if len(rows) != 1 else ''} for you, from {n_screened} screened."
            if rows else f"Nothing new matched today. {n_screened} papers screened.")
    parts = ['<div style="max-width:640px;font-family:Arial,Helvetica,sans-serif;">',
             f'<p style="font-size:14px;color:#24272b;">{escape(head)}</p>']
    parts += [_card(cfg, scope, r) for r in rows[:MAX_CARDS]]
    if len(rows) > MAX_CARDS:
        parts.append(f'<p style="font-size:12.5px;color:#7a8087;">Plus {len(rows) - MAX_CARDS} more in '
                     f'paper_log.csv.</p>')
    if failures:
        parts.append('<p style="font-size:12.5px;color:#7a8087;border-top:1px solid #eceef0;padding-top:10px;">'
                     'Problems in this round:<br>' + "<br>".join(escape(f) for f in failures) + "</p>")
    parts.append("</div>")
    return "\n".join(parts)


def subject(cfg: Settings, n: int, failures: list[str]) -> str:
    hello = f"Morning {cfg.greeting_name}!"
    if n:
        return f"{hello} {n} paper{'s' if n != 1 else ''} in today's round" + (" (with problems)" if failures else "")
    return f"{hello} The paper round hit a snag" if failures else f"{hello} Nothing new in today's round"


def send(cfg: Settings, api_key: str, scope: Scope, rows: list[dict], n_screened: int, failures: list[str]) -> None:
    resp = requests.post(
        "https://api.resend.com/emails", timeout=30,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"from": cfg.email_from, "to": [cfg.email_to], "subject": subject(cfg, len(rows), failures),
              "html": build_html(cfg, scope, rows, n_screened, failures)},
    )
    if not resp.ok:
        raise RuntimeError(f"Resend HTTP {resp.status_code}: {resp.text[:200]}")
