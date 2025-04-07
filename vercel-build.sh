#!/bin/bash

# Install Python dependencies
pip install -r requirements-vercel.txt

# Install only Chromium browser
playwright install chromium

# Make browser executable
chmod -R 777 ~/.cache/ms-playwright/ 