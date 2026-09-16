import json, os, asyncio
from playwright.async_api import async_playwright

STATE_FILE = "posted.json"

def load_posted():
    if os.path.exists(STATE_FILE):
        return set(json.load(open(STATE_FILE)))
    return set()

def save_posted(ids):
    json.dump(list(ids), open(STATE_FILE, "w"))

def normalize_cookies(cookies):
    mapping = {
        "no_restriction": "None",
        "unspecified": "Lax",
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }
    fixed = []
    for c in cookies:
        c = dict(c)
        same_site = c.get("sameSite", "Lax")
        c["sameSite"] = mapping.get(str(same_site).lower(), "Lax")
        allowed_keys = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
        c = {k: v for k, v in c.items() if k in allowed_keys}
        if "expires" not in c or c["expires"] is None:
            c["expires"] = -1
        fixed.append(c)
    return fixed

async def main():
    posted = load_posted()
    raw_cookies = json.loads(os.environ["X_COOKIES"])
    cookies = normalize_cookies(raw_cookies)
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
