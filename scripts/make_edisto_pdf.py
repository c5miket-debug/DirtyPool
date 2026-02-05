#!/usr/bin/env python3
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path

import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

TITLE = "Edisto Beach State Park — Spring RV Trip Guide"
SUBTITLE = "For two RV rigs (up to ~32 ft) • Target season: April–May"

IMG_URLS = [
  ("Edisto Beach State Park (Wikimedia Commons)", "https://upload.wikimedia.org/wikipedia/commons/0/0e/Edisto_Beach_State_Park.jpg"),
  ("Interpretive Center (NARA via Wikimedia Commons)", "https://upload.wikimedia.org/wikipedia/commons/2/2c/Edisto_Island_National_Scenic_Byway_-_Edisto_State_Park_Interpretive_Center_-_NARA_-_7718273.jpg"),
]

SOURCES = [
  ("Official camping + campground basics", "https://southcarolinaparks.com/edisto-beach/camping"),
  ("Reservations", "https://reserve.southcarolinaparks.com/edisto-beach"),
  ("Park main page", "https://southcarolinaparks.com/edisto-beach"),
  ("Edisto Chamber events", "https://edistochamber.com/category/events-weddings/"),
  ("Wikimedia Commons category", "https://commons.wikimedia.org/wiki/Category:Edisto_Beach_State_Park"),
]


def dl(url, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return out_path
    r = requests.get(url, timeout=60, headers={"User-Agent": "SiliconMinion/1.0"})
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return out_path


def bullets(items, max_width=95):
    out = []
    for it in items:
        wrapped = textwrap.fill(it, width=max_width, subsequent_indent="  ")
        out.append(f"• {wrapped}")
    return "\n".join(out)


def main():
    out_pdf = Path('/home/ubuntu/clawd/out/Edisto_Spring_RV_Trip_Guide.pdf')
    img_dir = Path('/home/ubuntu/clawd/out/images')

    # Download images
    local_imgs = []
    for label, url in IMG_URLS:
        fname = url.split('/')[-1]
        p = dl(url, img_dir / fname)
        local_imgs.append((label, p))

    styles = getSampleStyleSheet()
    h1 = styles['Title']
    h2 = styles['Heading2']
    body = styles['BodyText']

    doc = SimpleDocTemplate(str(out_pdf), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = []

    story.append(Paragraph(TITLE, h1))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph(SUBTITLE, styles['Italic']))
    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph(f"Prepared: {datetime.now().strftime('%b %d, %Y')}", body))
    story.append(Spacer(1, 0.25*inch))

    # Hero image
    label, img_path = local_imgs[0]
    story.append(Image(str(img_path), width=6.5*inch, height=4.2*inch, kind='proportional'))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(label, styles['Caption'] if 'Caption' in styles else styles['BodyText']))
    story.append(PageBreak())

    # Executive summary
    story.append(Paragraph('Executive summary', h2))
    story.append(Paragraph(
        "Edisto Beach State Park is an oceanfront South Carolina state park on Edisto Island with RV-friendly campsites, beach access, and marsh-side nature areas. For a spring meet-up with two rigs (~32 ft), April–May offers mild weather and fewer crowds than summer, but popular weekends (spring break/Easter) can book early.",
        body
    ))
    story.append(Spacer(1, 0.15*inch))

    story.append(Paragraph('Best spring windows (April–May)', h2))
    story.append(Paragraph(bullets([
        "Late March through mid-May is typically the sweet spot: comfortable temperatures, good birding, fewer crowds than summer.",
        "Expect higher demand around spring break weeks and Easter weekend—reserve early if targeting those dates.",
        "Weekdays and non-holiday weekends tend to be quieter and make it easier to get adjacent sites.",
    ]), body))
    story.append(Spacer(1, 0.15*inch))

    story.append(Paragraph('Campground + RV notes (two rigs ~32 ft)', h2))
    story.append(Paragraph(bullets([
        "Two campground areas: ocean-side and marsh-side (Live Oak). Both have water + electric hookups.",
        "Officially, several sites accommodate RVs up to ~40 ft; with 32 ft rigs you should have plenty of options, but still confirm site fit and maneuvering room per site photos/maps.",
        "All standard sites support 20/30/50 amp service; dump station available on-site; restrooms include hot showers.",
        "Strategy for friends: book specific site numbers that are adjacent/nearby; if you must book separately, coordinate site numbers in advance and call the park office to ask about nearby availability.",
    ]), body))

    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph('Reservations & policies (high level)', h2))
    story.append(Paragraph(bullets([
        "Reservations are handled through the SC State Parks reservation system; minimum stay is often 2 nights (check your dates).",
        "Book as early as possible if you want side-by-side sites. Spring weekends can go quickly.",
        "Always verify cancellation rules and check-in/out times on the reservation page for your specific booking.",
    ]), body))

    story.append(PageBreak())

    story.append(Paragraph('Things to do (spring-friendly)', h2))
    story.append(Paragraph(bullets([
        "Beach time + sunrise/sunset walks.",
        "Marsh boardwalks and nature trails; spring birding can be excellent.",
        "Kayaking/SUP in tidal creeks (plan around tides).",
        "Fishing: surf/pier nearby (check local rules and licenses).",
        "Environmental Learning Center / ranger programs (schedule varies).",
        "Biking: island roads and park areas—great for a group ride.",
    ]), body))

    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph('Nearby events & festivals (check current-year dates)', h2))
    story.append(Paragraph(bullets([
        "Edisto Chamber of Commerce posts community events, markets, and seasonal happenings.",
        "Spring craft/arts markets often appear in late March/early April (varies year to year).",
        "Recommendation: pick trip dates first, then confirm the event calendar for that exact week.",
    ]), body))

    # Second image
    label2, img2 = local_imgs[1]
    story.append(Spacer(1, 0.2*inch))
    story.append(Image(str(img2), width=6.0*inch, height=4.0*inch, kind='proportional'))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(label2, styles['BodyText']))

    story.append(PageBreak())

    story.append(Paragraph('Sample itineraries', h2))
    story.append(Paragraph('<b>3-day weekend</b><br/>' + bullets([
        "Day 1: arrive, set up, sunset beach walk, group cookout.",
        "Day 2: morning kayak/birding, afternoon beach + biking, optional ranger program.",
        "Day 3: short trail/boardwalk, brunch, depart.",
    ]), body))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph('<b>4-day (more relaxed)</b><br/>' + bullets([
        "Day 1: arrive + beach.",
        "Day 2: marsh paddle + local seafood night.",
        "Day 3: optional Charleston day trip or slow beach day.",
        "Day 4: final walk + depart.",
    ]), body))

    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph('Group coordination checklist', h2))
    story.append(Paragraph(bullets([
        "Share site numbers + arrival windows ahead of time.",
        "Bring a shared grocery list and one “group meal” night.",
        "Pack bug spray (marsh areas), sunscreen, and a tide chart for paddling.",
        "If rain: keep a Charleston indoor backup plan (museums/food/markets).",
    ]), body))

    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph('Sources & links', h2))
    for name, url in SOURCES:
        story.append(Paragraph(f"<b>{name}:</b> {url}", body))
        story.append(Spacer(1, 0.06*inch))

    doc.build(story)
    print(str(out_pdf))


if __name__ == '__main__':
    main()
