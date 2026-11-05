# Public demo

`demo_wsgi.py` runs a separate demo of the board (`coast_requests/demo.py`). It is not the station's app and shares nothing with it:

- **No real data or controls.** It has no username or password, no Netlify webhook secret (the webhook route returns 404) and no database file. It can't receive real requests, see listener details or affect the station.
- **A private board per visitor.** "Open the demo board" creates an in-memory SQLite database with eight fictional requests. Played, Not played, Remove and "Add a listener request" only change that visitor's board. Boards are deleted after an hour without activity.
- **Bounds.** Up to 200 boards at once; when full, only a board unused for over two minutes can make way (open boards refresh every 20 seconds), otherwise newcomers are asked to try again shortly. 60 new boards a minute overall, and, when `TRUSTED_PROXY_HOPS` says which `X-Forwarded-For` entry the host's proxy adds, 6 a minute and 10 at once per visitor address. It's off by default, because an address a visitor writes themselves could be used to claim someone else's limit. 60 requests per board, 16 KB per form, two hours at most per board. CSRF protection, escaping and the Content-Security-Policy are the same as the real app.
- **Hosting.** `render.yaml` runs it as a free Render web service with one Gunicorn process. After 15 minutes without visitors Render stops it, so the next visitor waits about a minute and every board starts afresh.

Run it locally:

```
pip install -r requirements.txt
flask --app coast_requests.demo:create_demo_app run
```

`tests/test_demo.py` checks private boards, that sign-in and the webhook can't be used, the request cap, CSRF and expiry.

Made by Claude (Anthropic's AI assistant) in Claude Code on 5 November 2026, at Jamie's request.
