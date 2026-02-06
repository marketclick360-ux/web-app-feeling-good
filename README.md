# Feeling Good - App Hub

A multi-app wellness platform hosted on Cloudflare Pages (free).

## Apps

| App | Path | Description |
|-----|------|-------------|
| Hub (Home) | `/` | Landing page linking to all apps |
| Pioneer Tracker | `/pioneer/` | Spiritual growth tracking and meeting prep |
| Wellness App | `/wellness/` | Third app (placeholder) |

## Project Structure

```
web-app-feeling-good/
|-- index.html          <- Hub landing page
|-- pioneer/
|   |-- index.html      <- Pioneer Spiritual Growth Tracker
|-- wellness/
|   |-- index.html      <- Third app
|-- README.md
|-- .gitignore
```

## Deploy to Cloudflare Pages (Free)

1. Go to Cloudflare > Workers & Pages > Pages
2. Connect this GitHub repo
3. Build command: (leave blank)
4. Output directory: `/`
5. Deploy!

Each push to `main` auto-deploys all apps.

## How to Add Your App Code

1. Download your app as HTML from Perplexity ("Download as HTML" button)
2. Rename the file to `index.html`
3. Go to the matching folder in this repo (e.g. `pioneer/`)
4. Click the existing `index.html` > Edit > Select all > Paste your HTML > Commit

Done! Cloudflare will auto-deploy within 1-2 minutes.
