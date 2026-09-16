import json, os, asyncio
from twscrape import API
from playwright.async_api import async_playwright

STATE_FILE = "posted.json"

def load_posted():
    if os.path.exists(STATE_FILE):
        return set(json.load(open(STATE_FILE)))
    return set()

def save_posted(ids):
    json.dump(list(ids), open(STATE_FILE, "w"))

async def get_new_tweets(source_account, posted):
    api = API()
    await api.pool.login_all()
    tweets = []
    async for t in api.user_tweets(source_account, limit=10):
        if str(t.id) not in posted:
            tweets.append(t)
    return tweets

async def post_tweet(page, text):
    await page.goto("https://x.com/compose/post")
    await page.fill('div[aria-label="Post text"]', text)
    await page.click('button[data-testid="tweetButtonInline"]')

async def main():
    posted = load_posted()
    new_tweets = await get_new_tweets(os.environ["SOURCE_ACCOUNT"], posted)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://x.com/login")
        await page.fill('input[name="text"]', os.environ["X_USERNAME"])
        await page.click('text=Next')
        await page.fill('input[name="password"]', os.environ["X_PASSWORD"])
        await page.click('text=Log in')
        await page.wait_for_timeout(3000)

        for t in new_tweets:
            await post_tweet(page, t.rawContent)
            posted.add(str(t.id))
            await page.wait_for_timeout(2000)

        await browser.close()

    save_posted(posted)

asyncio.run(main())
