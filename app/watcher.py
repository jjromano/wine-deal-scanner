import asyncio, random, re
from playwright.async_api import async_playwright
from app import config
from app.domutils import extract_from_cta
from app.notify import telegram_send
from app.vivino_client import fetch_vivino_info
from app.models import Deal, DealDetails, EnrichedDeal
from app.enrichment import enrich_deal

def _deal_id(title: str) -> str:
    return (title or "").strip().lower()

async def run_watcher():
    print(f"[watcher] flags DEBUG={config.DEBUG} SAFE_MODE={config.SAFE_MODE} HEADFUL={config.HEADFUL}")
    
    # Don't use async context manager to avoid premature browser closure
    p = await async_playwright().start()
    try:
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

        # Skip MutationObserver for now to debug the issue
        # async def _on_deal_change(source, payload):
        #     try:
        #         title = (payload or {}).get("title") or ""
        #         price_text = (payload or {}).get("priceText") or ""
        #         price = None
        #         m = re.search(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)", price_text)
        #         if m:
        #             try: price = float(m.group(1).replace(",", ""))
        #             except: pass
        #         if config.is_generic_title(title):
        #             if config.DEBUG: print(f"[mo] (skip generic) {title!r}")
        #             return
        #         if price is not None and price < 5.0:
        #             price = None
        #         page._last_mo = {"title": title, "price": price}
        #         if config.DEBUG: print(f"[mo] change title={title!r} price={price}")
        #     except Exception as e:
        #         print("[mo] error:", e)

        # await page.expose_binding("pyDealChanged", _on_deal_change)

        # Skip MutationObserver for now to debug the issue
        pass

        # Fallback: small poll that prefers MO cache
        last_id = None
        
        async def get_dom_deal():
            # Skip MutationObserver cache for now
            # if getattr(page, "_last_mo", None):
            #     d = page._last_mo
            #     return d.get("title") or "", d.get("price")
            try:
                title, price = await extract_from_cta(page)
                return title, price
            except Exception as e:
                if config.DEBUG: print("[poll] error", e)
                return "", None

        while True:
            try:
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
                if config.DEBUG:
                    print(f"[deal_id] current='{nid}' last='{last_id}'")
                
                if not nid:
                    if config.DEBUG: print("[deal_id] skipping - no valid deal ID")
                    continue
                if nid == last_id:
                    if config.DEBUG: print("[deal_id] skipping - same deal as last time")
                    continue  # Same deal, no need to send notification
                
                if config.DEBUG: print(f"[deal_id] NEW DEAL DETECTED! '{nid}' != '{last_id}'")
                last_id = nid

                deal = Deal(title=title.strip(), price=(price or 0.0), bottle_size_ml=750, url=config.LASTBOTTLE_URL)
                if config.DEBUG:
                    print(f"[event] deal_changed id='{nid}' title='{deal.title}' price=${deal.price:.2f}")

                # Keep Vivino call; we're focusing on flips
                try:
                    vintage, overall, vintage_year = await fetch_vivino_info(browser, deal.title, existing_page=page)
                except Exception as e:
                    if config.DEBUG: print("[vivino.debug] error:", e)
                    vintage, overall, vintage_year = (None, None, None)

                await telegram_send(deal, (vintage, overall, vintage_year))
                
            except Exception as e:
                print(f"[watcher] ERROR in main loop: {e}")
                print(f"[watcher] Error type: {type(e)}")
                import traceback
                traceback.print_exc()
                # Continue the loop even if there's an error
                continue
            
    finally:
        # Clean up manually
        try:
            await browser.close()
        except:
            pass
        try:
            await p.stop()
        except:
            pass


# Backward compatibility classes/functions for tests
class DealWatcher:
    """Backward compatibility class for tests."""
    
    def __init__(self):
        self.last_deals = {}
    
    async def _process_deal_details(self, deal_details: DealDetails, source: str = "test"):
        """Process deal details with enrichment and notification."""
        try:
            # Enrich the deal
            enriched_deal = await enrich_deal(deal_details)
            
            # Send notification
            await send_telegram_message(enriched_deal)
            
            # Store for deduplication
            from app.extract import deal_key
            key = deal_key(deal_details.wine_name, deal_details.vintage, deal_details.deal_price)
            self.last_deals[key] = enriched_deal
            
        except Exception as e:
            if config.DEBUG:
                print(f"[watcher] process_deal_details error: {e}")


async def send_telegram_message(enriched_deal: EnrichedDeal) -> bool:
    """Send Telegram message for enriched deal."""
    try:
        # Convert EnrichedDeal to Deal format for current telegram_send
        deal = Deal(
            title=enriched_deal.wine_name,
            price=enriched_deal.deal_price,
            bottle_size_ml=enriched_deal.bottle_size_ml,
            vintage=str(enriched_deal.vintage) if enriched_deal.vintage else None,
            url=config.LASTBOTTLE_URL
        )
        
        # Create vivino data tuple
        vintage_data = (
            enriched_deal.vintage_rating,
            enriched_deal.vintage_reviews, 
            enriched_deal.vintage_price,
            None  # URL not available in EnrichedDeal
        )
        
        overall_data = (
            enriched_deal.overall_rating,
            enriched_deal.overall_reviews,
            enriched_deal.overall_price, 
            None  # URL not available in EnrichedDeal
        )
        
        await telegram_send(deal, (vintage_data, overall_data))
        return True
        
    except Exception as e:
        if config.DEBUG:
            print(f"[watcher] send_telegram_message error: {e}")
        return False