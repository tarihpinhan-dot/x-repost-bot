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
    print(f"Kaynak hesap: {source_account}")
    print(f"Daha önce paylaşılan tweet sayısı: {len(posted)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()

        await page.goto(f"https://x.com/{source_account}", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        try:
            await page.wait_for_selector('article', timeout=15000)
        except Exception as e:
            print(f"article elementi bulunamadı: {e}")

        await page.screenshot(path="debug.png", full_page=True)
        current_url = page.url
        print(f"Şu anki URL: {current_url}")

        if "login" in current_url:
            print("HATA: Cookie ile giriş yapılamadı, login sayfasına yönlendirildi.")
        else:
            print("Giriş başarılı görünüyor, sayfa yüklendi.")

        tweet_elements = await page.locator('article[data-testid="tweet"]').all()
        print(f"Sayfada bulunan tweet elementi sayısı: {len(tweet_elements)}")

        new_tweets = []
        for el in tweet_elements[:5]:
            try:
                text = await el.locator('div[data-testid="tweetText"]').inner_text()
                href = await el.locator('a[href*="/status/"]').first.get_attribute('href')
                tweet_id = href.split('/status/')[-1].split('?')[0]
                if tweet_id not in posted:
                    new_tweets.append((tweet_id, text))
            except Exception as e:
                print(f"Tweet okunamadı, atlanıyor: {e}")
                continue

        print(f"Yeni bulunan tweet sayısı: {len(new_tweets)}")

        for tweet_id, text in reversed(new_tweets):
            print(f"Paylaşılıyor: {tweet_id} -> {text[:50]}")
            await page.goto("https://x.com/compose/post")
            await page.wait_for_timeout(2000)
            await page.fill('div[aria-label="Post text"]', text)
            await page.click('button[data-testid="tweetButtonInline"]')
            await page.wait_for_timeout(3000)
            posted.add(tweet_id)

        await browser.close()

    save_posted(posted)

asyncio.run(main())
