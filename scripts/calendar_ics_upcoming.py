#!/usr/bin/env python3
"""Fetch a Google Calendar .ics feed and print upcoming events as JSON.

Outputs: [{"start": "2026-02-01T...-05:00", "end": "...", "title": "..."}, ...]

Notes:
- Intended for read-only private .ics URLs.
- Best-effort parsing; handles DTSTART/DTEND in common formats.
"""

import argparse
import json
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

DT_RE = re.compile(r"^(DTSTART|DTEND)(;[^:]*)?:(.*)$")
SUM_RE = re.compile(r"^SUMMARY:(.*)$")
BEGIN_EVT = "BEGIN:VEVENT"
END_EVT = "END:VEVENT"


def parse_dt(raw: str, tzid: str | None):
    raw = raw.strip()
    # Zulu
    if raw.endswith('Z'):
        # 20260201T133000Z
        dt = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt
    # Date-only
    if re.fullmatch(r"\d{8}", raw):
        dt = datetime.strptime(raw, "%Y%m%d")
        if tzid and ZoneInfo:
            return dt.replace(tzinfo=ZoneInfo(tzid))
        return dt.replace(tzinfo=timezone.utc)
    # Local date-time
    if re.fullmatch(r"\d{8}T\d{6}", raw):
        dt = datetime.strptime(raw, "%Y%m%dT%H%M%S")
        if tzid and ZoneInfo:
            return dt.replace(tzinfo=ZoneInfo(tzid))
        return dt.replace(tzinfo=timezone.utc)
    # Fallback: try ISO
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url-file', required=True)
    ap.add_argument('--days', type=int, default=1)
    ap.add_argument('--tz', default='America/New_York')
    ap.add_argument('--limit', type=int, default=20)
    args = ap.parse_args()

    url = open(args.url_file).read().strip()
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(url, context=ctx, timeout=30) as r:
        ics = r.read().decode('utf-8', 'ignore').splitlines()

    now = datetime.now(ZoneInfo(args.tz) if ZoneInfo else timezone.utc)
    horizon = now + timedelta(days=args.days)

    events = []
    in_evt = False
    cur = {'start': None, 'end': None, 'title': None, 'tzid': None}

    for line in ics:
        line = line.strip()
        if line == BEGIN_EVT:
            in_evt = True
            cur = {'start': None, 'end': None, 'title': None, 'tzid': None}
            continue
        if line == END_EVT:
            in_evt = False
            if cur['start'] and cur['title']:
                start = cur['start']
                end = cur['end']
                # Normalize to desired tz for output
                out_tz = ZoneInfo(args.tz) if ZoneInfo else timezone.utc
                try:
                    start_out = start.astimezone(out_tz)
                except Exception:
                    start_out = start
                if end:
                    try:
                        end_out = end.astimezone(out_tz)
                    except Exception:
                        end_out = end
                else:
                    end_out = None

                if now <= start_out <= horizon:
                    events.append({
                        'start': start_out.isoformat(),
                        'end': end_out.isoformat() if end_out else None,
                        'title': cur['title']
                    })
            continue

        if not in_evt:
            continue

        m = SUM_RE.match(line)
        if m:
            cur['title'] = m.group(1)
            continue

        m = DT_RE.match(line)
        if m:
            kind, params, value = m.group(1), (m.group(2) or ''), m.group(3)
            tzid = None
            if 'TZID=' in params:
                # e.g. ;TZID=America/New_York
                tzid = params.split('TZID=')[1].split(';')[0]
            dt = parse_dt(value, tzid)
            if dt is None:
                continue
            if kind == 'DTSTART':
                cur['start'] = dt
            else:
                cur['end'] = dt
            continue

    events.sort(key=lambda e: e['start'])
    events = events[: args.limit]
    print(json.dumps(events, indent=2))


if __name__ == '__main__':
    main()
