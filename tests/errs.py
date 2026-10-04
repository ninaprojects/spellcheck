import os
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
with sync_playwright() as pw:
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    row.get_by_text('Add location').click(); pg.wait_for_selector('#sessionsList .loc-item')
    row.locator('.loc-item').first.click(); pg.wait_for_timeout(500)
    for t in ['coven','journey','receipts','today']:
        pg.click(f'.tabbar .tab[data-tab={t}]'); pg.wait_for_timeout(300)
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(300)
    errs=[x for x in e.errors if 'ServiceWorker' not in x]
    print('unexpected errors:', errs)
    e.close()
