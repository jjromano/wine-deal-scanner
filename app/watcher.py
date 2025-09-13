import asyncio, random, re
from playwright.async_api import async_playwright
from app import config
from app.domutils import extract_from_cta
from app.notify import telegram_send
from app.vivino_client import fetch_vivino_info
from app.models import Deal

def _deal_id(title: str) -> str:
    return (title or "").strip().lower()

async def run_watcher():
    print(f"[watcher] flags DEBUG={config.DEBUG} SAFE_MODE={config.SAFE_MODE} HEADFUL={config.HEADFUL}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not config.HEADFUL)
        # MAKE SURE we pass the forced UA
        ctx = await browser.new_context(user_agent=config.USER_AGENT, locale="en-US")
        # Minor stealth
        await ctx.add_init_script("""
          Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
          Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
          Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
        """)
        page = await ctx.new_page()
        print("[watcher] request blocking DISABLED (MVP)")
        await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded")

        # Python binding the page calls when the DOM changes
        async def _on_deal_change(source, payload):
            try:
                title = (payload or {}).get("title") or ""
                price_text = (payload or {}).get("priceText") or ""
                price = None
                m = re.search(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)", price_text)
                if m:
                    try: price = float(m.group(1).replace(",", ""))
                    except: pass
                if config.is_generic_title(title):
                    if config.DEBUG: print(f"[mo] (skip generic) {title!r}")
                    return
                if price is not None and price < 5.0:
                    price = None
                page._last_mo = {"title": title, "price": price}
                if config.DEBUG: print(f"[mo] change title={title!r} price={price}")
            except Exception as e:
                print("[mo] error:", e)

        await page.expose_binding("pyDealChanged", _on_deal_change)

        # Install MutationObserver on the WHOLE BODY and re-find the deal each time
        await page.add_init_script("""
        (() => {
          if (window.__lb_mo_installed) return;
          window.__lb_mo_installed = true;

          function moneyText(root){
            const t = (root?.innerText || root?.textContent || "");
            const cleaned = t.replace(/you save.*?\\$[\\d.,]+/ig,'');
            const m = cleaned.match(/\\$\\s*\\d[\\d,]*(?:\\.\\d{2})?/);
            return m ? m[0] : null;
          }
          function getRoot(){
            const btns = Array.from(document.querySelectorAll('button, input[type="submit"]'));
            const btn  = btns.find(b => /add to cart|buy|purchase|add to bag/i.test((b.innerText||b.value||''))) || null;
            return (btn && (btn.closest('form, .product, .product-detail, .deal, .product-container, main, #content, .container'))) || document.body;
          }
          function getTitle(root){
            const sels = ['.product-title','.deal-title','h1.product-title','h1.title','h1','h2'];
            for (const s of sels) {
              const el = root.querySelector(s);
              if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
            }
            return (document.title || '').trim();
          }
          function getPrice(root){
            const sels = ['.last-bottle-price','.deal-price','.price .current','.our-price','.price','[data-price]','[data-lb-price]'];
            for (const s of sels) {
              const el = root.querySelector(s);
              const mt = moneyText(el);
              if (mt) return mt;
            }
            return moneyText(root);
          }

          let lastTitle = "";
          let lastPrice = "";

          function push(){
            const root  = getRoot();
            const title = getTitle(root);
            const price = getPrice(root);
            if (title !== lastTitle || price !== lastPrice) {
              lastTitle = title; lastPrice = price;
              try { window.pyDealChanged({title, priceText: price}); } catch(_) {}
            }
          }

          Promise.resolve().then(push); // initial push
          const obs = new MutationObserver(() => { push(); });
          obs.observe(document.body, {subtree:true, childList:true, characterData:true, attributes:true});
          addEventListener('popstate', push, {passive:true});
        })();
        """)

        # Fallback: small poll that prefers MO cache
        last_id = None
        async def get_dom_deal():
            if getattr(page, "_last_mo", None):
                d = page._last_mo
                return d.get("title") or "", d.get("price")
            try:
                title, price = await extract_from_cta(page)
                return title, price
            except Exception as e:
                if config.DEBUG: print("[poll] error", e)
                return "", None

        while True:
            await asyncio.sleep(0.6 + random.random()*0.2)
            title, price = await get_dom_deal()
            if not title or config.is_generic_title(title):
                if config.DEBUG and title: print(f"[dom.peek] (generic) {title!r}")
                continue
            if price is not None and price < 5.0:
                price = None

            if config.DEBUG:
                print(f"[dom.peek] title={title!r} price={price}")

            nid = _deal_id(title)
            if not nid or nid == last_id:
                continue
            last_id = nid

            deal = Deal(title=title.strip(), price=(price or 0.0), bottle_size_ml=750, url=config.LASTBOTTLE_URL)
            if config.DEBUG:
                print(f"[event] deal_changed id='{nid}' title='{deal.title}' price=${deal.price:.2f}")

            # Keep Vivino call; we're focusing on flips
            try:
                vintage, overall = await fetch_vivino_info(browser, deal.title)
            except Exception as e:
                if config.DEBUG: print("[vivino.debug] error:", e)
                vintage, overall = (None, None)

            await telegram_send(deal, (vintage, overall))