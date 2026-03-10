#!/usr/bin/env python3
"""
BKFC Event Scraper
Scrapes upcoming events from bkfc.com and generates a .ics calendar file.
Event times are automatically converted to the system's local timezone.
"""

import re
import time as time_module
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from icalendar import Calendar, Event


BKFC_EVENTS_URL = "https://www.bkfc.com/events"
WATCH_URL = "https://watch.bkfc.com/"
SOURCE_URL = "https://www.bkfc.com"
OUTPUT_FILE = "BKFC_Events.ics"


def get_local_timezone() -> ZoneInfo:
    """Auto-detect the system's local timezone."""
    try:
        # Works on Linux/macOS (reads /etc/localtime symlink)
        import subprocess
        result = subprocess.run(
            ["timedatectl", "show", "--property=Timezone", "--value"],
            capture_output=True, text=True
        )
        tz_name = result.stdout.strip()
        if tz_name:
            return ZoneInfo(tz_name)
    except Exception:
        pass

    try:
        # Fallback: use tzlocal if available
        from tzlocal import get_localzone
        return get_localzone()
    except ImportError:
        pass

    # Final fallback: read the UTC offset from time module
    offset_seconds = -time_module.timezone if time_module.daylight == 0 else -time_module.altzone
    offset_hours = offset_seconds // 3600
    # Map common UTC offsets to IANA timezone names
    offset_map = {
        -12: "Etc/GMT+12", -11: "Etc/GMT+11", -10: "Pacific/Honolulu",
        -9: "America/Anchorage", -8: "America/Los_Angeles", -7: "America/Denver",
        -6: "America/Chicago", -5: "America/New_York", -4: "America/Halifax",
        -3: "America/Sao_Paulo", -2: "Etc/GMT+2", -1: "Atlantic/Azores",
        0: "UTC", 1: "Europe/London", 2: "Europe/Paris", 3: "Europe/Moscow",
        4: "Asia/Dubai", 5: "Asia/Karachi", 6: "Asia/Dhaka",
        7: "Asia/Bangkok", 8: "Asia/Singapore", 9: "Asia/Tokyo",
        10: "Australia/Sydney", 11: "Pacific/Noumea", 12: "Pacific/Auckland",
    }
    tz_name = offset_map.get(offset_hours, "UTC")
    print(f"  ℹ️  Could not detect timezone by name — using UTC{offset_hours:+d} → {tz_name}")
    return ZoneInfo(tz_name)


def fetch_page(url: str) -> BeautifulSoup:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_events(soup: BeautifulSoup) -> list[dict]:
    events = []

    # Each event block contains an <a> tag wrapping the card
    event_blocks = soup.find_all("a", href=re.compile(r"^/events/"))

    seen_slugs = set()

    for block in event_blocks:
        href = block.get("href", "")
        slug = href.strip("/").split("/")[-1]

        # Skip duplicates (the page lists some events twice)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Title
        title_tag = block.find(["h2", "h3"])
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        # Date & time — look for text that matches date patterns nearby
        text = block.get_text(" ", strip=True)

        # Match patterns like "March 14, 2026 3:00 PM"
        dt_match = re.search(
            r"(\w+ \d{1,2},\s*\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)", text
        )
        if not dt_match:
            continue

        date_str = dt_match.group(1).strip()
        time_str = dt_match.group(2).strip()

        try:
            # BKFC times are published in UTC — we'll convert to local tz in build_ics
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        except ValueError:
            continue

        # Location — look for lines that appear after the date pattern
        location = ""
        lines = [l.strip() for l in text.split("  ") if l.strip()]
        for i, line in enumerate(lines):
            if re.search(r"\d{4}", line) and i + 1 < len(lines):
                candidate = lines[i + 1]
                # Heuristic: location lines often contain a dash or comma
                if re.search(r"[-,]", candidate) and len(candidate) < 100:
                    location = candidate
                    break

        events.append({
            "title": title,
            "datetime": dt,  # timezone-aware UTC datetime
            "location": location,
            "url": f"https://www.bkfc.com{href}",
            "slug": slug,
        })

    return events


def build_ics(events: list[dict], local_tz: ZoneInfo) -> bytes:
    tz_name = str(local_tz)

    cal = Calendar()
    cal.add("prodid", "-//BKFC Events Scraper//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "BKFC Events")
    cal.add("x-wr-timezone", tz_name)

    for evt in events:
        # Convert UTC event time to local timezone
        local_dt = evt["datetime"].astimezone(local_tz)
        local_dt_end = local_dt + timedelta(hours=4)

        description = (
            f"📺 How to Watch: BKFC+ — {WATCH_URL}\n"
            f"🔗 Event Info: {evt['url']}\n"
            f"\n"
            f"Source: {SOURCE_URL}"
        )

        vevent = Event()
        vevent.add("summary", evt["title"])
        vevent.add("dtstart", local_dt)
        vevent.add("dtend", local_dt_end)
        vevent.add("url", evt["url"])
        vevent.add("description", description)
        if evt["location"]:
            vevent.add("location", evt["location"])
        vevent["uid"] = f"{evt['slug']}@bkfc-calendar"
        cal.add_component(vevent)

    return cal.to_ical()


def main():
    print(f"🌍 Detecting local timezone ...")
    local_tz = get_local_timezone()
    print(f"   Timezone: {local_tz}")

    print(f"\n📡 Fetching events from {BKFC_EVENTS_URL} ...")
    soup = fetch_page(BKFC_EVENTS_URL)

    events = parse_events(soup)
    print(f"   Found {len(events)} events.\n")

    if not events:
        print("⚠️  No events found — check if the site structure has changed.")
        return

    for e in events:
        local_dt = e["datetime"].astimezone(local_tz)
        print(f"  • {local_dt.strftime('%b %d, %Y %I:%M %p %Z')}  |  {e['title']}")

    ics_bytes = build_ics(events, local_tz)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(ics_bytes)

    print(f"\n✅ Calendar saved to {OUTPUT_FILE} (times in {local_tz})")


if __name__ == "__main__":
    main()
