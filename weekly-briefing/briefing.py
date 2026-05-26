#!/usr/bin/env python3
"""
Weekly AI Briefing Pipeline
Usage: python briefing.py [--links urls.txt] [--output briefing.md]
Env:   ANTHROPIC_API_KEY=your-key
"""
import argparse, os, sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"), override=True)
import anthropic, feedparser, httpx

DEFAULT_FEEDS = [
    "https://towardsdatascience.com/feed",
    "https://machinelearningmastery.com/blog/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

def fetch_rss(feed_urls, max_per_feed=5):
    articles = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                articles.append({"title": entry.get("title", "Untitled"),
                                  "url": entry.get("link", ""),
                                  "summary": entry.get("summary", "")[:300],
                                  "source": feed.feed.get("title", url)})
            print(f"  + {feed.feed.get('title', url)}")
        except Exception as e:
            print(f"  x {url}: {e}")
    return articles

def load_links(path):
    articles = []
    with open(path) as f:
        for line in f:
            url = line.strip()
            if url and not url.startswith("#"):
                articles.append({"title": url, "url": url, "summary": "", "source": "custom"})
    return articles

def generate(articles, client):
    article_list = "\n".join(
        f"{i}. **{a['title']}** ({a['source']})\n   URL: {a['url']}\n   Preview: {a['summary'][:200]}"
        for i, a in enumerate(articles, 1)
    )
    prompt = dedent(f"""
    You are producing a weekly AI and technology briefing from {len(articles)} articles.

    1. Group them into 3-6 thematic categories based on the core problem each addresses.
    2. For each group, write 2-4 KEY INSIGHTS (specific numbers, named companies, concrete outcomes).
    3. End with "What to do this week": 3 concrete, specific actions.

    Use Markdown headers. Flag anything risky with a warning note. Preserve specific numbers.

    Articles:
    {article_list}
    """).strip()
    return client.messages.create(
        model="claude-sonnet-4-6", max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    ).content[0].text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--links")
    parser.add_argument("--output")
    parser.add_argument("--max-articles", type=int, default=20)
    args = parser.parse_args()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key: print("Set ANTHROPIC_API_KEY"); sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    print(f"\nWeekly AI Briefing — {datetime.now().strftime('%B %d, %Y')}")
    articles = load_links(args.links) if args.links else fetch_rss(DEFAULT_FEEDS)
    articles = articles[:args.max_articles]
    print(f"\n-> Generating from {len(articles)} articles...")
    briefing = generate(articles, client)
    header = f"# Weekly AI Briefing\n**{datetime.now().strftime('%A, %B %d, %Y')}** | {len(articles)} articles\n\n---\n\n"
    output = header + briefing
    if args.output:
        Path(args.output).write_text(output)
        print(f"\nSaved to: {args.output}")
    else:
        print("\n" + output)

if __name__ == "__main__":
    main()
