"""
Pulls recent Reddit posts mentioning each tracked asset from a small set
of relevant subreddits. Requires a free Reddit API app (script type) —
create one at https://www.reddit.com/prefs/apps and set the client id/
secret in .env. Free tier is rate-limited (roughly 100 queries/min) which
is plenty for a 10-minute ingestion cycle over ~10 assets.
"""
import praw
from app.config import settings


def _get_reddit_client():
    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
        return None
    return praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent=settings.REDDIT_USER_AGENT,
    )


def fetch_reddit_mentions() -> list[dict]:
    reddit = _get_reddit_client()
    if reddit is None:
        print("[reddit] no credentials set, skipping")
        return []

    results = []
    asset_groups = [
        (settings.STOCK_SYMBOLS, settings.STOCK_SUBREDDITS),
        (settings.CRYPTO_SYMBOLS, settings.CRYPTO_SUBREDDITS),
    ]

    for symbols, subreddits in asset_groups:
        for sub_name in subreddits:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.new(limit=50):
                    haystack = f"{post.title} {getattr(post, 'selftext', '')}".lower()
                    for symbol in symbols:
                        if symbol.lower() in haystack:
                            results.append({
                                "symbol": symbol,
                                "source": "reddit",
                                "text": post.title,
                                "url": f"https://reddit.com{post.permalink}",
                            })
            except Exception as e:
                print(f"[reddit] failed on r/{sub_name}: {e}")
                continue
    return results
