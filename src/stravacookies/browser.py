"""Authenticate using Strava's JavaScript login and request legacy TMS cookies."""
from http import cookiejar
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError, TimeoutError, sync_playwright

from .fetch_error import StravaCFetchCookieError

LOGIN_URL = "https://www.strava.com/login"
AUTH_URL = "https://heatmap-external-a.strava.com/auth"
COOKIE_NAMES = ("CloudFront-Key-Pair-Id", "CloudFront-Policy", "CloudFront-Signature")


class StravaBrowser:
    def __init__(self, *, headless=False, timeout=60000, channel=None,
                 user_data_dir=None):
        """timeout is in milliseconds; an optional dedicated profile retains login.

        The default opens a visible browser so Strava can perform its normal
        browser checks. Install Chromium with ``python -m playwright install chromium``
        or select an installed browser with ``channel="chrome"``.
        """
        self.headless = headless
        self.timeout = timeout
        self.channel = channel
        self.user_data_dir = user_data_dir
        self.cookiejar = cookiejar.CookieJar()

    def cookiesFromContext(self, context):
        """Use an authenticated Playwright BrowserContext without closing it.

        Request /auth LAST: the modern maps page issues a different CloudFront
        policy for content-a.strava.com, which cannot authorize legacy TMS URLs.
        """
        self.cookiejar.clear()
        response = context.request.get(AUTH_URL, timeout=self.timeout,
                                       max_redirects=0)
        if response.status != 200:
            raise StravaCFetchCookieError(
                "Strava heatmap authorization failed (HTTP {}). "
                "Complete login in the browser first.".format(response.status))
        # Only take cookies that apply to the TMS host; never export login tokens.
        cookies = context.cookies(AUTH_URL)
        for item in cookies:
            if item["name"] not in COOKIE_NAMES:
                continue
            domain = item["domain"]
            expires = item.get("expires", -1)
            self.cookiejar.set_cookie(cookiejar.Cookie(
                version=0, name=item["name"], value=item["value"],
                port=None, port_specified=False,
                domain=domain, domain_specified=domain.startswith("."),
                domain_initial_dot=domain.startswith("."),
                path=item.get("path", "/"), path_specified=True,
                secure=item.get("secure", True),
                expires=int(expires) if expires > 0 else None,
                discard=expires <= 0, comment=None, comment_url=None,
                rest={"HttpOnly": None} if item.get("httpOnly") else {},
                rfc2109=False))
        if set(COOKIE_NAMES) - {c.name for c in self.cookiejar}:
            self.cookiejar.clear()
            raise StravaCFetchCookieError(
                "Strava did not return all three heatmap authorization cookies.")

    def _login(self, context, email, password):
        page = context.new_page()
        page.set_default_timeout(self.timeout)
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            # A remembered login may redirect directly to dashboard/onboarding.
            if "/login" in page.url:
                consent = page.locator("#CybotCookiebotDialogBodyButtonDecline")
                # Cookiebot can appear after hydration; a blocking overlay is
                # handled before entering any credentials.
                try:
                    consent.wait_for(state="visible", timeout=min(3000, self.timeout))
                    consent.click()
                except TimeoutError:
                    pass
                email_input = page.locator('input[type="email"]:visible').first
                email_input.fill(email)
                password_input = page.locator('input[type="password"]:visible').first
                if not password_input.is_visible():
                    with page.expect_response(
                        lambda r: "/login/request_otp" in r.url
                        and r.request.method == "POST"
                    ) as pending:
                        email_input.locator("xpath=ancestor::form").locator(
                            'button[type="submit"]').click()
                    response = pending.value
                    if response.status != 200:
                        raise StravaCFetchCookieError(
                            "Strava rejected the login request (HTTP {}). "
                            "Complete any verification in a browser, then use "
                            "fetchCookiesFromBrowser(context).".format(response.status))
                    result = response.json()
                    if not result.get("use_password"):
                        raise StravaCFetchCookieError(
                            "Strava requires an email verification code. Complete "
                            "login in a browser and use fetchCookiesFromBrowser(context).")
                    # Account settings can switch the page language after email
                    # submission even when the browser locale is English.
                    page.locator('[data-testid="use-password-cta"]:visible').click()
                password_input.fill(password)
                with page.expect_response(
                    lambda r: r.url.split("?")[0] == "https://www.strava.com/session"
                    and r.request.method == "POST"
                ) as pending:
                    password_input.locator("xpath=ancestor::form").locator(
                        'button[type="submit"]').click()
                response = pending.value
                if response.status != 200:
                    raise StravaCFetchCookieError(
                        "Strava did not accept the login. Check the credentials "
                        "or complete the required verification in a browser.")
                # A successful login may immediately navigate across page
                # processes, making the response body unavailable over CDP.
                # A 200 alone is NOT proof: require a same-site redirect and
                # authenticated /auth cookies below instead of reading JSON.
                try:
                    page.wait_for_url(
                        lambda url: urlsplit(url).hostname == "www.strava.com"
                        and not urlsplit(url).path.startswith("/login"),
                        wait_until="domcontentloaded")
                except TimeoutError:
                    raise StravaCFetchCookieError(
                        "Strava did not complete the login. Check the credentials "
                        "or complete the required verification in a browser."
                    ) from None
            self.cookiesFromContext(context)
        finally:
            page.close()

    def stravaLogin(self, email, password):
        self.cookiejar.clear()
        try:
            with sync_playwright() as playwright:
                options = {"headless": self.headless}
                if self.channel:
                    options["channel"] = self.channel
                if self.user_data_dir:
                    context = playwright.chromium.launch_persistent_context(
                        str(self.user_data_dir), locale="en-US", **options)
                    try:
                        self._login(context, email, password)
                    finally:
                        context.close()
                else:
                    browser = playwright.chromium.launch(**options)
                    try:
                        context = browser.new_context(locale="en-US")
                        self._login(context, email, password)
                    finally:
                        browser.close()
        except StravaCFetchCookieError:
            raise
        except TimeoutError:
            raise StravaCFetchCookieError(
                "Strava login timed out. A verification step or a changed login "
                "page may require manual login; use fetchCookiesFromBrowser(context)."
            ) from None
        except PlaywrightError:
            # Playwright call logs can contain form values. Never echo them.
            raise StravaCFetchCookieError(
                "Browser operation failed. Install Chromium with "
                "'python -m playwright install chromium', or use channel='chrome' "
                "with an installed Chrome browser."
            ) from None
