# 🚀 Deploying OnBoarding Buddy to Render

This comprehensive guide walks you through deploying **OnBoarding Buddy** to [Render](https://render.com) as a production-grade, highly available cloud web service.

---

## 🌟 Architecture Overview

OnBoarding Buddy is packaged as a **unified high-performance web service**:
- **Backend**: FastAPI / Uvicorn (Python 3.12) running AST code parsing, Git analysis, repository indexing, security auditing, and Groq AI inference.
- **Frontend**: Responsive Single-Page Application (SPA) served directly from the root `/` and `/static/*` path with Vis.js interactive dependency graphs, Markdown rendering, and code navigation.
- **Database**: Works out of the box with **Neon Serverless PostgreSQL**, Render Managed PostgreSQL, Supabase, or automatic local SQLite fallback.
- **Health Probes**: Liveness and readiness probes pre-configured at `/api/health`.

---

## ⚡ Deployment Methods

Choose the method that best matches your workflow:

| Method | Best For | Complexity | Setup Time |
|---|---|---|---|
| **Option 1: Render Blueprint (`render.yaml`)** *(Recommended)* | Automated Infrastructure-as-Code | 🟢 1-Click | ~3 minutes |
| **Option 2: Docker Web Service** | Exact container reproducibility | 🟢 Simple | ~4 minutes |
| **Option 3: Native Python Web Service** | Fast build times on Render Free Tier | 🟢 Simple | ~2 minutes |

---

## Option 1: 1-Click Render Blueprint (Recommended)

Render Blueprints use the repository's [render.yaml](file:///c:/OnBoarding_Buddy/render.yaml) file to automatically configure the service, health checks, ports, and environment variables.

### Steps:
1. Push your repository to GitHub:
   ```bash
   git push origin main
   ```
2. Log in to your [Render Dashboard](https://dashboard.render.com/).
3. In the top navigation, click **New +** and select **Blueprint**.
4. Connect your GitHub repository (`Hary2003/OnBoarding_Buddy`).
5. Render will automatically detect [render.yaml](file:///c:/OnBoarding_Buddy/render.yaml) and parse the configuration.
6. Under **Environment Variables**, provide your secrets:
   - **`GROQ_API_KEY`**: Your Groq API key from [console.groq.com](https://console.groq.com/keys) (e.g., `gsk_...`).
   - **`DATABASE_URL`**: *(Optional)* Your PostgreSQL connection string (from Neon or Render PostgreSQL). If left empty, OnBoarding Buddy will automatically fall back to SQLite.
7. Click **Apply**.
8. Render will build the container and deploy your live URL (e.g. `https://onboarding-buddy.onrender.com`).

---

## Option 2: Render Docker Web Service (Manual)

If you prefer to configure the Web Service manually via the Render UI:

### Steps:
1. In the Render Dashboard, click **New +** -> **Web Service**.
2. Select **Build and deploy from a Git repository** and connect your repository.
3. Configure the service settings:
   - **Name**: `onboarding-buddy`
   - **Region**: Choose the closest region (e.g., *Oregon (US West)*, *Frankfurt (EU)*, *Singapore (Asia)*).
   - **Branch**: `main`
   - **Language / Runtime**: **Docker**
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Context**: `.`
   - **Instance Type**: **Free** or **Starter**
4. Expand **Advanced** and set **Health Check Path**:
   ```
   /api/health
   ```
5. Add the **Environment Variables** (see table below).
6. Click **Create Web Service**.

---

## Option 3: Native Python Web Service (Manual)

For slightly faster initial build times without Docker layer caching:

### Steps:
1. In the Render Dashboard, click **New +** -> **Web Service**.
2. Connect your repository.
3. Configure settings:
   - **Language / Runtime**: **Python 3**
   - **Branch**: `main`
   - **Build Command**:
     ```bash
     chmod +x render-build.sh && ./render-build.sh
     ```
     *(Or simply `pip install -r requirements.txt`)*
   - **Start Command**:
     ```bash
     python app.py
     ```
4. Expand **Advanced** and set **Health Check Path**: `/api/health`.
5. Add the **Environment Variables**.
6. Click **Create Web Service**.

---

## 🔑 Environment Variables Reference

Configure these in the **Environment** tab of your Render service:

| Variable | Required | Default / Recommended Value | Description |
|---|---|---|---|
| `GROQ_API_KEY` | **Yes** | `gsk_...` | Groq Cloud API Key for AI onboarding assistance, chat, and AST summaries |
| `DATABASE_URL` | Optional | `postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require` | PostgreSQL connection string. Defaults to SQLite if omitted. |
| `ENVIRONMENT` | Yes | `production` | Enables production security policies and hides development stack traces |
| `DEBUG` | Yes | `false` | Disables debug mode in production |
| `HOST` | Yes | `0.0.0.0` | Network interface to bind (required for cloud containers) |
| `PORT` | Auto | `8000` *(Render sets this automatically)* | Application port |
| `ENABLE_DOCS` | Optional | `true` | Enables Swagger UI at `/docs` and ReDoc at `/redoc` |
| `GROQ_MODEL` | Optional | `openai/gpt-oss-120b` | Groq LLM model (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`) |
| `RATE_LIMIT_ENABLED` | Optional | `true` | Enables per-IP sliding-window rate limiting |
| `RATE_LIMIT_PER_MINUTE` | Optional | `120` | Maximum requests per IP per minute |
| `API_AUTH_ENABLED` | Optional | `false` | Optional Bearer API Key gate for `/api/*` endpoints |
| `API_KEY` | Optional | *(Secret token)* | API Key to require when `API_AUTH_ENABLED=true` |
| `CORS_ALLOWED_ORIGINS`| Optional | *(Auto-configured with Render URL)* | Comma-separated list of additional external frontend domains |

---

## 🗄️ Setting Up the Database

You have two great options for persistent storage:

### Option A: Neon Serverless PostgreSQL (Recommended)
1. Go to [neon.tech](https://neon.tech) and create a free PostgreSQL database.
2. Copy the Connection String (starts with `postgresql://...`).
3. Paste it as `DATABASE_URL` in your Render Environment Variables.
4. OnBoarding Buddy automatically applies all Alembic migrations on startup!

### Option B: Render Managed PostgreSQL
1. In the Render Dashboard, click **New +** -> **PostgreSQL**.
2. Name it `onboarding-buddy-db`.
3. Choose the **Free** plan.
4. Once created, copy the **Internal Database URL** (or **External Database URL**).
5. Add it as `DATABASE_URL` in your OnBoarding Buddy web service.

---

## ✅ Post-Deployment Verification

Once Render finishes deploying (displays `Your service is live 🎉`), verify your instance:

1. **Health Check Probe**:
   ```bash
   curl -f https://<YOUR-RENDER-APP>.onrender.com/api/health
   ```
   *Expected Response:*
   ```json
   {
     "status": "healthy",
     "environment": "production",
     "groq_configured": true,
     "db_configured": true,
     "database": {
       "status": "connected"
     }
   }
   ```

2. **Web Application Interface**:
   - Open `https://<YOUR-RENDER-APP>.onrender.com/` in your browser.
   - You should see the complete OnBoarding Buddy UI with real-time status indicators.

3. **API Documentation**:
   - Open `https://<YOUR-RENDER-APP>.onrender.com/docs` to test endpoints via Swagger UI.

---

## 💡 Render Free Tier Tips

- **Cold Starts**: Render's free tier spins down web services after 15 minutes of inactivity. When a new request arrives, it may take ~30-50 seconds to spin back up.
- **Repository Cloning**: When analyzing large public GitHub repositories (e.g. >500MB), allow a few extra seconds as Render free tier instances operate on shared CPU bandwidth.
- **Keep-Alive (Optional)**: You can set up a free uptime monitor (e.g. UptimeRobot or Cron-job.org) to ping `https://<YOUR-RENDER-APP>.onrender.com/api/health` every 10 minutes to prevent cold starts.
