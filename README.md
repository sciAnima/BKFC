# BKFC Calendar

Automatically scrapes upcoming events from [bkfc.com/events](https://www.bkfc.com/events) and generates a `.ics` calendar file, updated weekly via GitHub Actions.

## Subscribe on iPhone

1. Go to **Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar**
2. Enter the raw URL of `BKFC_Events.ics` from this repo:
   ```
   https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/BKFC_Events.ics
   ```
3. Tap **Next** → **Save**

Your iPhone will now automatically sync BKFC events to your calendar!

## Run Locally

```bash
pip install -r requirements.txt
python scrape.py
```

## How It Works

- **`scrape.py`** fetches the BKFC events page, parses event titles, dates, times, and locations, and writes a standards-compliant `.ics` file.
- **GitHub Actions** runs the scraper every Monday at 6 AM UTC and commits any changes automatically.
- You can also trigger a manual run from the **Actions** tab in GitHub.

## Files

| File | Description |
|------|-------------|
| `scrape.py` | The scraper script |
| `BKFC_Events.ics` | The generated calendar file (auto-updated) |
| `requirements.txt` | Python dependencies |
| `.github/workflows/update-calendar.yml` | GitHub Actions workflow |
