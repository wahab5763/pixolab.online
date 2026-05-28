# AdFusion AI SaaS — Influencer Product Ad Generator

AdFusion AI SaaS is a full-stack Python + React application that creates a single promotional ad image from two uploads:

- **Image 1:** person / influencer / model photo
- **Image 2:** product photo
- **Output:** a branded social-media ad creative

This upgraded version improves the previous output quality by using safer design rules: no overlapping headline, no duplicated CTA, better product stage, shadows, typography panels, cleaner composition, optional Hugging Face FLUX background, and an experimental image-to-image **AI Creative** mode.

---

## What changed in this upgraded version

### 1. Improved Smart Poster mode

The default mode now creates a cleaner marketing layout:

- top safe text area
- product hero card/stage
- better shadows and depth
- cleaner CTA placement
- no headline behind the person/product
- readable deterministic typography
- improved colour/background design
- optional cutout support with `rembg`

### 2. Improved AI Background mode

AI Background mode uses Hugging Face FLUX only for the **background**, then applies the improved poster layout. This gives more creative backgrounds while keeping text readable and controlled.

### 3. New AI Creative mode

AI Creative mode is an experimental premium mode. It first creates a clean reference composition, then optionally sends that image to an image-to-image model through Hugging Face if configured.

This mode is designed for later SaaS premium usage, but it requires a Hugging Face provider/model that supports image-to-image.

---

## Tech stack

### Frontend

- React + Vite
- Tailwind CSS
- Framer Motion
- lucide-react icons
- Modern SaaS-style UI

### Backend

- Python FastAPI
- SQLite + SQLAlchemy
- JWT authentication
- Credit-based generation
- PIL/Pillow image compositor
- Optional Hugging Face integration
- Stripe-ready placeholder billing

---

## Quick start in VS Code

Open the project folder in VS Code and use two terminals.

### Terminal 1 — Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env`:

Windows:

```powershell
copy .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Run backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend docs:

```text
http://localhost:8000/docs
```

### Terminal 2 — Frontend

```bash
cd frontend
npm install
```

Create `.env`:

Windows:

```powershell
copy .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Run frontend:

```bash
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## Recommended optional install for better cutouts

For cleaner person/product cutouts, install the optional background-removal dependencies inside the backend virtual environment:

```bash
pip install -r requirements-optional-ai.txt
```

The first `rembg` use may download model weights, so it can be slower on first generation.

---

## Hugging Face background mode

Add a new Hugging Face token to `backend/.env`:

```env
HF_TOKEN=hf_your_new_token_here
HF_MODEL_ID=black-forest-labs/FLUX.1-schnell
HF_PROVIDER=
ENABLE_HF_BACKGROUND=true
```

Then select **AI Background** in the UI.

Important: if you have shared your token anywhere, revoke it and create a new token. The token should have Hugging Face Inference Providers permission, and the selected model may require accepting access/terms on Hugging Face.

---

## Experimental AI Creative mode

To test image-to-image refinement, add a model that supports image-to-image:

```env
ENABLE_AI_CREATIVE=true
HF_CREATIVE_MODEL_ID=black-forest-labs/FLUX.1-Kontext-dev
```

Then select **AI Creative** in the UI.

If the selected provider/model fails, the backend will fall back to the improved Smart Poster output instead of breaking the app. Check the backend terminal for `[HF ERROR]` messages.

---

## Demo flow

1. Register a user.
2. Upload a person image.
3. Upload a product image.
4. Select a style.
5. Add brand name, headline, subheadline and CTA.
6. Select Smart Poster, AI Background, or AI Creative mode.
7. Confirm consent.
8. Generate and download the result.

---

## Notes for SaaS launch

For production, replace local storage/SQLite with:

- PostgreSQL
- S3 / Cloudflare R2 / Cloudinary
- Redis + Celery/RQ generation queue
- Stripe webhooks for credit top-ups
- admin dashboard
- content moderation
- rate limits
- email verification

---

## Project structure

```text
adfusion-ai-saas/
  backend/
    app/
      main.py
      config.py
      database.py
      models.py
      schemas.py
      security.py
      services.py
      routes/
        auth.py
        generation.py
        billing.py
    requirements.txt
    requirements-optional-ai.txt
    .env.example
  frontend/
    src/
      App.jsx
      pages/ImageCombiner.jsx
      components/
      lib/api.js
    package.json
    .env.example
```
