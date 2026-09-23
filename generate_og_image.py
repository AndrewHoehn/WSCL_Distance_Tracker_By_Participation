#!/usr/bin/env python3
"""
Generate og-image.png for social link previews.
1200x630, dark theme, hero stats about league-wide travel effort.
"""
import json
import os
import re
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (13, 17, 23)              # #0d1117
FG = (230, 237, 243)           # #e6edf3
MUTED = (139, 148, 158)        # #8b949e
ACCENT = (78, 205, 196)        # teal (matches dashboard accent)
ACCENT_WARM = (255, 230, 109)  # warm yellow for the big number

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def compute_stats():
    with open(os.path.join(SCRIPT_DIR, "wscl_distance_data.json")) as f:
        data = json.load(f)
    total_miles = sum(r["total_miles_traveled"] for r in data["travel_data"])
    total_minutes = sum(r["total_minutes_traveled"] for r in data["travel_data"])
    total_riders = sum(r["riders"] for r in data["travel_data"])
    teams = len({r["team"] for r in data["travel_data"]})
    races = len({r["date"] for r in data["travel_data"]})
    cost = total_miles * 0.725
    return {
        "miles": total_miles,
        "days": total_minutes / 60 / 24,
        "riders": total_riders,
        "teams": teams,
        "races": races,
        "cost": cost,
    }


def money(amount):
    return f"${amount/1_000_000:.2f}M" if amount >= 1_000_000 else f"${amount/1000:.0f}K"


def update_page_meta(stats):
    """Keep the dashboard's description and social-preview text in step with the data."""
    path = os.path.join(SCRIPT_DIR, "wscl_dashboard_v2.html")
    miles_m = f"{stats['miles']/1_000_000:.2f} million"
    blurb = (
        f"{miles_m} miles, {int(stats['days']):,} days on the road, and "
        f"{money(stats['cost'])} in family driving costs across {stats['races']} races "
        f"since 2023. A leaderboard for the WSCL teams and families putting in the work "
        f"to get kids to race day."
    )
    description = (
        "A leaderboard for the Washington Student Cycling League: how many miles each "
        "team drives, what it costs families, and how many hours parents put into "
        f"race-day travel. {miles_m[0].upper() + miles_m[1:]} miles tracked since 2023."
    )
    alt = f"WSCL Tracker: {miles_m} miles driven by WSCL families since 2023"
    tags = {
        r'<meta name="description" content="[^"]*">': f'<meta name="description" content="{description}">',
        r'<meta property="og:description" content="[^"]*">': f'<meta property="og:description" content="{blurb}">',
        r'<meta name="twitter:description" content="[^"]*">': f'<meta name="twitter:description" content="{blurb}">',
        r'<meta property="og:image:alt" content="[^"]*">': f'<meta property="og:image:alt" content="{alt}">',
    }
    with open(path, encoding="utf-8") as f:
        html = f.read()
    for pattern, replacement in tags.items():
        html, n = re.subn(pattern, lambda _: replacement, html)
        if n != 1:
            raise RuntimeError(f"Expected one match for {pattern}, found {n}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Updated page description: {blurb}")


def draw_stat(d, x, y, value, label, value_font, label_font, value_color=None):
    if value_color is None:
        value_color = FG
    d.text((x, y), value, font=value_font, fill=value_color)
    d.text((x, y + 52), label.upper(), font=label_font, fill=MUTED)


def main():
    stats = compute_stats()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # Subtle accent stripe at the top
    d.rectangle([0, 0, W, 4], fill=ACCENT)

    # Fonts
    chip_font = find_font(16, bold=True)
    hero_font = find_font(160, bold=True)
    hero_label_font = find_font(36, bold=True)
    sub_font = find_font(26)
    stat_value_font = find_font(44, bold=True)
    stat_label_font = find_font(16, bold=True)
    url_font = find_font(22, bold=True)

    PAD_X = 70

    # Brand chip
    d.text((PAD_X, 50), "WSCL  ·  TRACKER", font=chip_font, fill=ACCENT)

    # Hero number: total miles
    miles_str = f"{stats['miles']/1_000_000:.2f}M"
    d.text((PAD_X, 90), miles_str, font=hero_font, fill=ACCENT_WARM)
    d.text((PAD_X + 5, 265), "miles driven by WSCL families", font=hero_label_font, fill=FG)

    # Sub-tagline
    d.text((PAD_X, 330), "Tracking the hours, miles, and effort every team puts into", font=sub_font, fill=MUTED)
    d.text((PAD_X, 362), "getting their kids to race day — since 2023.", font=sub_font, fill=MUTED)

    # Stats strip
    strip_y = 440
    strip_h = 110
    d.rectangle([PAD_X - 10, strip_y - 10, W - (PAD_X - 10), strip_y + strip_h + 10], fill=(22, 27, 34, 255), outline=(48, 54, 61, 255), width=1)

    gap = (W - 2 * PAD_X) // 4
    col_x = [PAD_X + 10 + i * gap for i in range(4)]

    draw_stat(d, col_x[0], strip_y + 10, f"{int(stats['days']):,}", "days behind the wheel", stat_value_font, stat_label_font)
    draw_stat(d, col_x[1], strip_y + 10, money(stats['cost']), "family driving cost", stat_value_font, stat_label_font)
    draw_stat(d, col_x[2], strip_y + 10, f"{stats['teams']}", "teams tracked", stat_value_font, stat_label_font)
    draw_stat(d, col_x[3], strip_y + 10, f"{stats['races']}", "races", stat_value_font, stat_label_font)

    # URL at bottom
    d.text((PAD_X, 590), "wscltracker.com", font=url_font, fill=ACCENT)

    out = os.path.join(SCRIPT_DIR, "og-image.png")
    img.save(out, "PNG", optimize=True)
    print(f"Saved {out} ({os.path.getsize(out)/1024:.0f} KB)")
    update_page_meta(stats)
    print(f"  {stats['miles']:,.0f} miles, {stats['days']:.0f} days, ${stats['cost']:,.0f}, {stats['teams']} teams, {stats['races']} races")


if __name__ == "__main__":
    main()
