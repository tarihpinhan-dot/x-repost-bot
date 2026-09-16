import json, os, asyncio
from playwright.async_api import async_playwright

STATE_FILE = "posted.json"

def load_posted():
    if os.path.exists(STATE_FILE):
        return set(json.load(open(STATE_FILE)))
    return set()

def save_posted(ids):
    json.dump(list(ids), open(STATE_FILE, "w"))

async def main():
    posted = load_posted()
    cookies = json.loads(os.environ["X_COOKIES"])
    source_account = os.environ["SOURCE_ACCOUNT"]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()

        await page.goto(f"https://x.com/{source_account}")
        await page.wait_for_timeout(5000)

        tweet_elements = await page.locator('article[data-testid="tweet"]').all()
        new_tweets = []
        for el in tweet_elements[:5]:
            try:
                text = await el.locator('div[data-testid="tweetText"]').inner_text()
                href = await el.locator('a[href*="/status/"]').first.get_attribute('href')
                tweet_id = href.split('/status/')[-1].split('?')[0]
                if tweet_id not in posted:
                    new_tweets.append((tweet_id, text))
            except Exception:
                continue

        for tweet_id, text in reversed(new_tweets):
            await page.goto("https://x.com/compose/post")
            await page.wait_for_timeout(2000)
            await page.fill('div[aria-label="Post text"]', text)
            await page.click('button[data-testid="tweetButtonInline"]')
            await page.wait_for_timeout(3000)
            posted.add(tweet_id)

        await browser.close()

    save_posted(posted)

asyncio.run(main())
