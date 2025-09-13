# Helper to run both vintage and overall lookups with the same UA/context
from app import config
from app import vivino

async def fetch_vivino_info(browser, title: str):
    # Split vintage year
    import re
    year_match = re.search(r'\b(19|20)\d{2}\b', title)
    vint_query = title
    all_query = re.sub(r'\b(19|20)\d{2}\b','', title).strip() if year_match else title

    ctx = await browser.new_context(user_agent=config.USER_AGENT, locale="en-US")
    page = await ctx.new_page()
    vintage = await vivino.lookup(page, vint_query)
    overall = None
    if all_query != vint_query:
        overall = await vivino.lookup(page, all_query)
    await ctx.close()
    return vintage, overall

