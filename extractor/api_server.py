"""
extractor/api_server.py

FastAPI backend exposing:
  • POST /api/extract           → extract a single quote file
  • POST /api/save-to-master    → commit extracted record to GitHub catalog
  • GET  /api/llama-health      → health check
  • GET  /api/master-data       → return current catalog_data.json

Deploy to: Render.com / Railway / Fly.io / your own VPS

Required env vars:
  LLAMA_CLOUD_API_KEY    → for parsing
  GITHUB_TOKEN           → PAT with 'repo' scope (for save-to-master)
  GITHUB_OWNER           → e.g. "asinfracoe"
  GITHUB_REPO            → e.g. "it-contracting-dashboard"
"""

import base64
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import your existing extractor modules
try:
    from .ai_extractor import extract_quote
    from .heuristic_extractor import heuristic_extract
    from .file_processor import is_supported, extract_text
except ImportError:
    from ai_extractor import extract_quote
    from heuristic_extractor import heuristic_extract
    from file_processor import is_supported, extract_text


# ============================================================================
# CONFIG
# ============================================================================

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "asinfracoe")
GITHUB_REPO  = os.environ.get("GITHUB_REPO",  "it-contracting-dashboard")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

CATALOG_PATH = "catalog_data.json"  # path within the repo


# ============================================================================
# APP
# ============================================================================

app = FastAPI(title="IT Contracting Extractor API", version="1.0.0")

# CORS — allow your GitHub Pages origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.github.io",
        "http://localhost:*",
        "http://127.0.0.1:*",
    ],
    allow_origin_regex=r"https://.*\.github\.io",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================================
# SCHEMAS
# ============================================================================

class ServiceLine(BaseModel):
    name: str
    sku: Optional[str] = ""
    qty: int = 1
    unitPrice: float = 0.0
    lineTotal: float = 0.0


class GroupedRecord(BaseModel):
    proj: str = "Unknown"
    region: str = "Global"
    country: str = ""
    cat: str = "Other"
    vendor: str = "Unknown"
    file: str
    folder: str = ""
    year: int = 2025
    quarter: str = "Q1"
    price: int = 0
    services: List[ServiceLine] = []
    confidence: int = 0


class SaveRequest(BaseModel):
    record:      GroupedRecord
    file_b64:    Optional[str] = None  # base64 of original quote file
    commit_msg:  Optional[str] = None


# ============================================================================
# HEALTH
# ============================================================================

@app.get("/api/llama-health")
async def health():
    """Health check for the dashboard's live status pill."""
    return {
        "status":     "ok",
        "llama_key":  bool(os.environ.get("LLAMA_CLOUD_API_KEY")),
        "github":     bool(GITHUB_TOKEN),
        "timestamp":  datetime.now().isoformat(),
    }


# ============================================================================
# EXTRACT ENDPOINT
# ============================================================================

