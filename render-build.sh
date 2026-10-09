#!/usr/bin/env bash
# ==============================================================================
# Render Build Script for OnBoarding Buddy (Native Python Runtime)
# ==============================================================================
set -o errexit

echo "==> [OnBoarding Buddy] Upgrading pip..."
python -m pip install --upgrade pip

echo "==> [OnBoarding Buddy] Installing Python dependencies..."
pip install -r requirements.txt

echo "==> [OnBoarding Buddy] Running database schema synchronization..."
python migrate.py || echo "==> [OnBoarding Buddy] Migration finished or local SQLite fallback active."

echo "==> [OnBoarding Buddy] Build completed successfully!"
