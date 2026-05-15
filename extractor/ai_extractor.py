"""
AI-orchestrated extractor that combines:
  1. LlamaParse (PDF/DOCX/XLSX → text)
  2. Heuristic extraction (vendor, price, services, line items)
  3. Optional AI validation/correction layer

Output: list of records ready for catalog_data.json
"""
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .heuristic_extractor import heuristic_extract

logger = logging.getLogger(__name__)


# ============================================================================
# LLAMAPARSE INTEGRATION
# ============================================================================

def parse_with_llama(file_path: Path) -> str:
    """
    Use LlamaParse to convert PDF/DOCX/XLSX/PPTX → markdown text.
    Falls back to plain-text reading for .txt and .csv.
    """
    suffix = file_path.suffix.lower()
    
    # Plain text files — read directly
    if suffix in (".txt", ".csv"):
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return ""
    
    # Use LlamaParse for everything else
    try:
        from llama_parse import LlamaParse
    except ImportError:
        logger.warning("llama_parse not installed — falling back to raw read")
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "").strip()
    if not api_key:
        logger.warning("LLAMA_CLOUD_API_KEY not set — falling back to raw read")
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    
    try:
        parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            verbose=False,
            language="en",
            num_workers=1,
        )
        documents = parser.load_data(str(file_path))
        text = "\n".join(doc.text for doc in documents)
        logger.info(f"LlamaParse extracted {len(text)} chars from {file_path.name}")
        return text
    except Exception as e:
        logger.error(f"LlamaParse failed for {file_path.name}: {e}")
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


# ============================================================================
# PROJECT FOLDER MAPPING
# ============================================================================

def detect_project(folder_name: str) -> str:
    """
    Map a folder name on disk to a canonical project name.
    Folders are typically lowercase ('panasonic') or capitalised ('Idemia').
    """
    folder_lower = folder_name.lower()
    mapping = {
        "panasonic": "Panasonic",
        "idemia": "Idemia",
        "tenneco": "Tenneco",
    }
    return mapping.get(folder_lower, folder_name.capitalize())


# ============================================================================
# SINGLE-FILE EXTRACTION
# ============================================================================

def extract_quote(file_path: Path, project_folder: str) -> Optional[Dict]:
    """
    Extract a single quote file into a record dict.
    Returns None on extraction failure.
    """
    logger.info(f"Extracting: {file_path.name}")
    
    # Step 1: Parse file → text
    text = parse_with_llama(file_path)
    if not text or len(text) < 50:
        logger.warning(f"Empty or too-short extraction for {file_path.name}")
        return None
    
    # Step 2: Run heuristic extraction
    try:
        data = heuristic_extract(text, file_path.name)
    except Exception as e:
        logger.error(f"Heuristic extraction crashed for {file_path.name}: {e}")
        return None
    
    # Step 3: Build the final record (matches dashboard schema)
    project = detect_project(project_folder)
    
    record = {
        "proj": project,
        "region": data["region"],
        "country": data["country"],
        "cat": data["category"],
        "vendor": data["vendor"],
        "file": file_path.name,
        "folder": project_folder,           # exact folder casing for GitHub URL
        "services": data["services"],
        "lines": data["lines"],             # SKU/qty/unit_price/line_total
        "price": data["price"],
        "year": data["year"],
        "quarter": data["quarter"],
        "_validated": False,
    }
    
    # Sanity checks
    if not record["services"]:
        logger.warning(f"No services found in {file_path.name}")
    if record["price"] <= 0:
        logger.warning(f"No price extracted from {file_path.name}")
    
    return record


# ============================================================================
# BATCH EXTRACTION
# ============================================================================

def extract_all_quotes(quotes_dir: Path) -> List[Dict]:
    """
    Walk the quotes/ directory and extract every quote file in every subfolder.
    
    Expected structure:
      quotes/
        ├── panasonic/
        │   ├── Cisco_PASCZ.pdf
        │   └── ...
        ├── Idemia/
        │   └── ...
        └── Tenneco/
            └── ...
    """
    if not quotes_dir.exists() or not quotes_dir.is_dir():
        logger.error(f"Quotes directory not found: {quotes_dir}")
        return []
    
    valid_extensions = {".pdf", ".docx", ".xlsx", ".xlsb", ".pptx", ".csv", ".txt"}
    records = []
    
    for project_folder in sorted(quotes_dir.iterdir()):
        if not project_folder.is_dir():
            continue
        if project_folder.name.startswith(".") or project_folder.name.startswith("_"):
            continue
        
        logger.info(f"📁 Processing project folder: {project_folder.name}")
        
        for file_path in sorted(project_folder.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in valid_extensions:
                continue
            if file_path.name.startswith("~$") or file_path.name.startswith("."):
                continue  # skip Office lock files & hidden
            
            try:
                record = extract_quote(file_path, project_folder.name)
                if record:
                    records.append(record)
                    logger.info(
                        f"  ✅ {file_path.name} → "
                        f"{record['vendor']} · ${record['price']:,} · "
                        f"{len(record['services'])} svcs · {len(record['lines'])} lines"
                    )
            except Exception as e:
                logger.error(f"  ❌ {file_path.name} crashed: {e}")
                continue
            
            # Be polite to LlamaParse API
            time.sleep(0.5)
    
    logger.info(f"📊 Total extracted: {len(records)} records")
    return records


# ============================================================================
# OPTIONAL: AI VALIDATION HOOK
# ============================================================================

def validate_with_ai(records: List[Dict]) -> List[Dict]:
    """
    Optional second pass: use Grok/GPT to flag and correct obvious mistakes.
    Currently a no-op pass-through; wire in your validator here if desired.
    """
    try:
        from .ai_validator import validate_records
        return validate_records(records)
    except ImportError:
        logger.info("ai_validator not configured — skipping AI validation")
        return records
    except Exception as e:
        logger.error(f"AI validation failed: {e}")
        return records


# ============================================================================
# MAIN ENTRY POINT (called by GitHub Action / extract.py)
# ============================================================================

def run_extraction(quotes_dir: str = "quotes", output_path: str = "catalog_data.json") -> int:
    """
    End-to-end extraction pipeline.
    Returns the number of records written.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    
    quotes_path = Path(quotes_dir)
    output_file = Path(output_path)
    
    logger.info(f"🚀 Starting extraction from {quotes_path.absolute()}")
    
    records = extract_all_quotes(quotes_path)
    
    if not records:
        logger.warning("⚠️ No records extracted — check that quotes/ has subfolders with files")
        return 0
    
    # Optional AI validation
    records = validate_with_ai(records)
    
    # Write JSON
    output_file.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    
    logger.info(f"✅ Wrote {len(records)} records to {output_file.absolute()}")
    
    # Print quick summary
    by_project = {}
    for r in records:
        by_project.setdefault(r["proj"], 0)
        by_project[r["proj"]] += 1
    logger.info(f"📊 Summary: {by_project}")
    
    line_count = sum(len(r.get("lines", [])) for r in records)
    sku_count = sum(1 for r in records for ln in r.get("lines", []) if ln.get("sku"))
    logger.info(f"📦 Line items extracted: {line_count} (with SKUs: {sku_count})")
    
    return len(records)


if __name__ == "__main__":
    import sys
    quotes_dir = sys.argv[1] if len(sys.argv) > 1 else "quotes"
    output = sys.argv[2] if len(sys.argv) > 2 else "catalog_data.json"
    count = run_extraction(quotes_dir, output)
    sys.exit(0 if count > 0 else 1)
