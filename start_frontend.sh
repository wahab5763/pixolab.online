#!/usr/bin/env bash
set -e
cd frontend
npm install
if [ ! -f .env ]; then cp .env.example .env; fi
npm run dev
