# Public demo

`demo_wsgi.py` runs a separate demo of the board (`coast_requests/demo.py`). It is not the station's app and shares nothing with it:

- **No real data or controls.** It has no username or password, no Netlify webhook secret (the webhook route returns 404) and no database file. It can't receive real requests, see listener details or affect the station.
- **A private board per visitor.** "Open the demo board" creates an in-memory SQLite database with eight fictional requests. Played, Not played, Remove and "Add a listener request" only change that visitor's board. Boards are deleted after an hour without activity.
- **Bounds.** Up to 200 boards at once, 30 new boards a minute, 60 requests per board and 16 KB per form. CSRF protection, escaping and the Content-Security-Policy are the same as the real app.
- **Hosting.** `deploy/huggingface/` builds a Docker image that runs it with one Gunicorn process.

Run it locally:

```
pip install -r requirements.txt
flask --app coast_requests.demo:create_demo_app run
```

`tests/test_demo.py` checks private boards, that sign-in and the webhook can't be used, the request cap, CSRF and expiry.

Made by Claude (Anthropic's AI assistant) in Claude Code on 5 November 2026, at Jamie's request.
