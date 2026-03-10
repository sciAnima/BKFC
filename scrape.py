#!/usr/bin/env python3
"""
BKFC Event Scraper
Scrapes upcoming events from bkfc.com and generates a .ics calendar file.
Event times are automatically converted to the system's local timezone.
"""

import re
import sys
import time as time_module
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event


BKFC_EVENTS_URL = "https://www.bkfc.com/events"
WATCH_URL = "https://watch.bkfc.com/"
SOURCE_URL = "https://www.bkfc.com"
OUTPUT_FILE = "BKFC_Events.ics"


def get_local_timezone() -> ZoneInfo:
    """Auto-detect the system's local timezone."""
    try:
        import subprocess
        result = subprocess.run(
            ["timedatectl", "show", "--property=Timezone", "--value"],
            capture_output=True, text=True
        )
        tz_name = result.stdout.strip()
        if tz_name:
            print(f"  ✅ Timezone detected via timedatectl: {tz_name}")
            return ZoneInfo(tz_name)
    except Exception as e:
        print(f"  ⚠️  timedatectl failed: {e}")

    try:
        from tzlocal import get_localzone
        tz = get_localzone()
        print(f"  ✅ Timezone detected via tzlocal: {tz}")
        return tz
    except ImportError:
        print("  ⚠️  tzlocal not available, falling back to UTC offset map")

    offset_seconds = -time_module.timezone if time_module.daylight == 0 else -time_module.altzone
    offset_hours = offset_seconds // 3600
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
    print(f"  ℹ️  Using UTC{offset_hours:+d} → {tz_name}")
    return ZoneInfo(tz_name)


def fetch_page(url: str) -> BeautifulSoup:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    print(f"  GET {url}")
    response = requests.get(url, headers=headers, timeout=15)
    print(f"  HTTP {response.status_code} ({len(response.text)} chars)")
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_events(soup: BeautifulSoup) -> list[dict]:
    events = []

    # Dump a sample of raw text to help debug parsing issues
    raw_text = soup.get_text(" ", strip=True)
    print(f"\n--- RAW TEXT SAMPLE (first 1000 chars) ---")
    print(raw_text[:1000])
    print(f"--- END SAMPLE ---\n")

    # Strategy 1: find <a href="/events/..."> blocks with an h2/h3 title
    event_blocks = soup.find_all("a", href=re.compile(r"^/events/"))
    print(f"  Found {len(event_blocks)} <a href=/events/...> blocks")

    seen_slugs = set()

    for i, block in enumerate(event_blocks):
        href = block.get("href", "")
        slug = href.strip("/").split("/")[-1]

        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        title_tag = block.find(["h2", "h3"])
        if not title_tag:
            print(f"  [block {i}] slug={slug} — no h2/h3 title, skipping")
            continue
        title = title_tag.get_text(strip=True)

        text = block.get_text(" ", strip=True)
        print(f"\n  [block {i}] slug={slug}")
        print(f"    title: {title}")
        print(f"    text snippet: {text[:200]}")

        # Match "March 14, 2026 3:00 PM" style dates
        dt_match = re.search(
            r"(\w+ \d{1,2},\s*\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)", text
        )
        if not dt_match:
            print(f"    ⚠️  No date/time match found — skipping")
            continue

        date_str = dt_match.group(1).strip()
        time_str = dt_match.group(2).strip()
        print(f"    date: {date_str}  time: {time_str}")

        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        except ValueError as e:
            print(f"    ⚠️  Date parse error: {e} — skipping")
            continue

        # Location heuristic
        location = ""
        lines = [l.strip() for l in text.split("  ") if l.strip()]
        for j, line in enumerate(lines):
            if re.search(r"\d{4}", line) and j + 1 < len(lines):
                candidate = lines[j + 1]
                if re.search(r"[-,]", candidate) and len(candidate) < 100:
                    location = candidate
                    break
        print(f"    location: {location or '(none found)'}")

        events.append({
            "title": title,
            "datetime": dt,
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
    print("🌍 Detecting local timezone ...")
    local_tz = get_local_timezone()
    print(f"   Timezone: {local_tz}\n")

    print(f"📡 Fetching events from {BKFC_EVENTS_URL} ...")
    try:
        soup = fetch_page(BKFC_EVENTS_URL)
    except Exception as e:
        print(f"❌ Failed to fetch page: {e}")
        sys.exit(1)

    print("\n🔍 Parsing events ...")
    events = parse_events(soup)
    print(f"\n   Parsed {len(events)} events.")

    if not events:
        print("❌ No events found — see debug output above for clues.")
        sys.exit(1)

    print("\n📅 Events found:")
    for e in events:
        local_dt = e["datetime"].astimezone(local_tz)
        print(f"  • {local_dt.strftime('%b %d, %Y %I:%M %p %Z')}  |  {e['title']}")

    ics_bytes = build_ics(events, local_tz)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(ics_bytes)

    print(f"\n✅ Calendar saved to {OUTPUT_FILE} (times in {local_tz})")


if __name__ == "__main__":
    main()

