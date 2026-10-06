# Fresh-session login investigation — 2026-10-06

## Follow-up controlled analysis — 08:39–08:43 Europe/Rome

**New evidence: two fresh-session logins completed end-to-end, including an
independent HTTP 200 PNG tile download (142,787 bytes each).** Both started with
zero cookies in isolated profiles, used the stored email/password automatically,
and involved no manual login, inbox access, imported session, or CAPTCHA solving.
This supersedes the earlier absence of a fresh-login PNG proof, but **not** the
conclusion that reliability is unresolved.

Same installed Chrome 149.0.7827.103, visible window, Italian locale, device,
network, account, UI-driven form submission and response-stage diagnostics:

| Trial | Launcher | navigator.webdriver | Email | Password | Independent tile |
| --- | --- | --- | --- | --- | --- |
| A | Normal Chrome + local CDP | false | 200 | 200 | 200, PNG |
| B | Normal Chrome + local CDP | false | 200 | 200 | 200, PNG |
| C | Playwright, same Chrome binary | true | 403 | not submitted | not attempted |
| D | Normal Chrome + local CDP | false | 403 | not submitted | not attempted |
| E | Normal Chrome + local CDP | false | 403 | not submitted | not attempted |

The rejected email responses were captured before the site's automatic reload:
`{"success":false,"details":{}}`. Requests contained a reCAPTCHA response and a
CSRF header, with an empty `country` honeypot field. In trial E the outgoing CSRF
header was compared in memory with the page's current CSRF meta value and matched.
No token or cookie values were logged. This rules out an absent/mismatched page
CSRF value in that trial, not every possible server-side CSRF/session error.

### What follows from the comparison

- A blanket inability to automate Strava login is disproved for this account:
  two complete automated runs succeeded.
- `navigator.webdriver` alone cannot explain all rejections: D and E failed with
  it false. It could still be one input to a broader decision.
- Wrong passwords or email OTP entry do not explain these specific failures:
  the rejection precedes password submission or an OTP entry screen.
- The public frontend handles email HTTP 403 as `login_failed_trust`. A dynamic
  trust/risk decision (potentially including reCAPTCHA, request history, account
  or network signals) is consistent with the observations, **not established as
  the exact server-side cause**. Strava exposes neither an assessment score nor
  a rejection reason in these responses.
- A reCAPTCHA token being present does not establish a valid/acceptable backend
  assessment. Google's documentation distinguishes validity, expected action,
  risk score and reasons; these assessments are returned to the site backend.

### Controls and limitations

This is a small ordered diagnostic sample, not a measured success rate or a
randomized experiment. The launcher changes several browser defaults at once;
no flag was individually toggled. Additional header inspection was enabled in
C/D, then removed in E; E still failed. The CSRF comparison was added in E.
All such instrumentation differences are explicit and prevent claiming perfect
experimental isolation. Temporal/rate effects have not been independently tested.
No stealth flags, fingerprint spoofing, proxy rotation, CAPTCHA-solving services
or artificial human-behavior simulation were used. Further bursts of login
attempts would add confounding rather than establish causality.

Reference: https://docs.cloud.google.com/recaptcha/docs/interpret-assessment-website

---

## Initial investigation (06:21–06:33): unresolved reliability

This investigation does **not** establish a reliable unattended login or a
solution for a public multi-user service. Keep the HTTP 403 issue open.

One fully scripted run from a new, empty Chrome profile reached `/onboarding`
after a successful password submission and retrieved heatmap authorization
cookies. No existing authenticated session was copied into that profile and
no email code or manual action was used. However, independent cold-start runs
still failed with HTTP 403 at `/login/request_otp`, including after waiting for
page/network initialization. There is no successful new end-to-end PNG proof
from this investigation: the post-login tile probe failed with an HTTP error
whose status was not recorded. Do not conflate the prior session-reuse tile
verification with these fresh-login trials.

## Configurations examined

- Playwright-launched installed Chrome, visible, empty persistent profile:
  HTTP 403 at the email stage.
- Independently launched installed Chrome, controlled through local CDP,
  empty profile: some email/password stages succeeded; other fresh starts
  returned HTTP 403. No stealth patches, user-agent spoofing, or challenge
  solving was applied.
- Playwright Firefox 150.0.2, headless, new context: HTTP 403 at the email stage.
- Waiting for network idle did not reliably remove the failure; this experiment
  is not shipped as a supposed 403 fix.
- A diagnostic retry following the site's own automatic error reload was
  inconclusive because the page was still transitioning. No retry loop is added.

The failing request included both a reCAPTCHA response and a CSRF header.
A response-stage diagnostic confirmed an application JSON rejection with
`success` and `details` fields, HTTP 403; no usable reason was established.
Their presence does not establish that either token was valid. The precise
server-side rejection cause remains unknown.

## Two independently demonstrated client bugs

1. After email submission, the account language switched the page to Italian
   despite the original English page. Looking for an English `Use password`
   label stalled. Select the site's `data-testid="use-password-cta"` instead.
2. A successful `/session` response can become unavailable to CDP when the
   browser immediately navigates. Reading `response.json()` raised
   `Network.getResponseBody: No resource with given identifier found` after
   HTTP 200. Require a same-site post-login navigation and authenticated
   `/auth` cookie retrieval instead. HTTP 200 alone is not success.

These fixes are useful but do not resolve the upstream 403 rejection.
Regression tests cover a translated button, a redirect without readable JSON,
failed credentials, cross-site redirects, and cookie authorization failures.
All simulated network traffic is intercepted; these tests are not live proof.

## Remaining authentication boundaries

- Accounts requiring an emailed code still need access to that code. Neither
  an email inbox nor a code provider was available/used in these trials.
- Interactive CAPTCHA or other verification cannot be claimed automated.
- The official Strava OAuth documentation covers API v3. Its reference does
  not document global heatmap signed-cookie authorization. No OAuth-based
  replacement for that authorization was established.
- Existing production browser sessions and the private app deployment were
  not changed. Credentials remained in the macOS Keychain and process memory;
  no credentials or signed URLs are included in this report or the repository.

## References

- https://developers.strava.com/docs/authentication/
- https://developers.strava.com/docs/reference/
- https://github.com/aexel90/strava_kudos/issues/4 (independent Firefox approach;
  useful as a hypothesis, not evidence that our account succeeds)
- https://github.com/williamfiset/strava_kudos/blob/main/src/browser.ts
