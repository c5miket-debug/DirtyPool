#!/usr/bin/env python3
"""Fetch recent Gmail messages via IMAP (app password).

Designed for siliconminion@gmail.com use-cases.

Outputs JSON:
{
  "items": [
    {
      "uid": 123,
      "date": "...",
      "from": "...",
      "subject": "...",
      "text": "..."  # best-effort plain text
    }
  ]
}

Notes:
- Uses UID-based incremental fetch with a state file.
- Filters by FROM domain and optional subject contains.
"""

import argparse
import email
import email.message
import imaplib
import json
import os
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path


def _read_secret(path: str) -> str:
    return Path(path).read_text().strip().replace(' ', '')


def _decode_header(val: str | None) -> str:
    if not val:
        return ''
    parts = decode_header(val)
    out = ''
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out += chunk.decode(enc or 'utf-8', errors='ignore')
        else:
            out += chunk
    return out


def _strip_html(raw: str) -> str:
    # Rough HTML strip (aim: readable text, no boilerplate)
    html = raw
    html = re.sub(r"<!doctype[\s\S]*?>", " ", html, flags=re.I)
    html = re.sub(r"<head[\s\S]*?</head>", " ", html, flags=re.I)
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    # Remove common hidden/preheader spans
    html = re.sub(r"<span[^>]*display\s*:\s*none[^>]*>[\s\S]*?</span>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _looks_like_html(text: str) -> bool:
    t = (text or '').lower()
    return ('<!doctype' in t) or ('<html' in t) or ('<head' in t) or ('<body' in t) or ('</' in t)


def _strip_footer(text: str) -> str:
    """Drop common email footer boilerplate (unsubscribe, privacy, address blocks)."""
    if not text:
        return ''
    lines = [l.rstrip() for l in text.splitlines()]
    cut_idx = None
    footer_markers = [
        r'unsubscribe',
        r'manage\s+preferences',
        r'privacy\s+policy',
        r'terms\s+of\s+(service|use)',
        r'view\s+in\s+browser',
        r'you\s+received\s+this\s+email',
        r'all\s+rights\s+reserved',
        r'copyright',
        r'\baddress\b',
        r'\bpo\s*box\b',
        r'\bst\.?\b|\bstreet\b|\bave\b|\bavenue\b|\broad\b|\brd\b',
    ]
    rx = re.compile('|'.join(footer_markers), re.I)
    for i, l in enumerate(lines):
        if rx.search(l.strip()):
            cut_idx = i
            break
    if cut_idx is not None and cut_idx > 0:
        lines = lines[:cut_idx]
    # remove tiny trailing lines
    while lines and len(lines[-1].strip()) == 0:
        lines.pop()
    return '\n'.join(lines).strip()


def _msg_text(msg: email.message.Message) -> str:
    # Prefer text/plain; fallback to stripped text/html.
    if msg.is_multipart():
        plain = None
        html = None
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get('Content-Disposition') or '').lower()
            if 'attachment' in disp:
                continue
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            text = payload.decode(charset, errors='ignore')
            if ctype == 'text/plain' and plain is None:
                plain = text
            elif ctype == 'text/html' and html is None:
                html = text
        if plain:
            plain = plain.strip()
            if _looks_like_html(plain):
                return _strip_footer(_strip_html(plain))
            return _strip_footer(plain)
        if html:
            return _strip_footer(_strip_html(html))
        return ''
    else:
        payload = msg.get_payload(decode=True) or b''
        charset = msg.get_content_charset() or 'utf-8'
        text = payload.decode(charset, errors='ignore').strip()
        if _looks_like_html(text):
            return _strip_footer(_strip_html(text))
        return _strip_footer(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', required=True)
    ap.add_argument('--app-pass-file', required=True)
    ap.add_argument('--state-file', required=True)
    ap.add_argument('--from-domain', default='patreon.com')
    ap.add_argument('--subject-contains', action='append', default=[])
    ap.add_argument('--limit', type=int, default=20)
    args = ap.parse_args()

    state_path = Path(args.state_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception:
            state = {}
    last_uid = int(state.get('last_uid') or 0)

    app_pass = _read_secret(args.app_pass_file)

    M = imaplib.IMAP4_SSL('imap.gmail.com')
    M.login(args.user, app_pass)
    M.select('INBOX')

    # Build search: FROM domain and UID range
    # Gmail IMAP doesn't support FROM domain directly; use FROM patreon.com substring.
    criteria = [f'UID {last_uid+1}:*', 'FROM', f'"{args.from_domain}"']
    # SUBJECT contains (OR chain) is messy; fetch broad then filter client-side.
    typ, data = M.uid('SEARCH', None, *criteria)
    uids = []
    if typ == 'OK' and data and data[0]:
        uids = [int(x) for x in data[0].split() if x.isdigit()]

    uids.sort()
    items = []
    max_uid_seen = last_uid

    for uid in uids[-args.limit:]:
        typ, msg_data = M.uid('FETCH', str(uid), '(RFC822)')
        if typ != 'OK' or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        subj = _decode_header(msg.get('Subject'))
        if args.subject_contains:
            if not any(s.lower() in subj.lower() for s in args.subject_contains):
                continue
        frm = _decode_header(msg.get('From'))
        date_hdr = msg.get('Date')
        try:
            dt = parsedate_to_datetime(date_hdr) if date_hdr else None
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = None
        text = _msg_text(msg)
        items.append({
            'uid': uid,
            'date': (dt.isoformat() if dt else ''),
            'from': frm,
            'subject': subj,
            'text': text[:20000],
        })
        max_uid_seen = max(max_uid_seen, uid)

    # Update state if we saw any UID (even if filtered) — safe to move forward
    if uids:
        state['last_uid'] = max(max_uid_seen, max(uids))
    state['updatedAt'] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2))

    M.logout()

    print(json.dumps({'items': items}, indent=2))


if __name__ == '__main__':
    main()