@app.post("/api/extract")
async def extract_endpoint(
    file:    UploadFile = File(...),
    project: str        = Form("Unknown"),
):
    """
    Extract a single quote file using the full pipeline:
      LlamaParse → Heuristic → returns grouped record
    """
    if not is_supported(Path(file.filename)):
        raise HTTPException(400, f"Unsupported file type: {Path(file.filename).suffix}")
    
    # Save uploaded file to temp location
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
    
    try:
        logger.info(f"📥 Extracting {file.filename} ({len(content)} bytes)")
        
        # Run the full extraction pipeline
        flat_records, grouped = extract_quote(tmp_path, project)
        
        if not grouped:
            raise HTTPException(422, "Extraction returned no data")
        
        # Override file/folder fields with user-provided values
        grouped["file"]   = file.filename
        grouped["folder"] = project.lower() if project != "Unknown" else ""
        
        logger.info(
            f"✅ Extracted: {grouped.get('vendor')} · "
            f"{len(grouped.get('services', []))} services · "
            f"${grouped.get('price', 0):,} · "
            f"confidence {grouped.get('confidence', 0)}%"
        )
        
        return {
            "status":  "ok",
            "record":  grouped,
            "lines":   flat_records,
            "summary": {
                "vendor":     grouped.get("vendor"),
                "category":   grouped.get("cat"),
                "price":      grouped.get("price"),
                "services":   len(grouped.get("services", [])),
                "confidence": grouped.get("confidence", 0),
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Extraction failed for {file.filename}")
        raise HTTPException(500, f"Extraction error: {str(e)}")
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


# ============================================================================
# SAVE TO MASTER ENDPOINT
# ============================================================================

@app.post("/api/save-to-master")
async def save_to_master(req: SaveRequest):
    """
    Append an extracted record to the master catalog_data.json on GitHub.
    Optionally also upload the original quote file.
    """
    if not GITHUB_TOKEN:
        raise HTTPException(503, "GITHUB_TOKEN not configured on server")
    
    record_dict = req.record.dict()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # ── Step 1: Fetch current catalog_data.json ──────────────
        catalog, sha = await _get_github_file(client, CATALOG_PATH)
        if catalog is None:
            catalog = []
            sha     = None
        
        if not isinstance(catalog, list):
            raise HTTPException(500, "catalog_data.json is not a JSON array")
        
        # ── Step 2: Dedup check ──────────────────────────────────
        existing_keys = {(r.get("folder",""), r.get("file","")) for r in catalog}
        new_key = (record_dict.get("folder",""), record_dict.get("file",""))
        
        if new_key in existing_keys:
            # Replace existing record
            catalog = [
                r for r in catalog
                if (r.get("folder",""), r.get("file","")) != new_key
            ]
            action = "replaced"
        else:
            action = "added"
        
        catalog.append(record_dict)
        
        # ── Step 3: Upload original file (if provided) ───────────
        file_uploaded = False
        if req.file_b64 and record_dict.get("file") and record_dict.get("folder"):
            quote_path = f"quotes/{record_dict['folder']}/{record_dict['file']}"
            try:
                await _put_github_file(
                    client,
                    path     = quote_path,
                    content  = req.file_b64,
                    message  = f"📄 Upload {record_dict['file']}",
                    is_b64   = True,
                )
                file_uploaded = True
                logger.info(f"📤 Uploaded original file to {quote_path}")
            except Exception as e:
                logger.warning(f"Could not upload original file: {e}")
        
        # ── Step 4: Push updated catalog ─────────────────────────
        commit_msg = req.commit_msg or (
            f"📊 {action.capitalize()} {record_dict.get('vendor','Unknown')} "
            f"quote: {record_dict.get('file','')}"
        )
        
        new_content = json.dumps(catalog, indent=2, ensure_ascii=False)
        await _put_github_file(
            client,
            path     = CATALOG_PATH,
            content  = new_content,
            message  = commit_msg,
            sha      = sha,
            is_b64   = False,
        )
        
        logger.info(f"✅ Catalog updated: {action} record (now {len(catalog)} total)")
        
        return {
            "status":         "ok",
            "action":         action,
            "total_records":  len(catalog),
            "file_uploaded":  file_uploaded,
            "commit_message": commit_msg,
        }


# ============================================================================
# MASTER DATA ENDPOINT
# ============================================================================

@app.get("/api/master-data")
async def get_master_data():
    """Return current catalog_data.json from GitHub."""
    if not GITHUB_TOKEN:
        raise HTTPException(503, "GITHUB_TOKEN not configured")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        catalog, _ = await _get_github_file(client, CATALOG_PATH)
        return {
            "status":  "ok",
            "records": catalog or [],
            "count":   len(catalog) if catalog else 0,
        }


# ============================================================================
# GITHUB HELPERS
# ============================================================================

async def _get_github_file(client: httpx.AsyncClient, path: str):
    """Get a file from GitHub. Returns (decoded_content, sha) or (None, None)."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
    }
    params = {"ref": GITHUB_BRANCH}
    
    try:
        r = await client.get(url, headers=headers, params=params)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json()
        decoded = base64.b64decode(data["content"]).decode("utf-8")
        try:
            return json.loads(decoded), data["sha"]
        except json.JSONDecodeError:
            return decoded, data["sha"]
    except httpx.HTTPError as e:
        logger.error(f"GitHub get failed: {e}")
        return None, None


async def _put_github_file(
    client:  httpx.AsyncClient,
    path:    str,
    content: str,
    message: str,
    sha:     Optional[str] = None,
    is_b64:  bool = False,
):
    """Create or update a file on GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
    }
    
    if is_b64:
        encoded = content  # already base64
    else:
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    
    body = {
        "message": message,
        "content": encoded,
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha
    
    r = await client.put(url, headers=headers, json=body)
    r.raise_for_status()
    return r.json()


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=False)
