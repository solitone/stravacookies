# Changelog

## 2.0.0 — 2026-10-05

- Replace the obsolete mechanize login with Playwright and the modern Strava email/password flow.
- Reuse authenticated browser contexts via `fetchCookiesFromBrowser(context)`.
- Validate signed heatmap cookies and clear stale state on errors.
- Keep the existing `fetchCookies(email, password)` API.
- Migration: Python >=3.9 and a Playwright browser are required for fresh login.
- Known limitation: Strava may still block fresh automated browsers with HTTP 403; authenticated context reuse is the verified path, not a guarantee of unattended login.
- Distributed as a GitHub release; this release does not publish to PyPI.
