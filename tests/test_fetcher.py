import time
from http.cookiejar import Cookie, CookieJar
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from stravacookies import StravaBrowser, StravaCFetchCookieError, StravaCookieFetcher
from stravacookies.browser import AUTH_URL, COOKIE_NAMES


def cookie(name, value="test", expires=None):
    return Cookie(0, name, value, None, False, ".strava.com", True, True,
                  "/", True, True, expires, expires is None, None, None, {})


def jar(names=COOKIE_NAMES, expires=None):
    result = CookieJar()
    for name in names:
        result.set_cookie(cookie(name, expires=expires))
    return result


def test_query_string_compatibility():
    fetcher = StravaCookieFetcher()
    fetcher.processCookieJar(jar())
    assert fetcher.getCookieString() == "Key-Pair-Id=test&Policy=test&Signature=test"


@pytest.mark.parametrize("names", [COOKIE_NAMES[:2], (),
                                  tuple("prefix-" + n for n in COOKIE_NAMES)])
def test_incomplete_refresh_clears_previous_result(names):
    fetcher = StravaCookieFetcher()
    fetcher.processCookieJar(jar())
    with pytest.raises(StravaCFetchCookieError):
        fetcher.processCookieJar(jar(names))
    assert fetcher.getCookieString() == ""
    assert (fetcher.keyPairId, fetcher.policy, fetcher.signature) == ("", "", "")


def test_expired_cookies_are_rejected():
    with pytest.raises(StravaCFetchCookieError):
        StravaCookieFetcher().processCookieJar(jar(expires=int(time.time()) - 1))


def test_failed_login_clears_previous_result(monkeypatch, capsys):
    fetcher = StravaCookieFetcher()
    fetcher.processCookieJar(jar())
    def fail(*args, **kwargs):
        raise StravaCFetchCookieError("Login rejected")
    monkeypatch.setattr(StravaBrowser, "stravaLogin", fail)
    with pytest.raises(StravaCFetchCookieError, match="Login rejected"):
        fetcher.fetchCookies("email", "secret")
    assert fetcher.cookieString == ""
    assert capsys.readouterr().err == ""


def context(status=200, names=COOKIE_NAMES):
    ctx = Mock()
    ctx.request.get.return_value = SimpleNamespace(status=status)
    ctx.cookies.return_value = [dict(name=n, value="test", domain=".strava.com",
                                    path="/", expires=time.time() + 60,
                                    httpOnly=True, secure=True) for n in names]
    return ctx


def test_context_requests_legacy_authorization_and_exports_only_heatmap_cookies():
    ctx = context(names=COOKIE_NAMES + ("_strava4_session", "strava_remember_token"))
    browser = StravaBrowser()
    browser.cookiesFromContext(ctx)
    ctx.request.get.assert_called_once_with(AUTH_URL, timeout=60000, max_redirects=0)
    ctx.cookies.assert_called_once_with(AUTH_URL)
    assert {c.name for c in browser.cookiejar} == set(COOKIE_NAMES)
    ctx.close.assert_not_called()


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_auth_failure_does_not_export_stale_cookies(status):
    browser = StravaBrowser()
    browser.cookiejar = jar()
    with pytest.raises(StravaCFetchCookieError, match=str(status)):
        browser.cookiesFromContext(context(status=status))
    assert not list(browser.cookiejar)


def test_successful_status_without_complete_cookies_is_not_success():
    with pytest.raises(StravaCFetchCookieError, match="all three"):
        StravaBrowser().cookiesFromContext(context(names=COOKIE_NAMES[:2]))


def test_public_context_api():
    fetcher = StravaCookieFetcher()
    ctx = context()
    fetcher.fetchCookiesFromBrowser(ctx)
    assert fetcher.signature == "test"
    ctx.close.assert_not_called()
