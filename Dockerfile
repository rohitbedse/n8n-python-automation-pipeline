FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir requests beautifulsoup4 playwright

RUN playwright install --with-deps chromium

CMD ["python", "/data/scraper/run_pipeline.py"]