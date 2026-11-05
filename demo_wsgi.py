"""Entry point for the public demo (fictional requests, no connection to the station).
See docs/demo.md."""

from coast_requests.demo import create_demo_app

application = create_demo_app()
