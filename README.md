# stravacookies

A small Python package for retrieving the signed cookies needed to download
high-resolution [Strava Global Heatmap](https://www.strava.com/maps/global-heatmap)
tiles in applications such as [JOSM](https://josm.openstreetmap.de) and
[Cartograph Maps](https://www.cartograph.eu).

## Installation

Python 3.9 or later and a Strava account are required:

```sh
python -m pip install "stravacookies @ git+https://github.com/solitone/stravacookies.git@v2.0.0"
python -m playwright install chromium
```

For this checkout, replace the first command with `python -m pip install .`.
On Linux, Playwright may also require `python -m playwright install --with-deps chromium`.
Alternatively, use an installed Chrome browser with `channel="chrome"`.

## Usage

The existing two-argument API is preserved:

```python
from getpass import getpass
from stravacookies import StravaCookieFetcher

fetcher = StravaCookieFetcher()
fetcher.fetchCookies(input("Strava email: "), getpass("Strava password: "))
parameters = fetcher.getCookieString()
# Treat parameters as credentials; do not log or publish them.
tms_url = (
    "tms[3,15]:https://heatmap-external-{switch:a,b,c}.strava.com/"
    "tiles-auth/run/hot/{zoom}/{x}/{y}.png?" + parameters
)
```

A visible Chromium window opens temporarily and closes after the operation.
The login follows Strava's email step, selects **Use password**, submits the
password, and retrieves the heatmap cookies. It does not opt the account into
email-code login. Browser profiles are temporary unless explicitly supplied.

**Current limitation:** Strava may return HTTP 403 for a fresh automated browser,
even with valid credentials. This was observed during live testing. In that case
use the authenticated-browser method below; changing the password is not a fix.

Optional keyword arguments:

```python
fetcher.fetchCookies(email, password, channel="chrome", timeout=60000)
# Reuse a dedicated profile to retain a login (contains sensitive session data):
fetcher.fetchCookies(email, password, user_data_dir="/private/path/strava-profile")
```

`timeout` is in milliseconds. `headless=True` is supported but Strava's browser
checks may reject it. Do not use a profile directory already open in another
browser process. The synchronous API should be called outside an asyncio event loop.

### Email codes, CAPTCHA and other interactive login

If Strava requires verification, or the account uses Google/Apple login, complete
login yourself in a Playwright browser and pass its context to the fetcher:

```python
from playwright.sync_api import sync_playwright
from stravacookies import StravaCookieFetcher

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    try:
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.strava.com/login")
        input("Complete Strava login in the browser, then press Enter here: ")
        fetcher = StravaCookieFetcher()
        fetcher.fetchCookiesFromBrowser(context)
        parameters = fetcher.getCookieString()
    finally:
        browser.close()
```

The library does not bypass verification, read your email, or accept onboarding
agreements. It does not close a browser/context supplied by the caller.

## What changed since 1.3

Strava replaced its static login form with a JavaScript-driven, multi-step flow.
`mechanize` can no longer find the password field. Version 2 uses Playwright
instead and requires Python 3.9+ and a browser installation.

After login, the library requests `https://heatmap-external-a.strava.com/auth`
to obtain `CloudFront-Key-Pair-Id`, `CloudFront-Policy` and `CloudFront-Signature`
for the legacy `heatmap-external-*.strava.com/tiles-auth/...` service. These are
still returned in the same query-string format expected by existing callers.

**Do not substitute cookies from the new maps page:** it issues a different
CloudFront policy for `content-*.strava.com/identified/...`, and that newer service
also requires an identity cookie. Those cookies do not authorize the legacy TMS
URL above. Requesting the legacy `/auth` endpoint last is essential.

Only the three heatmap cookies are exported; login/session cookies stay in the
browser. Cookies expire: retrieve them again when tile requests stop working.
Failures raise `StravaCFetchCookieError`; a failed refresh clears any old result.
Strava's website endpoints are not a stable public API and can change again.

## Development

```sh
python -m pip install -e . pytest
python -m pytest
```

Tests use synthetic cookies and a local simulated login site; they do not need
credentials or contact Strava. On 2026-10-05, login through an existing Chrome
browser and `fetchCookiesFromBrowser(context)` were verified live, including a
successful legacy TMS zoom-15 PNG download. The fully automatic fresh-browser
path encountered Strava HTTP 403 and is not claimed to work reliably.

A [2026-10-06 investigation](docs/login-investigation-2026-10-06.md) identified
and corrected translated-button and post-login response-body handling bugs.
Follow-up controlled trials completed two fresh-profile logins and independent
PNG downloads without manual input, but subsequent cold starts still returned
403 with the same normal Chrome setup. These changes are **not** a reliable-login
fix; the investigation records the successful and failed cases separately.

## Licence

GPL v3.0. See [LICENSE](LICENSE).
For Strava's historical permission to use heatmaps in JOSM, see the
[OSM Strava page](https://wiki.openstreetmap.org/wiki/Strava) and
[permission record](https://wiki.openstreetmap.org/wiki/Permissions/Strava).
