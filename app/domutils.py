# Minimal CTA-scoped extraction used as a fallback when no MO signal yet.
import re

async def extract_from_cta(page):
    out = await page.evaluate("""
      () => {
        const btns = Array.from(document.querySelectorAll('button, input[type="submit"]'));
        const btn  = btns.find(b => /add to cart|buy|purchase|add to bag/i.test((b.innerText||b.value||''))) || btns[0] || null;
        const box  = btn ? (btn.closest('form, .product, .product-detail, .deal, .product-container, main, #content, .container') || document.body) : document.body;

        function getTitle(container){
          const tSel = ['.product-title','.deal-title','h1.product-title','h1.title','h1','h2'];
          for (const s of tSel) {
            const el = container.querySelector(s);
            if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
          }
          return (document.title || '').trim();
        }

        function getPrice(container){
          const money = /\\$\\s*\\d[\\d,]*(?:\\.\\d{2})?/;
          const pSel = ['.last-bottle-price','.deal-price','.price .current','.our-price','.price','[data-price]','[data-lb-price]'];
          for (const s of pSel) {
            const el = container.querySelector(s);
            if (el) {
              const txt = (el.innerText||'').replace(/you save.*?\\$[\\d.,]+/ig,'');
              const m = txt.match(money);
              if (m) return m[0];
            }
          }
          const scrub = (container.innerText||'').replace(/you save.*?\\$[\\d.,]+/ig,'');
          const m = scrub.match(money);
          return m ? m[0] : null;
        }

        const title = getTitle(box);
        const priceText = getPrice(box);
        return { title, priceText };
      }
    """)

    title = (out.get('title') or '').strip()
    price = None
    if out.get('priceText'):
        m = re.search(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)", out['priceText'])
        if m:
            try: price = float(m.group(1).replace(',', ''))
            except: pass
    return title, price