#!/bin/sh

set -e

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers and their dependencies
playwright install --with-deps chromium