"""Backwards-compatible interface for retrieving signed heatmap parameters."""
from .browser import StravaBrowser, COOKIE_NAMES
from .fetch_error import StravaCFetchCookieError


class StravaCookieFetcher:
    def __init__(self):
        self.deleteCookieInfo()

    def deleteCookieInfo(self):
        self.keyPairId = ""
        self.policy = ""
        self.signature = ""
        self.cookieString = ""

    def setCookieString(self):
        if not all((self.keyPairId, self.policy, self.signature)):
            raise StravaCFetchCookieError(
                "setCookieString() must be called after fetchCookies()")
        self.cookieString = ("Key-Pair-Id=" + self.keyPairId + "&Policy=" + self.policy
                             + "&Signature=" + self.signature)

    def getCookieString(self):
        return self.cookieString

    def processCookieJar(self, cookiejar):
        self.deleteCookieInfo()
        values = {cookie.name: cookie.value for cookie in cookiejar
                  if cookie.name in COOKIE_NAMES and not cookie.is_expired()}
        if not all(values.get(name) for name in COOKIE_NAMES):
            raise StravaCFetchCookieError("Authentication Strava cookies not found.")
        self.keyPairId = values["CloudFront-Key-Pair-Id"]
        self.policy = values["CloudFront-Policy"]
        self.signature = values["CloudFront-Signature"]
        self.setCookieString()

    def fetchCookies(self, stravaEmail, stravaPassword, **browser_options):
        """Log in using Chromium. Existing two-argument calls remain valid."""
        self.deleteCookieInfo()
        browser = StravaBrowser(**browser_options)
        browser.stravaLogin(stravaEmail, stravaPassword)
        self.processCookieJar(browser.cookiejar)

    def fetchCookiesFromBrowser(self, context):
        """Fetch from an already authenticated Playwright BrowserContext.

        Useful for email-code, CAPTCHA or federated login completed by the user.
        The caller owns the browser and is responsible for closing it.
        """
        self.deleteCookieInfo()
        browser = StravaBrowser()
        browser.cookiesFromContext(context)
        self.processCookieJar(browser.cookiejar)
