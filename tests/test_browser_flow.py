"""Exercise the actual browser workflow without sending data to Strava."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from stravacookies import StravaBrowser, StravaCFetchCookieError
from unittest.mock import Mock

LOGIN = '''<form id="email-form"><input type="email"><button type="submit">Log in</button></form>
<script>
const passwordForm = () => {
 document.body.innerHTML = '<form id="password-form"><input type="password"><button type="submit">Log in</button></form>';
 document.querySelector('form').onsubmit = async e => {
  e.preventDefault();
  const r = await fetch('/session', {method:'POST'});
  const data = await r.json();
  if (data.success) location.href = '/dashboard';
 };
};
document.querySelector('form').onsubmit = async e => {
 e.preventDefault();
 const r = await fetch('/login/request_otp', {method:'POST'});
 const data = await r.json();
 if (r.ok && data.use_password) {
  document.body.innerHTML = '<button>Use password</button><button>Email me a code</button>';
  document.querySelector('button').onclick = passwordForm;
 }
};
</script>'''


@pytest.fixture
def context():
    with sync_playwright() as p:
        options = {"headless": True}
        if not Path(p.chromium.executable_path).exists():
            if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists():
                options['channel'] = 'chrome'
            else:
                pytest.skip('Install Playwright Chromium for browser-flow tests')
        browser = p.chromium.launch(**options)
        context = browser.new_context(locale='en-US')
        yield context
        browser.close()


def simulate(context, *, otp_status=200, use_password=True, success=True):
    calls = []
    def route(request):
        path = request.request.url.split('.com', 1)[-1]
        calls.append(path)
        if path == '/login':
            request.fulfill(content_type='text/html', body=LOGIN)
        elif path == '/login/request_otp':
            request.fulfill(status=otp_status, content_type='application/json',
                            body=json.dumps({'use_password':use_password}))
        elif path == '/session':
            request.fulfill(content_type='application/json', body=json.dumps({'success':success}))
        elif path == '/auth':
            request.fulfill(body='authorized')
        else:
            request.fulfill(content_type='text/html', body='Dashboard')
    context.route('**/*', route)
    # context.request bypasses page routing: fake only the legacy auth response;
    # the login flow, form submissions and redirects use a real browser.
    return calls


def auth_stub(browser, calls):
    def authorize(context):
        calls.append('legacy-auth-after-login')
    browser.cookiesFromContext = authorize


def test_two_step_login(context):
    calls = simulate(context)
    browser = StravaBrowser(timeout=5000)
    auth_stub(browser, calls)
    browser._login(context, 'test@example.invalid', 'dummy-password')
    assert '/login/request_otp' in calls
    assert '/session' in calls
    assert calls.index('/session') < calls.index('legacy-auth-after-login')
    assert not context.pages


@pytest.mark.parametrize('settings,message', [
    ({'otp_status':403}, 'HTTP 403'),
    ({'use_password':False}, 'email verification code'),
    ({'success':False}, 'did not accept'),
])
def test_login_errors_are_actionable(context, settings, message):
    calls = simulate(context, **settings)
    browser = StravaBrowser(timeout=5000)
    auth_stub(browser, calls)
    with pytest.raises(StravaCFetchCookieError, match=message):
        browser._login(context, 'test@example.invalid', 'dummy-password')
    assert 'legacy-auth-after-login' not in calls
    assert not context.pages


def test_remembered_login():
    context = Mock()
    page = context.new_page.return_value
    page.url = 'https://www.strava.com/dashboard'
    browser = StravaBrowser(timeout=5000)
    browser.cookiesFromContext = Mock()
    browser._login(context, '', '')
    browser.cookiesFromContext.assert_called_once_with(context)
    page.locator.assert_not_called()
    page.close.assert_called_once_with()
