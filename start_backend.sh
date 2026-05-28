#!/usr/bin/env bash
set -e
cd backend
if [ ! -d .venv ]; then python -m venv .venv; fi
source .venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
uvicorn app.main:app --reload --port 8000
