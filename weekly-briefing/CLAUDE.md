# Weekly AI Briefing System

## What this project does
Automated pipeline that collects recent AI and technology articles, groups them
by theme, and produces a formatted briefing with key insights and action items.
Designed to run weekly (or on-demand) and output a clean Markdown file.

## How to run

```bash
# From RSS feeds (default sources)
python briefing.py

# From a custom URL list
python briefing.py --links my-links.txt

# Save to file
python briefing.py --output ~/Desktop/briefing-$(date +%Y-%m-%d).md

# Specific feeds
python briefing.py --feeds https://towardsdatascience.com/feed https://venturebeat.com/category/ai/feed/
```

## Adding your own sources

Edit `DEFAULT_FEEDS` in briefing.py to add or remove RSS feeds.

For one-off link lists, create a plain text file with one URL per line:
```
# My weekly reading list
https://example.com/article-1
https://example.com/article-2
```
Then run: `python briefing.py --links my-list.txt`

## Scheduling (macOS)

Add to crontab (`crontab -e`) — runs every Monday at 7am:
```
0 7 * * 1 cd /path/to/weekly-briefing && ANTHROPIC_API_KEY=your-key python briefing.py --output ~/Desktop/briefing.md
```

## Requirements

```bash
pip install anthropic feedparser httpx
export ANTHROPIC_API_KEY=your-key
```

## Output format

The briefing is Markdown with:
- Grouped themes (3–6 categories)
- 2–4 insight bullets per group with specific numbers preserved
- ⚠️ flags on anything risk-related
- "What to do this week" action section at the end

## Files in this project

- `briefing.py` — main pipeline script
- `CLAUDE.md` — this file (project context for Claude Code)
- `urls.txt.example` — example link file format

## What Claude should do if asked to modify this

- Run the script to test before changing output format
- Keep the DEFAULT_FEEDS list clean and commented
- Don't change the Anthropic API call parameters without testing
- The `--links` flag is the most-used — protect that interface
