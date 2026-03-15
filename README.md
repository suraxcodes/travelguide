# ⬡ GoaInsight — AI Travel Guide OS

> **An intelligent, multi-agent travel content engine for Goa, India — wrapped in a cyberpunk-grade Streamlit UI.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit)
![AutoGen](https://img.shields.io/badge/AutoGen-MagenticOne-purple?style=flat-square)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-green?style=flat-square&logo=mongodb)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## 🧭 What is GoaInsight?

**GoaInsight** is a full-stack, AI-powered travel intelligence platform that generates rich, structured travel content for any destination in Goa — and beyond. You type a topic (e.g., *"Colva Beach"*, *"Baga Nightlife"*, *"Anjuna Flea Market"*), and the system dispatches a squad of specialized AI agents that collaboratively produce descriptions, full editorial content, geo-coordinates, travel guidelines, SEO titles, tags, AI-generated images, and a lot more — all stored in MongoDB and rendered in a stunning real-time UI.

This is not a chatbot. It is an **agentic content generation pipeline** with a production-grade database layer, intelligent caching, smart update detection, and a live Streamlit dashboard.

---

## ✨ What Makes GoaInsight Stand Out

| Feature | Why It's Different |
|---|---|
| 🤖 **Multi-Agent Architecture** | Uses Microsoft AutoGen's `MagenticOneGroupChat` — multiple specialized agents collaborate in parallel, not one monolithic prompt |
| 🧠 **Smart Update Engine** | Detects stale, wrong-location, or generic AI content and surgically updates only the fields that need it |
| 📡 **Live Geo-Tracking** | Fetches, validates, caches, and reverse-geocodes coordinates via Nominatim (OpenStreetMap) — with retry strategies |
| 🖼️ **AI Image Generation** | Generates full gallery images and thumbnails via Pollinations API, encoded as WebP base64 data URIs |
| 🗄️ **MongoDB-First** | Every piece of content is persisted, deduped, and enriched in a structured MongoDB Atlas collection |
| 🎨 **Cyberpunk UI** | A fully custom Streamlit interface with a neon-grid aesthetic, animated status indicators, and real-time panels |
| 🔀 **Dual LLM Support** | Switch between a **local Ollama model** (e.g., DeepSeek, LLaMA3) and **OpenRouter** (e.g., GPT-4o-mini) with one config flag |
| 🔒 **Flexible API Key Management** | Resolves credentials from env vars → Streamlit Secrets → local `api.txt` — works locally and in production |

---

## 🗂️ Project Structure

```
goainsight/
├── app.py                  # Streamlit frontend — the full UI dashboard
├── optimizetreavel.py      # Core engine — agents, DB, image gen, geo, smart update logic
├── location_cache.json     # Auto-generated local cache for geocoding results
├── api.txt                 # (Optional) Local API key file — not committed to Git
├── requirements.txt        # Python dependencies
└── README.md
```

---

## ⚙️ How It Works — Full Workflow

```
User Input (topic + optional details)
         │
         ▼
┌─────────────────────────┐
│   MongoDB Lookup         │  ← Check if topic already exists in DB
└────────────┬────────────┘
             │
     ┌───────┴────────┐
     │                │
  EXISTS           NOT FOUND
     │                │
     ▼                ▼
Smart Validator    Full Agent Pipeline
  ├─ Location?       ├─ Location Agent       → Nominatim Geocoding + Validation
  ├─ Description?    ├─ Description Agent    → 1-sentence summary
  ├─ Content?        ├─ Content Agent        → Full HTML editorial content
  ├─ Guidelines?     ├─ Guidelines Agent     → Visitor tips & protocols
  ├─ Images?         ├─ Image Prompt Agent   → Vivid prompt → Pollinations API
  └─ Tags/SEO?       ├─ Thumbnail Agent      → Focused thumbnail prompt
                     ├─ Tags Agent           → Keyword matrix
                     └─ SEO Agent            → Dual title variants
                              │
                              ▼
                    MongoDB INSERT / UPDATE
                              │
                              ▼
                    Streamlit UI Render
         ┌────────────────────┴────────────────────┐
         │                                         │
    LEFT PANEL                              RIGHT PANEL
  Title + Description                    Geo Tracker Map
  Tag Matrix                             Transport Grid
  Field Protocols (Guidelines)           Flag Register
  Full Intelligence Report               (Active / Trending / etc.)
  Visual Feed (Gallery + Thumbnail)
```

---

## 🤖 The Agent Squad

Each agent is a focused `AssistantAgent` from AutoGen, orchestrated by `MagenticOneGroupChat`. Agents do not share a single giant prompt — each has a narrow, specialized role:

| Agent | Role |
|---|---|
| `smart_location_agent` | Decides whether geo-lookup is needed and crafts the optimal search query |
| `location_validator_agent` | Validates that fetched coordinates actually match the topic |
| `description_agent` | Writes a punchy 1-sentence summary of the destination |
| `content_agent` | Generates full editorial HTML content tailored to the content type |
| `guidelines_agent` | Produces practical visitor tips, dos & don'ts |
| `image_prompt_agent` | Crafts a detailed, vivid image generation prompt |
| `thumbnail_prompt_agent` | Crafts a focused, square-format thumbnail prompt |
| `tags_agent` | Generates a keyword tag matrix for discovery |
| `seo_agent` | Outputs two SEO-optimized title variants |

---

## 🧠 Smart Update System

GoaInsight doesn't blindly regenerate — it checks whether existing database content is still valid before deciding what to update. A field triggers an update if any of the following are true:

- **Empty or blank** — field has no content
- **Outdated** — content was created more than 60 days ago
- **Wrong location** — content references a city/state inconsistent with the topic (e.g., a Goa beach article mentioning Mumbai)
- **Generic AI filler** — content contains vague phrases like *"popular destination"* or *"great spot"*
- **Missing topic name** — the destination name doesn't appear in the content
- **Stale years** — content references 2020, 2021, 2022, or 2023

Only fields that fail these checks are re-generated and patched via `$set` — no full document rewrites.

---

## 🗺️ Geo Intelligence

Location resolution uses a multi-strategy approach:

1. **Cache-first** — results are stored in `location_cache.json` to avoid redundant API calls
2. **Priority search** — tries `{topic}, Goa, India` first, then broader Indian states, then global
3. **Importance scoring** — picks the highest-importance Nominatim result within Goa's bounding box
4. **Reverse geocoding verification** — validates coordinates by reverse-geocoding them back
5. **Agent validation** — the `location_validator_agent` semantically checks if the address matches the topic
6. **Retry with modified queries** — up to 3 attempts with progressively adjusted search strategies

---

## 🖼️ AI Image Generation

Images are generated via the **Pollinations API** (free, no key required):

- **Main gallery image**: `512×512`, saved as PNG + encoded as WebP base64 data URI
- **Thumbnail**: `256×256`, same pipeline
- Images are embedded directly into MongoDB as data URIs, so no external image hosting is required

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/goainsight.git
cd goainsight
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

**Key dependencies:**
- `streamlit`
- `autogen-agentchat`, `autogen-ext[openai]`
- `pymongo`
- `Pillow`
- `requests`

### 3. Configure your API key

**Option A — Environment variable:**
```bash
export OPENROUTER_KEY=your_openrouter_key_here
```

**Option B — Streamlit Secrets (for deployment):**
Add to `.streamlit/secrets.toml`:
```toml
OPENROUTER_KEY = "your_key_here"
MONGODB_URI = "your_mongo_uri_here"
```

**Option C — Local file:**
Create `api.txt` in the project root with just your key on the first line.

### 4. Configure LLM backend

In `optimizetreavel.py`, set the flag at the top:

```python
# Use local Ollama (e.g., deepseek-r1:7b, llama3, mistral)
USE_OLLAMA = True
OLLAMA_MODEL = "deepseek-r1:7b"

# OR use OpenRouter (GPT-4o-mini, Claude, etc.)
USE_OLLAMA = False
```

### 5. Set up MongoDB

Create a MongoDB Atlas cluster (free tier works), create a database named `goa-app`, and add the URI to your secrets or env var as `MONGODB_URI`.

### 6. Run the app

```bash
streamlit run app.py
```

---

## 🖥️ UI Overview

The dashboard is divided into three zones:

**Left Panel — Intelligence Feed**
- Destination title and short description
- Tag matrix with color-coded chips
- Field protocols (visitor guidelines)
- Full intelligence report (scrollable HTML content)
- Visual feed (gallery + thumbnail images)

**Center Panel — Scan Console**
- Topic input and optional details field
- INITIATE DEEP SCAN trigger button
- AI chat interface for follow-up queries
- Live system status and timestamps

**Right Panel — Geo & Metadata**
- Embedded OpenStreetMap with marker and coordinate HUD
- Transport Grid (Walk / Boat / Drive / Transit availability)
- Flag Register (Active / Featured / Couple-Friendly / Group-Friendly / Kids / Trending / Monsoon / Open Now)

---

## 🔧 CLI Usage

You can also run the content engine directly from the terminal:

```bash
# Interactive mode
python optimizetreavel.py

# With arguments
python optimizetreavel.py "Colva Beach" "Known for its long stretch and Saturday market nearby"
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + Custom CSS (Orbitron / Share Tech Mono / Rajdhani fonts) |
| AI Agents | Microsoft AutoGen — `MagenticOneGroupChat` |
| LLM Backend | OpenRouter (GPT-4o-mini) or local Ollama |
| Image Generation | Pollinations API |
| Geocoding | OpenStreetMap Nominatim |
| Database | MongoDB Atlas (PyMongo) |
| Image Processing | Pillow (PIL) — WebP encoding |

---

## 🗺️ Roadmap

- [ ] Multi-city support beyond Goa
- [ ] User authentication and personalized watchlists
- [ ] Scheduled auto-refresh for outdated content
- [ ] Export to CMS-ready JSON / Markdown
- [ ] Voice input for destination queries
- [ ] Map clustering for multiple results

---

## 👨‍💻 Developer

Built by **Suraj Gawas**  
`GOAINSIGHT // TRAVEL·GUIDE·OS v2.4.1 // ALL SYSTEMS NOMINAL`

---

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.