#!/usr/bin/env python3
import argparse
import ssl
import smtplib
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


def _read_secret(path: str) -> str:
    return Path(path).read_text().strip().replace(' ', '')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--from', dest='from_addr', required=True)
    p.add_argument('--to', dest='to_addr', required=True)

    subj = p.add_mutually_exclusive_group(required=True)
    subj.add_argument('--subject')
    subj.add_argument('--subject-template', help='strftime template (see Python datetime.strftime docs)')

    p.add_argument('--tz', default='America/New_York', help='Timezone for subject-template (default: America/New_York)')

    p.add_argument('--body-file', required=True, help='Plaintext body')
    p.add_argument('--html-file', help='Optional HTML body (used as alternative)')

    p.add_argument('--app-pass-file', required=True)

    # Attachments
    p.add_argument('--attach', action='append', default=[], help='Attachment file path (repeatable)')

    # Best-effort dedupe: if file exists, do not send. Create it after success.
    p.add_argument('--dedupe-file', help='If exists, skip send; otherwise create after success')

    args = p.parse_args()

    if args.dedupe_file and Path(args.dedupe_file).exists():
        # Already sent for this key
        return

    app_pass = _read_secret(args.app_pass_file)
    body_text = Path(args.body_file).read_text()

    if args.subject_template:
        if ZoneInfo:
            now = datetime.now(ZoneInfo(args.tz))
        else:
            now = datetime.now()
        subject = now.strftime(args.subject_template)
    else:
        subject = args.subject

    msg = EmailMessage()
    msg['From'] = args.from_addr
    msg['To'] = args.to_addr
    msg['Subject'] = subject

    msg.set_content(body_text)

    if args.html_file:
        html = Path(args.html_file).read_text()
        msg.add_alternative(html, subtype='html')

    # Attachments (best-effort MIME guess)
    for apath in (args.attach or []):
        pth = Path(apath)
        if not pth.exists():
            continue
        data = pth.read_bytes()
        filename = pth.name
        maintype, subtype = 'application', 'octet-stream'
        if filename.lower().endswith('.pdf'):
            maintype, subtype = 'application', 'pdf'
        elif filename.lower().endswith(('.jpg','.jpeg')):
            maintype, subtype = 'image', 'jpeg'
        elif filename.lower().endswith('.png'):
            maintype, subtype = 'image', 'png'
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    context = ssl.create_default_context()
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as s:
        s.ehlo()
        s.starttls(context=context)
        s.ehlo()
        s.login(args.from_addr, app_pass)
        s.send_message(msg)

    if args.dedupe_file:
        Path(args.dedupe_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.dedupe_file).write_text(datetime.utcnow().isoformat() + 'Z\n')


if __name__ == '__main__':
    main()
