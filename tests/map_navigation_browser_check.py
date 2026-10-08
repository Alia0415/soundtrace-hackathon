"""Verify desktop map navigation scrolls away while mobile navigation stays docked."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime/test-deps'))
from playwright.sync_api import sync_playwright

shots = ROOT / 'docs/previews/map-navigation-fix'
shots.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    for route in ['/map', '/demo/map']:
        for width, height in [(1440, 900), (1024, 768), (800, 650)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.goto('http://127.0.0.1:8093' + route, wait_until='networkidle')
            nav = page.locator('.st-dock')
            assert nav.locator('a').count() == 4
            initial = nav.bounding_box()
            header = page.locator('.doodle-header').bounding_box()
            assert initial['y'] >= header['y']
            assert initial['y'] + initial['height'] <= header['y'] + header['height']
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.evaluate("scrollTo({top:360,behavior:'instant'})")
            scroll = page.evaluate('scrollY')
            after = nav.bounding_box()
            assert scroll > 0
            assert abs(after['y'] - (initial['y'] - scroll)) < 1, (route, width, after)
            header_after = page.locator('.doodle-header').bounding_box()
            assert after['y'] + after['height'] <= header_after['y'] + header_after['height']
            if scroll > initial['y'] + initial['height']:
                assert after['y'] + after['height'] < 0
            account = page.locator('.st-account-button').bounding_box()
            assert account['y'] + account['height'] <= header_after['y'] + header_after['height']
            # The map is interactive directly under the former header overlay.
            map_top = page.locator('#mapWrap').bounding_box()['y']
            assert not nav.evaluate("(e,y)=>e.contains(document.elementFromPoint(innerWidth/2,y))", max(40,map_top+20))
            assert page.locator('#mapWrap').evaluate("e=>e.contains(document.elementFromPoint(innerWidth/2,Math.max(40,e.getBoundingClientRect().top+20)))")
            if route == '/demo/map' and width == 1440:
                page.screenshot(path=str(shots / 'after-desktop.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.goto('http://127.0.0.1:8093' + route, wait_until='networkidle')
        nav = page.locator('.st-dock')
        assert nav.evaluate("e=>getComputedStyle(e).position") == 'fixed'
        initial = nav.bounding_box()
        page.evaluate("scrollTo({top:250,behavior:'instant'})")
        after = nav.bounding_box()
        assert abs(after['y'] - initial['y']) < 1
        assert abs(after['y'] + after['height'] - 844) < 1
        assert not page.locator('body').evaluate("e=>e.scrollWidth>innerWidth")
    assert not errors, errors
    browser.close()
print('PASS: formal/demo desktop header scrolls away at 1440/1024/800; map unobstructed; mobile bottom navigation preserved; no page errors')
