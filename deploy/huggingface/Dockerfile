# Coast Requests public demo: fictional requests only, no connection to the station.
FROM python:3.13-slim
ARG COAST_REQUESTS_COMMIT=main
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 1000 demo
WORKDIR /app
RUN git clone https://github.com/JamieP-205/coast-requests.git . && git checkout "$COAST_REQUESTS_COMMIT" \
 && pip install --no-cache-dir -r requirements.txt -r requirements-demo.txt && chown -R demo /app
USER demo
EXPOSE 7860
# One process, so every visitor's in-memory board lives in the same place.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:7860", "demo_wsgi:application"]
