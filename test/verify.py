"""Browser check: main screen in gu/hi/en and every details tab; mobile screenshots; JS errors; saves the rendered text
of every view to shots/rendered_*.txt for test/wordcheck.py. Usage: python3 test/verify.py <base-url> [out-dir]"""
import sys, json, asyncio
from playwright.async_api import async_playwright
BASE = sys.argv[1]; OUT = sys.argv[2] if len(sys.argv) > 2 else "shots"
TABS = ["cond", "val", "trend", "macro", "log", "sources"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        errs = []
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, timezone_id="Asia/Kolkata")
        pg = await ctx.new_page(); pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e))); pg.on("console", lambda m: m.type == "error" and errs.append("console: " + m.text))
        await pg.goto(BASE, wait_until="networkidle"); await pg.evaluate("localStorage.clear()"); await pg.reload(wait_until="networkidle"); await pg.wait_for_timeout(1500)
        for lang in ("gu", "hi", "en"):
            await pg.click(f"#langs button[data-l={lang}]"); await pg.wait_for_timeout(300)
            txt = await pg.evaluate("document.getElementById('simple').innerText")
            open(f"{OUT}/rendered_main_{lang}.txt", "w").write(txt)
            print(f"MAIN {lang}: {txt[:900]!r}")
            await pg.screenshot(path=f"{OUT}/main_{lang}_mobile.png", full_page=True)
        wa = await pg.evaluate("(()=>{let u=null;window.open=(x)=>{u=x};document.getElementById('wa-btn').click();return decodeURIComponent(u)})()")
        print("WA:", wa)
        await pg.click("#langs button[data-l=gu]")
        await pg.goto(BASE + "#details", wait_until="networkidle"); await pg.wait_for_timeout(1000)
        alltxt = []
        for t in TABS:
            await pg.click(f".tab[data-s={t}]"); await pg.wait_for_timeout(250)
            txt = await pg.evaluate(f"document.getElementById('s-{t}').innerText")
            print(f"tab {t}: {len(txt)} chars; warn={'Could not render' in txt}")
            if "Could not render" in txt:
                errs.append(f"tab {t}: {txt[:200]}")
            alltxt.append(txt if t != "sources" else txt.split("Headlines (context only")[0])
            await pg.screenshot(path=f"{OUT}/details_{t}_mobile.png", full_page=True)
        open(f"{OUT}/rendered_details_en.txt", "w").write("\n".join(alltxt) + "\n" + await pg.evaluate("document.querySelector('header').innerText"))
        await b.close()
        print("ERRORS:", errs or "none")
        if errs:
            sys.exit(1)

asyncio.run(main())
