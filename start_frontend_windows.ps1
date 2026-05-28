cd frontend
npm install
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
