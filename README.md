# Digital Asset Protection 

A next-generation, Pure AI-driven FastAPI service designed to protect media copyright and detect stolen, modified, or reposted official assets. By leveraging Google's **Gemini 2.5 Flash Multimodal AI**, this engine completely bypasses traditional mathematical hashing (like pHash) to semantically understand images, making it infinitely more resilient to cropping, lighting changes, camera angles, and advanced visual manipulation.

## 🚀 Features

- **FastAPI Core**: Highly performant asynchronous backend with auto-generated Swagger documentation.
- **Pure Semantic AI Detection**: Powered by Google's `google.genai` SDK and the `gemini-2.5-flash` model. It evaluates images like a human expert, ignoring superficial differences to focus on the true scene/context.
- **AI-Generated Modification Heuristics**: Gemini automatically reverse-engineers *how* a stolen image was modified (e.g. `["different angle", "cropped", "lighting changes"]`).
- **Quantified Similarity**: Returns a persistent 0-100 `similarity_score` and exact reasoning behind every AI decision.

---

## 🛠️ Installation & Setup

1. **Clone the repository** and navigate into the folder:
   ```bash
   git clone <your-repo-url>
   cd core-engine
   ```

2. **Set up a Python Virtual Environment** (Recommended):
   ```bash
   python -m venv .venv
   
   # Windows
   .\.venv\Scripts\activate
   
   # Mac/Linux
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Create a `.env` file in the root directory and add your Google Gemini API Key:
   ```env
   GEMINI_API_KEY="your_api_key_here"
   ```

5. **Start the Server**:
   ```bash
   uvicorn main:app
   ```

---

## 📖 API Endpoints

Once the server is running, access the interactive Swagger UI at **`http://127.0.0.1:8000/docs`**.

### `POST /register`
**Purpose**: Ingests an official asset to be protected.
**Process**: 
- Saves the file to `/assets`.
- Registers it into the local `db.json`.

### `POST /scan`
**Purpose**: Compares a suspicious/scraped image against the official database.
**Process**: 
- Saves the suspicious file to `/suspicious`.
- Sends the image payload + all registered assets directly to Google Gemini 2.5 Flash.
- **Returns**: A JSON payload with `match` (true/false), `confidence` (0-100 similarity score), the closest `matched_asset`, Gemini's text `reason`, and a list of `modifications` detected by the AI.

---

## 🧩 Architecture Integration

This engine is designed to sit between a **Web Crawler** and a **UI Dashboard**.

1. **The Crawler**: Scrapes social media and sends downloaded images to the `/scan` endpoint.
2. **The Database**: When `/scan` returns `{"match": true}`, the crawler logs the hit (and the confidence score) into a central SQL/NoSQL database.
3. **The Dashboard**: A frontend React/Vue application pulls from the central database to show a visual feed of pirated/stolen media to the moderation team.
