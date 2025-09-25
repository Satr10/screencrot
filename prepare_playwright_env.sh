#!/bin/sh

set -e

# Install dependensi Python
pip install "fastapi[all]" uvicorn playwright

# Install browser Playwright dan dependensinya
playwright install --with-deps chromium
