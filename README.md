# BKFC Calendar

Automatically scrapes upcoming events from [bkfc.com/events](https://www.bkfc.com/events) and generates a `.ics` calendar file, updated every Monday via GitHub Actions.

Each event description includes start times for all US timezones — no setup required.

## Subscribe on iPhone

1. Go to **Settings > Calendar > Accounts > Add Account > Other > Add Subscribed Calendar**
2. Enter the raw URL:
   ```
   https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/BKFC_Events.ics
   ```
3. Tap **Next** > **Save**

## What You'll See

Each calendar event includes:
```
Start Times:
  ET: 7:00 PM EDT
  CT: 6:00 PM CDT
  MT: 5:00 PM MDT
  PT: 4:00 PM PDT

How to Watch: BKFC+ -- https://watch.bkfc.com/
Event Info: https://www.bkfc.com/events/...

Source: https://www.bkfc.com
```

## Run Locally

```bash
pip install -r requirements.txt
python scrape.py
```

## Files

| File | Description |
|------|-------------|
| `scrape.py` | The scraper script |
| `BKFC_Events.ics` | The generated calendar file (auto-updated) |
| `requirements.txt` | Python dependencies |
| `.github/workflows/update-calendar.yml` | GitHub Actions workflow |
