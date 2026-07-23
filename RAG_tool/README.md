
# 📡 Telecom RAG Assistant

An engineering-grade Retrieval-Augmented Generation (RAG) system designed specifically for telecom engineers. It answers complex RF optimization and 5G/LTE Core questions directly from 3GPP specifications, providing strict citations to TS Number, Release, and Section.

Unlike generic RAG chatbots, this system is fine-tuned for the structure of 3GPP documents—handling messy PDF tables, preserving section hierarchies, and preventing LLM hallucinations.

## ✨ Key Engineering Features

- **No Docker Required:** Uses Qdrant in local embedded mode (`vector_db/qdrant_local`). It runs entirely inside Python and saves to disk.
- **Section-Aware Chunking:** Standard chunkers split formulas in half. This system detects 3GPP section headers (e.g., `5.5.4.4 Event A3`) and splits along boundaries, maintaining semantic context.
- **Table Extraction:** Automatically detects tables in PDFs (like CQI mappings or Timer values) and converts them to Markdown for the LLM to read cleanly.
- **Cross-Encoder Re-ranking:** Retrieves 4x the required chunks, then uses `bge-reranker-base` to score and filter only the most highly relevant context for the LLM.
- **Anti-Hallucination Prompt:** Strict system prompts force the LLM to say *"I cannot find this in the supplied specifications"* rather than guessing or making up section numbers.
- **Metadata Filtering:** Query strictly against specific TS numbers (e.g., `36.331`) or Releases (e.g., `17`) to avoid cross-spec confusion.
- **Streamlit Chat UI:** ChatGPT-style interface with sidebar filters and expandable citations.

## 🏗️ Architecture & Pipeline

```text
3GPP PDFs
   │
   ▼
Parser (PyMuPDF) ──► Extracts text, strips headers, converts tables to Markdown
   │
   ▼
Chunker ──► Splits text hierarchically by 3GPP section numbers
   │
   ▼
Embedder (BGE-large) ──► Converts chunks to dense vectors
   │
   ▼
Vector Store (Local Qdrant) ──► Stores vectors + metadata (TS, Release, Section, Page)
   │
   ▼
User Query ──► Embeds ──► Qdrant retrieves top 20 chunks
   │
   ▼
Reranker (BGE-reranker) ──► Scores & filters down to top 5 chunks
   │
   ▼
Gemini LLM ──► Generates technical answer with strict citations
```

## 🚀 Setup & Installation

### 1. Clone & Create Virtual Environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Copy the example environment file and add your Gemini API key:
```bash
cp .env.example .env
```
Edit `.env` and set your key:
```env
GEMINI_API_KEY=your_api_key_here
```
*(Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey))*

### 4. Add 3GPP Specifications
Place your 3GPP PDF documents in the `data/` directory.
```text
data/
├── TS36.331.pdf   (LTE RRC)
├── TS36.214.pdf   (LTE Physical Layer)
└── TS38.331.pdf   (NR RRC)
```
*(Download from the [3GPP FTP Archive](https://www.3gpp.org/ftp/Specs/archive))*

## 💻 Usage

### Step 1: Ingest PDFs into Local Vector Database
Run the ingestion CLI. This will parse the PDFs, chunk them, generate embeddings, and store them in Qdrant.

```bash
python -m app.ingest --all
```
*(Note: The first run will download the `BAAI/bge-large-en-v1.5` embedding model (~1.3GB).*

### Step 2: Start the Streamlit Chat UI
```bash
python -m streamlit run app/ui.py 
```
You can now interact with the assistant in your browser. Use the sidebar to filter by specific TS numbers or Releases.

*(Optional)* **Start the FastAPI Backend**
If you prefer to use the API instead of the Streamlit UI:
```bash
uvicorn app.main:app --reload --port 8000
```

### Example API Response (FastAPI)
```json
{
  "answer": "According to TS 36.331, Event A3 is triggered when a neighbor becomes offset better than the serving cell. The formula is: `Mn + Ofn + Ocn − Hys > Ms + Ofs + Ocs`",
  "references": [
    {
      "ts": "36.331",
      "release": "17",
      "section": "5.5.4.4",
      "page": 220,
      "score": 14.82
    }
  ],
  "chunks": [...]
}
```

## 📁 Project Structure

```text
telecom-rag/
├── app/
│   ├── config.py          # Environment variables & constants
│   ├── parser.py          # PyMuPDF text & table extraction
│   ├── chunker.py         # 3GPP section-aware splitting logic
│   ├── embeddings.py      # BGE local embedding wrapper
│   ├── retriever.py       # Local Qdrant connection & search
│   ├── reranker.py        # Cross-encoder relevance scoring
│   ├── llm.py             # Gemini API & strict system prompt
│   ├── rag.py             # Orchestrates the full RAG pipeline
│   ├── ingest.py          # CLI tool for loading PDFs
│   ├── main.py            # FastAPI web server
│   └── ui.py              # Streamlit Chat UI
├── data/                  # Place 3GPP PDFs here
├── vector_db/             # Auto-created local Qdrant database
├── .env                   # Your environment variables
├── .gitignore
├── requirements.txt
└── README.md
```


