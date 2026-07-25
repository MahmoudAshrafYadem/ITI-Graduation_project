
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
OpenRouter API ──► Generates technical answer with strict citations
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
Copy the example environment file:
```bash
cp .env.example .env
```
Add your OpenRouter API key to `.env` (this file is intentionally excluded from Git):
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

The application sends only the question and retrieved specification chunks to
OpenRouter. Embeddings, Qdrant, and reranking remain local.

### 4. Add 3GPP Specifications
Place your 3GPP PDF documents in the `data/` directory.

**We are using fixed file names** in the format: `TS_<TS_NUMBER>_Rel_<RELEASE>.pdf`

```text
data/
├── TS_36.331_Rel_17.pdf   (LTE RRC)
├── TS_36.214_Rel_17.pdf   (LTE Physical Layer)
└── TS_38.331_Rel_18.pdf   (NR RRC)
```
*(Download from the [3GPP FTP Archive](https://www.3gpp.org/ftp/Specs/archive))*

### Step 3: Enable Debug Mode (Optional)
Set `DEBUG_MODE=true` in `.env` to enable:
- Pipeline stage timing for every query
- Prompt statistics (character count, estimated tokens, chunk sizes)
- Per-stage performance metrics in the Streamlit sidebar
- Console output with a full pipeline report

### Performance Tuning
All retrieval and chunking parameters are configurable via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TOP_K` | `5` | Number of chunks returned to the LLM |
| `FETCH_MULTIPLIER` | `4` | Multiplier for chunks fetched from Qdrant before reranking |
| `CHUNK_SIZE` | `800` | Maximum tokens per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap tokens between chunks |
| `DEBUG_MODE` | `false` | Enable profiling dashboard and verbose logging |

### Configuration Reference
```env
# OpenRouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Debug / Profiling
DEBUG_MODE=true
WARN_INFERENCE_THRESHOLD=20
WARN_PROMPT_THRESHOLD=8000

# Retrieval
TOP_K=5
FETCH_MULTIPLIER=4

# Chunking
CHUNK_SIZE=800
CHUNK_OVERLAP=100
```

## 🔧 Chunking Strategy (Redesigned)

The chunker has been redesigned for 3GPP specifications to produce semantically coherent, narrowly scoped chunks.

### Chunk Types

| Type | Description |
|------|-------------|
| \section_content\ | General explanatory text within a section |
| \event_definition\ | Measurement event definitions (A1-A6, D1, etc.) |
| \sn1\ | ASN.1 grammar definitions |
| \	able\ | Extracted tables |
| \igure\ | Figure captions and descriptions |
| \nnex\ | Annex/appendix content |
| \history\ | Change/revision history, CR entries |
| \ormula\ | Mathematical formulas |

### Chunk Boundaries

A new chunk is created at:

* Section header transitions (major and minor)
* ASN.1 block boundaries (\-- TAG-START\, \-- ASN1START\)
* Figure boundaries
* Table boundaries
* Annex boundaries
* Change/revision history sections
* CR correction reports

### Target Sizes

* Average: 200--350 tokens
* Maximum: 500 tokens
* Overlap: 15--50 words

### Chunk ID Format

\TS_NUMBER.SECTION_NUMBER.CHUNK_TYPE.SEQUENCE
\
Example:

\36.331.5.5.4.4.event_definition.001
\
## ⚙️ Optimization Configuration

The pipeline is fully configurable via `.env` for performance tuning.

### Chunking

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `300` | Max tokens per chunk (target 200–350) |
| `CHUNK_OVERLAP` | `50` | Overlap tokens between chunks |
| `MAX_PROMPT_TOKENS` | `3000` | Stop adding chunks after this token budget |

### Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `TOP_K` | `3` | Final chunks sent to the LLM |
| `FETCH_MULTIPLIER` | `2` | Chunks retrieved from Qdrant before reranking |
| `REMOVE_DUPLICATES` | `true` | Deduplicate chunks from same page/section |
| `FILTER_ASN1` | `true` | Filter ASN.1 grammar and revision table chunks |
| `FILTER_CHANGE_HISTORY` | `true` | Filter CR history and change log chunks |

### Debug / Profiling

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG_MODE` | `false` | Enable profiling dashboard and verbose logging |
| `WARN_INFERENCE_THRESHOLD` | `20` | Warn if OpenRouter inference exceeds this many seconds |
| `WARN_PROMPT_THRESHOLD` | `3000` | Warn if prompt exceeds this many characters |

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

### Response format
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
│   ├── profiler.py        # Pipeline profiling & timing utility
│   ├── parser.py          # PyMuPDF text & table extraction
│   ├── chunker.py         # 3GPP section-aware splitting logic
│   ├── embeddings.py      # BGE local embedding wrapper
│   ├── retriever.py       # Local Qdrant connection & search
│   ├── reranker.py        # Cross-encoder relevance scoring
│   ├── llm.py             # OpenRouter client & strict system prompt
│   ├── rag.py             # Orchestrates the full RAG pipeline
│   ├── ingest.py          # CLI tool for loading PDFs
│   └── ui.py              # Streamlit Chat UI
├── data/                  # Place 3GPP PDFs here
├── vector_db/             # Auto-created local Qdrant database
├── .env                   # Your environment variables
├── .gitignore
├── requirements.txt
└── README.md
```


