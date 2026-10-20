"""Capture the owned website's illustrative product panels, without calling app APIs.

Maintenance-only: requires Playwright and Chromium; generated PNGs are committed for CI.
Usage: python tools/capture_linkedin_assets.py --browser /path/to/chrome
"""
import argparse
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    website = root.parent / 'Interview-Sarthi'
    destination = root / 'assets/brand'

    def local(route):
        url = urlsplit(route.request.url)
        path = (website / unquote(url.path).lstrip('/')).resolve()
        if url.hostname != 'sarthi.local' or not path.is_relative_to(website.resolve()):
            return route.abort()
        if path.is_dir():
            path /= 'index.html'
        if path.is_file():
            route.fulfill(body=path.read_bytes(), content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
        else:
            route.fulfill(status=404, body='Not found')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **({'executable_path': args.browser} if args.browser else {}))
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=2,
                                      reduced_motion='reduce')
        context.route('**/*', local)
        page = context.new_page()
        page.goto('http://sarthi.local/apply/', wait_until='networkidle')
        for step in ('match', 'fill'):
            page.locator('#tab-' + step).click()
            page.locator('.product-visual').screenshot(path=str(destination / f'linkedin-apply-{step}.png'))
        page.goto('http://sarthi.local/prep/', wait_until='networkidle')
        page.locator('.call').first.screenshot(path=str(destination / 'linkedin-prep-preview.png'))
        browser.close()
    print('Captured three labelled website product illustrations.')


if __name__ == '__main__':
    main()
