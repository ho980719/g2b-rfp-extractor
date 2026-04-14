# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two independent microservices and a logic utilities directory, all part of a Korean public procurement (나라장터/G2B) bid processing pipeline:

1. **Root service** (`main.py`) — HWP/HWPX-to-PDF converter
2. **`bid-sync/`** — 나라장터 bid data sync API (MySQL)
3. **`logic/`** — Standalone Python logic modules (used as Dify code nodes)

---

## Services

### 1. HWP Converter (`main.py`)

FastAPI service that downloads a file from a URL and converts it to PDF via LibreOffice.

**Run locally (Docker only — requires LibreOffice + H2Orestart):**
```bash
docker build -t hwp-converter .
docker run -d -p 8000:8000 -v /data001/convert:/tmp --name hwp-converter hwp-converter
```

**Endpoints:**
- `POST /convert` — body: `{"url": "https://..."}` — returns PDF file or `{"skipped": true, ...}`
- `GET /health`

**Key constraints:**
- Only accepts URLs from `ALLOWED_HOSTS = {"www.g2b.go.kr", "input.g2b.go.kr"}`
- Max file size: 50MB
- LibreOffice uses per-request isolated user profiles (under tmpdir) to avoid profile lock conflicts
- `.pdf` files are returned as-is without conversion; unsupported formats return a skip response instead of an error

### 2. Bid Sync API (`bid-sync/`)

FastAPI service that bulk-inserts 나라장터 bid notices into a MySQL `tb_bids` table.

**Run locally:**
```bash
cd bid-sync
# configure .env (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

**Run via Docker:**
```bash
cd bid-sync
docker build -t bid-sync .
docker run -d --name bid-sync -p 8001:8000 --env-file .env bid-sync
```

**Endpoints:**
- `POST /sync` — bulk upsert-style insert; skips existing `(bid_ntce_no, bid_ntce_ord)` pairs
- `GET /health`

**DB setup:** Tables are auto-created on startup via `Base.metadata.create_all()`.

---

## Architecture

### HWP Converter flow
`POST /convert` → validate URL domain → download file → detect file type (content-type → content-disposition → URL path) → if PDF return directly → if HWP/HWPX run LibreOffice subprocess with isolated profile → return PDF → cleanup tmpdir

### Bid Sync flow
`POST /sync` → filter items with `bidNtceNo` → batch-query existing keys → bulk insert only new records → commit or rollback

### Logic modules (`logic/`)
Standalone functions designed as **Dify workflow code nodes** — each file exports a `main()` function:

- `logic/new/공고목록조회.py` — parses raw 나라장터 API response, deduplicates by latest bid order (`bidNtceOrd`), classifies attached files as `rfp` / `exclude` / `unclear` using keyword matching
- `logic/context_set.py` — formats Dify retrieval results into a structured context string for LLM prompts
- `logic/파일분류.py` — (separate file classification utility)

### Bid data model (`bid-sync/models.py` — `tb_bids`)
Composite PK: `(bid_ntce_no, bid_ntce_ord)`. Key status fields use string enums:
- `file_status`: `PENDING` → `PROCESSING` → `DONE` / `FAILED` / `SKIPPED`
- `keyword_status`: `PENDING` → `DONE` / `FAILED`

The `raw_json` column stores the original 나라장터 API item JSON verbatim.