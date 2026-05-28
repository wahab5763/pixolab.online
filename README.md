# Pixolab — Free Online Image Editor

> A fully free, no-account-required image editing web app.  
> Live at: **pixolab.online**

---

## Features

| Tool | Description |
|---|---|
| **Background Remover** | AI-powered background removal using U²-Net (rembg) |
| **Change Background** | Swap background with an uploaded image, solid color, or AI-generated scene |
| **Smart Poster** | 9 professional ad poster templates — upload product image, fill in text, download |
| **Photo Studio** | Client-side photo editor with filters, adjustments, and transforms |
| **Image Tools** | Resize, compress, and watermark — all in the browser, no upload needed |

- No login or account required
- No credits or payments — 100% free
- Photo Studio and Image Tools run entirely client-side (no server upload)
- Fully responsive — mobile, tablet, and desktop

---

## Tech Stack

### Backend
- **Python 3.11+** / **FastAPI** — REST API
- **Pillow** — poster rendering and image compositing
- **rembg + ONNX Runtime** — AI background removal (U²-Net model)
- **SQLAlchemy + SQLite** — lightweight database
- **Uvicorn** — ASGI server

### Frontend
- **React 18 + Vite** — fast development and production builds
- **Tailwind CSS** — utility-first styling
- **Framer Motion** — animations
- **Lucide React** — icons
- **HTML5 Canvas API** — client-side image processing for Photo Studio and Image Tools

---

## Project Structure

```
pixolab/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point
│   │   ├── config.py             # Settings via pydantic-settings
│   │   ├── services.py           # Image processing logic (Pillow)
│   │   ├── templates_config.py   # 9 Smart Poster template definitions
│   │   └── routes/
│   │       ├── generation.py     # POST /api/generation/*
│   │       └── tools.py          # POST /api/tools/*
│   ├── storage/
│   │   ├── uploads/              # Uploaded images (gitignored)
│   │   └── results/              # Generated outputs (gitignored)
│   ├── requirements.txt
│   └── requirements-optional-ai.txt   # rembg + onnxruntime
└── frontend/
    ├── public/
    │   └── favicon.svg
    ├── src/
    │   ├── App.jsx
    │   ├── index.css
    │   ├── lib/api.js             # API client
    │   ├── components/
    │   │   ├── Navbar.jsx
    │   │   ├── FeatureStrip.jsx
    │   │   ├── TemplateGallery.jsx
    │   │   └── TemplateForm.jsx
    │   └── pages/
    │       ├── BackgroundRemover.jsx
    │       ├── ChangeBackground.jsx
    │       ├── SmartPoster.jsx
    │       ├── PhotoStudio.jsx
    │       └── ImageTools.jsx
    ├── package.json
    └── vite.config.js
```

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

# Install core dependencies
pip install -r requirements.txt

# Install background removal (downloads ~170 MB model on first use)
pip install -r requirements-optional-ai.txt

# Create .env
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux

# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173`.

---

## Environment Variables

Create `backend/.env`:

```env
APP_NAME=Pixolab
DATABASE_URL=sqlite:///./pixolab.db
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Background removal (requires rembg installed)
ENABLE_BACKGROUND_REMOVAL=true

# Hugging Face — optional, for AI background generation
HF_TOKEN=your_hf_token_here
ENABLE_HF_BACKGROUND=false
HF_MODEL_ID=black-forest-labs/FLUX.1-schnell
```

> `.env` is gitignored — never commit it.

---

## Smart Poster Templates

9 templates across 6 categories. The person/influencer image is **optional** on all templates.

| Template | Category |
|---|---|
| Tech Product Launch | Technology |
| Elegance & Power | Fashion & Lifestyle |
| Performance Action | Sports & Tech |
| Beauty Glow | Beauty |
| Sports Energy | Sports |
| Corporate Pro | Business |
| Premium Hero Product | Technology |
| Influencer Split Poster | Fashion & Lifestyle |
| Futuristic Launch | Technology |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/generation/templates` | List all poster templates |
| `POST` | `/api/generation/generate` | Generate a custom poster |
| `POST` | `/api/generation/generate-template` | Generate from a template |
| `POST` | `/api/tools/remove-background` | Remove image background |
| `POST` | `/api/tools/change-background` | Swap image background |

---

## Deployment

Requires a VPS with Python support — **not** PHP shared hosting.

**Recommended: Hetzner Cloud CX23** (~€3.79/mo)
- 2 vCPU, 4 GB RAM, 40 GB SSD
- rembg needs ~1.5–2 GB RAM; 4 GB is the minimum

Suggested server stack on Ubuntu 24.04:
- **Nginx** — reverse proxy + SSL termination
- **Uvicorn** — FastAPI process
- **Certbot** — free SSL via Let's Encrypt
- **systemd** — keep the backend running as a service

---

## License

MIT — free to use, modify, and deploy.
