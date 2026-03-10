#!/usr/bin/env python3
"""
BKFC Event Scraper
Scrapes upcoming events from bkfc.com and generates a .ics calendar file.
Event times are stored in ET and listed in ET / CT / PT in the description.
"""

import re
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event


BKFC_EVENTS_URL = "https://www.bkfc.com/events"
WATCH_URL = "https://watch.bkfc.com/"
SOURCE_URL = "https://www.bkfc.com"
OUTPUT_FILE = "BKFC_Events.ics"

TZ_ET = ZoneInfo("America/New_York")
TZ_CT = ZoneInfo("America/Chicago")
TZ_MT = ZoneInfo("America/Denver")
TZ_PT = ZoneInfo("America/Los_Angeles")


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
    seen_slugs = set()

    title_links = soup.find_all("a", href=re.compile(r"^/events/"))
    print(f"  Found {len(title_links)} /events/ links")

    for link in title_links:
        title_tag = link.find(["h2", "h3"])
        if not title_tag:
            continue

        href = link.get("href", "")
        slug = href.strip("/").split("/")[-1]
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        title = title_tag.get_text(strip=True)

        # Walk up the DOM to find an ancestor that contains the date/time
        container = link
        date_text = ""
        for _ in range(6):
            container = container.parent
            if container is None:
                break
            text = container.get_text(" ", strip=True)
            if re.search(r"\w+ \d{1,2},\s*\d{4}.*\d{1,2}:\d{2}\s*[AP]M", text):
                date_text = text
                break

        if not date_text:
            print(f"  [{slug}] no date found in parent containers - skipping")
            continue

        dt_match = re.search(
            r"(\w+ \d{1,2},\s*\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)", date_text
        )
        if not dt_match:
            print(f"  [{slug}] date regex did not match - skipping")
            continue

        date_str = dt_match.group(1).strip()
        time_str = dt_match.group(2).strip()

        try:
            # BKFC publishes times in ET (Eastern Time), not UTC
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
            dt = dt.replace(tzinfo=TZ_ET)
        except ValueError as e:
            print(f"  [{slug}] date parse error: {e} - skipping")
            continue

        # Location: prefer ALL-CAPS lines with a dash or comma
        location = ""
        for line in date_text.splitlines():
            line = line.strip()
            if re.search(r"[-,]", line) and line.isupper() and 5 < len(line) < 100:
                location = line
                break
        if not location:
            after_date = date_text[dt_match.end():]
            for chunk in after_date.split("  "):
                chunk = chunk.strip()
                if re.search(r"[-,]", chunk) and 5 < len(chunk) < 100:
                    location = chunk
                    break

        events.append({
            "title": title,
            "datetime": dt,
            "location": location,
            "url": f"https://www.bkfc.com{href}",
            "slug": slug,
        })

    return events


def fmt(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%-I:%M %p %Z")


def build_ics(events: list[dict]) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//BKFC Events Scraper//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "BKFC Events")
    cal.add("x-wr-timezone", "America/New_York")

    for evt in events:
        # Use ET as the base time for the calendar entry
        et_dt = evt["datetime"].astimezone(TZ_ET)
        et_dt_end = et_dt + timedelta(hours=4)

        description = (
            "Start Times:\n"
            f"  ET: {fmt(evt['datetime'], TZ_ET)}\n"
            f"  CT: {fmt(evt['datetime'], TZ_CT)}\n"
            f"  MT: {fmt(evt['datetime'], TZ_MT)}\n"
            f"  PT: {fmt(evt['datetime'], TZ_PT)}\n"
            "\n"
            "How to Watch: BKFC+ -- " + WATCH_URL + "\n"
            "Event Info: " + evt["url"] + "\n"
            "\n"
            "Source: " + SOURCE_URL
        )

        vevent = Event()
        vevent.add("summary", evt["title"])
        vevent.add("dtstart", et_dt)
        vevent.add("dtend", et_dt_end)
        vevent.add("url", evt["url"])
        vevent.add("description", description)
        if evt["location"]:
            vevent.add("location", evt["location"])
        vevent["uid"] = f"{evt['slug']}@bkfc-calendar"
        cal.add_component(vevent)

    return cal.to_ical()


def main():
    print(f"Fetching events from {BKFC_EVENTS_URL} ...")
    try:
        soup = fetch_page(BKFC_EVENTS_URL)
    except Exception as e:
        print(f"ERROR: Failed to fetch page: {e}")
        sys.exit(1)

    print("\nParsing events ...")
    events = parse_events(soup)
    print(f"Parsed {len(events)} events.")

    if not events:
        print("ERROR: No events found - check if the site structure has changed.")
        sys.exit(1)

    print("\nEvents:")
    for e in events:
        print(
            f"  {fmt(e['datetime'], TZ_ET)} ET  |  "
            f"{fmt(e['datetime'], TZ_CT)} CT  |  "
            f"{fmt(e['datetime'], TZ_PT)} PT  |  "
            f"{e['title']}"
        )

    ics_bytes = build_ics(events)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(ics_bytes)

    print(f"\nCalendar saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
