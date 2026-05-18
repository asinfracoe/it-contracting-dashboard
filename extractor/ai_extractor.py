"""
extractor/ai_extractor.py

AI-orchestrated extractor that combines:
  1. LlamaParse        (PDF/DOCX/XLSX → markdown text)
  2. Heuristic extract (vendor, price, SKUs, qty, unit prices)
  3. AI validation     (optional Grok/GPT correction layer)

Output formats:
  • FLAT records       → one record per line item (for CatalogBuilder)
  • GROUPED records    → one record per file with nested services (for dashboard)

Each FLAT record:
  {
    "file": "...", "proj": "...", "region": "...", "country": "...",
    "cat": "...", "vendor": "...", "service": "...", "sku": "...",
    "qty": 8, "unit_price": 3200.00, "line_total": 25600.00,
    "year": 2025, "quarter": "Q2", "folder": "panasonic",
    "confidence": 92
  }

Each GROUPED record (legacy/dashboard format):
  {
    "proj": "...", "region": "...", "country": "...", "cat": "...",
    "vendor": "...", "file": "...", "folder": "...", "year": 2025,
    "quarter": "Q2", "price": 25600,
    "services": [
      {"name": "...", "sku": "...", "qty": 8, "unitPrice": 3200, "lineTotal": 25600}
    ]
  }
"""

import os
import json
import time
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .heuristic_extractor import heuristic_extract

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

VALID_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xlsb", ".pptx", ".csv", ".txt"}

PROJECT_MAP = {
    "panasonic": "Panasonic",
    "idemia":    "Idemia",
    "tenneco":   "Tenneco",
}

# Cache LlamaParse output to avoid re-parsing on subsequent runs
CACHE_DIR = Path(".llama_cache")


# ============================================================================
# LLAMAPARSE INTEGRATION
# ============================================================================

def _file_hash(file_path: Path) -> str:
    """Compute a stable hash of a file's contents for caching."""
    h = hashlib.md5()
    h.update(file_path.name.encode())
    h.update(str(file_path.stat().st_size).encode())
    h.update(str(file_path.stat().st_mtime).encode())
    return h.hexdigest()[:16]


def _get_cached_text(file_path: Path) -> Optional[str]:
    """Return cached LlamaParse output if available, else None."""
    if not CACHE_DIR.exists():
        return None
    cache_file = CACHE_DIR / f"{_file_hash(file_path)}.md"
    if cache_file.exists():
        try:
            return cache_file.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def _save_cached_text(file_path: Path, text: str) -> None:
    """Cache LlamaParse output for future runs."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_file = CACHE_DIR / f"{_file_hash(file_path)}.md"
        cache_file.write_text(text, encoding="utf-8")
    except Exception as e:
        logger.debug(f"Cache write failed for {file_path.name}: {e}")


def parse_with_llama(file_path: Path, use_cache: bool = True) -> str:
    """
    Use LlamaParse to convert PDF/DOCX/XLSX/PPTX → markdown text.
    Falls back to plain-text reading for .txt and .csv.
    Caches results to avoid re-parsing.
    """
    suffix = file_path.suffix.lower()
    
    # ── Plain text files — read directly ─────────────────────────
    if suffix in (".txt", ".csv"):
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return ""
    
    # ── Check cache first ───────────────────────────────────────
    if use_cache:
        cached = _get_cached_text(file_path)
        if cached and len(cached) > 50:
            logger.info(f"  💾 Cache hit for {file_path.name}")
            return cached
    
    # ── Try LlamaParse ──────────────────────────────────────────
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
    
    # ── Invoke LlamaParse with retry on rate limit ──────────────
    max_retries = 3
    for attempt in range(max_retries):
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
            logger.info(f"  📄 LlamaParse: {len(text):,} chars from {file_path.name}")
            
            if use_cache:
                _save_cached_text(file_path, text)
            
            return text
        
        except Exception as e:
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "limit" in err_str:
                wait = 2 ** attempt * 5  # exponential backoff: 5s, 10s, 20s
                logger.warning(f"  ⏳ Rate limited, waiting {wait}s…")
                time.sleep(wait)
                continue
            
            logger.error(f"  ❌ LlamaParse failed for {file_path.name}: {e}")
            try:
                return file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return ""
    
    logger.error(f"  ❌ LlamaParse exhausted retries for {file_path.name}")
    return ""


# ============================================================================
# PROJECT FOLDER MAPPING
# ============================================================================

def detect_project(folder_name: str) -> str:
    """
    Map a folder name on disk to a canonical project name.
    Folders are typically lowercase ('panasonic') or capitalised ('Idemia').
    """
    folder_lower = folder_name.lower().strip()
    return PROJECT_MAP.get(folder_lower, folder_name.capitalize())


# ============================================================================
# LINE-ITEM TO RECORD CONVERSION
# ============================================================================

def _line_to_record(
    line: Dict,
    base: Dict,
) -> Optional[Dict]:
    """
    Convert a single line item dict from the heuristic extractor 
    into a complete catalog record. Returns None if the line is invalid.
    """
    sku        = str(line.get("sku", "")).strip()
    service    = str(line.get("service") or line.get("name") or "").strip()
    qty        = line.get("qty", 1)
    unit_price = line.get("unit_price", 0)
    line_total = line.get("line_total", 0)
    
    # ── Sanity & coercion ───────────────────────────────────────
    try:
        qty = max(1, int(qty or 1))
    except (TypeError, ValueError):
        qty = 1
    
    try:
        unit_price = float(unit_price or 0)
    except (TypeError, ValueError):
        unit_price = 0.0
    
    try:
        line_total = float(line_total or 0)
    except (TypeError, ValueError):
        line_total = 0.0
    
    # ── Auto-derive missing math ────────────────────────────────
    if line_total <= 0 and qty > 0 and unit_price > 0:
        line_total = round(qty * unit_price, 2)
    elif unit_price <= 0 and qty > 0 and line_total > 0:
        unit_price = round(line_total / qty, 2)
    elif qty <= 1 and unit_price > 0 and line_total > 0:
        qty = max(1, round(line_total / unit_price))
    
    # ── Reject obviously invalid lines ──────────────────────────
    if not service or unit_price <= 0:
        return None
    
    # ── Build the record ────────────────────────────────────────
    return {
        **base,
        "service":    service,
        "sku":        sku or "",
        "qty":        qty,
        "unit_price": round(unit_price, 2),
        "line_total": round(line_total, 2),
    }


# ============================================================================
# SINGLE-FILE EXTRACTION
# ============================================================================

def extract_quote(
    file_path: Path,
    project_folder: str,
) -> Tuple[List[Dict], Optional[Dict]]:
    """
    Extract a single quote file.
    
    Returns a tuple:
      (flat_records, grouped_record)
      
      flat_records:    one record per line item (for CatalogBuilder)
      grouped_record:  single nested record (for dashboard / debugging)
    """
    logger.info(f"🔎 Extracting: {file_path.name}")
    
    # ── Step 1: Parse file → text ────────────────────────────────
    text = parse_with_llama(file_path)
    if not text or len(text) < 50:
        logger.warning(f"  ⚠️  Empty or too-short extraction for {file_path.name}")
        return [], None
    
    # ── Step 2: Run heuristic extraction ────────────────────────
    try:
        data = heuristic_extract(text, file_path.name)
    except Exception as e:
        logger.error(f"  ❌ Heuristic extraction crashed: {e}")
        return [], None
    
    # ── Step 3: Build the base context ──────────────────────────
    project = detect_project(project_folder)
    
    base_context = {
        "file":       file_path.name,
        "folder":     project_folder,           # exact folder casing for GitHub URL
        "proj":       project,
        "region":     data.get("region", "Global"),
        "country":    data.get("country", ""),
        "cat":        data.get("category", "Other"),
        "vendor":     data.get("vendor", "Unknown"),
        "year":       data.get("year", 2025),
        "quarter":    data.get("quarter", "Q1"),
        "confidence": data.get("confidence", 70),
    }
    
    # ── Step 4: Convert lines → flat records ────────────────────
    lines = data.get("lines", []) or []
    flat_records = []
    
    for line in lines:
        rec = _line_to_record(line, base_context)
        if rec:
            flat_records.append(rec)
    
    # ── Step 5: Fallback if no lines but services exist ─────────
    if not flat_records and data.get("services"):
        # Distribute total price across services as a last resort
        services    = data["services"]
        total_price = float(data.get("price", 0))
        n           = len(services)
        
        if n > 0 and total_price > 0:
            est_unit = round(total_price / n, 2)
            for svc_name in services:
                rec = _line_to_record({
                    "service":    svc_name,
                    "sku":        "",
                    "qty":        1,
                    "unit_price": est_unit,
                    "line_total": est_unit,
                }, base_context)
                if rec:
                    rec["confidence"] = max(0, rec.get("confidence", 70) - 30)
                    flat_records.append(rec)
            logger.warning(
                f"  ⚠️  Fallback: distributed total ${total_price:,.0f} "
                f"across {n} services @ ${est_unit:,.2f} each"
            )
    
    # ── Step 6: Build grouped record (for dashboard / inspection) ──
    grouped_record = None
    if flat_records:
        grouped_record = {
            "proj":     base_context["proj"],
            "region":   base_context["region"],
            "country":  base_context["country"],
            "cat":      base_context["cat"],
            "vendor":   base_context["vendor"],
            "file":     base_context["file"],
            "folder":   base_context["folder"],
            "year":     base_context["year"],
            "quarter":  base_context["quarter"],
            "price":    round(sum(r["line_total"] for r in flat_records), 2),
            "services": [
                {
                    "name":      r["service"],
                    "sku":       r["sku"],
                    "qty":       r["qty"],
                    "unitPrice": r["unit_price"],
                    "lineTotal": r["line_total"],
                }
                for r in flat_records
            ],
            "confidence": base_context["confidence"],
        }
    
    # ── Sanity logging ───────────────────────────────────────────
    if not flat_records:
        logger.warning(f"  ⚠️  No line items extracted from {file_path.name}")
    else:
        skus_found = sum(1 for r in flat_records if r.get("sku"))
        logger.info(
            f"  ✅ {file_path.name} → "
            f"{base_context['vendor']} · "
            f"{len(flat_records)} lines ({skus_found} with SKU) · "
            f"${sum(r['line_total'] for r in flat_records):,.0f}"
        )
    
    return flat_records, grouped_record


# ============================================================================
# BATCH EXTRACTION
# ============================================================================

def extract_all_quotes(
    quotes_dir: Path,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Walk the quotes/ directory and extract every quote file.
    
    Expected structure:
      quotes/
        ├── panasonic/
        │   ├── Cisco_PASCZ.pdf
        │   └── ...
        ├── Idemia/
        │   └── ...
        └── Tenneco/
            └── ...
    
    Returns:
      (flat_records, grouped_records)
    """
    if not quotes_dir.exists() or not quotes_dir.is_dir():
        logger.error(f"❌ Quotes directory not found: {quotes_dir}")
        return [], []
    
    flat_all:    List[Dict] = []
    grouped_all: List[Dict] = []
    
    project_folders = sorted(
        f for f in quotes_dir.iterdir()
        if f.is_dir() and not f.name.startswith((".", "_"))
    )
    
    if not project_folders:
        logger.warning(f"⚠️  No project sub-folders found in {quotes_dir}")
        return [], []
    
    for project_folder in project_folders:
        logger.info(f"\n📁 Processing project folder: {project_folder.name}")
        
        files = sorted(
            f for f in project_folder.iterdir()
            if f.is_file()
            and f.suffix.lower() in VALID_EXTENSIONS
            and not f.name.startswith(("~$", "."))
        )
        
        if not files:
            logger.info(f"   (no extractable files)")
            continue
        
        for file_path in files:
            try:
                flat, grouped = extract_quote(file_path, project_folder.name)
                
                if flat:
                    flat_all.extend(flat)
                if grouped:
                    grouped_all.append(grouped)
            
            except Exception as e:
                logger.error(f"  ❌ {file_path.name} crashed: {e}", exc_info=True)
                continue
            
            # ── Be polite to the LlamaParse API ─────────────────
            time.sleep(0.3)
    
    logger.info(
        f"\n📊 Total extracted: "
        f"{len(flat_all)} line items across {len(grouped_all)} files"
    )
    return flat_all, grouped_all


# ============================================================================
# OPTIONAL AI VALIDATION HOOK
# ============================================================================

def validate_with_ai(records: List[Dict]) -> List[Dict]:
    """
    Optional second pass: use Grok/GPT to flag and correct obvious mistakes.
    Wires through to ai_validator.validate_records if available.
    """
    try:
        from .ai_validator import validate_records
        logger.info("🤖 Running AI validation pass…")
        return validate_records(records)
    except ImportError:
        logger.info("ℹ️  ai_validator not configured — skipping AI validation")
        return records
    except Exception as e:
        logger.error(f"❌ AI validation failed: {e}")
        return records


# ============================================================================
# CATALOG WRITING
# ============================================================================

def write_outputs(
    flat_records: List[Dict],
    grouped_records: List[Dict],
    output_path: str = "catalog_data.json",
    grouped_path: Optional[str] = "catalog_grouped.json",
) -> None:
    """
    Write both flat (per-line) and grouped (per-file) JSON outputs.
    
    The dashboard's index.html expects the GROUPED format under
    `catalog_data.json`, so by default we write the grouped version there
    and the flat version as a debug companion.
    """
    # Dashboard consumes the grouped (nested services) format
    dashboard_path = Path(output_path)
    dashboard_path.write_text(
        json.dumps(grouped_records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        f"💾 Wrote {len(grouped_records)} grouped records → {dashboard_path.absolute()}"
    )
    
    # Flat per-line records for analytics / catalog_builder consumption
    if grouped_path:
        flat_out = Path(grouped_path).with_name(
            Path(grouped_path).stem.replace("grouped", "flat") + ".json"
        )
        # If the user passed grouped_path explicitly, write FLAT records there
        flat_target = Path(grouped_path) if "flat" in grouped_path.lower() else flat_out
        flat_target.write_text(
            json.dumps(flat_records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            f"💾 Wrote {len(flat_records)} flat line records → {flat_target.absolute()}"
        )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def run_extraction(
    quotes_dir: str = "quotes",
    output_path: str = "catalog_data.json",
    flat_output_path: Optional[str] = "catalog_flat.json",
    use_catalog_builder: bool = True,
) -> int:
    """
    End-to-end extraction pipeline.
    
    Args:
        quotes_dir:           folder containing project sub-folders of quotes
        output_path:          where to write the dashboard-shaped grouped JSON
        flat_output_path:     where to write per-line flat JSON (or None to skip)
        use_catalog_builder:  if True, also run records through CatalogBuilder
                              for validation, dedup, and stats
    
    Returns:
        Number of grouped records written.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    
    quotes_path = Path(quotes_dir)
    
    logger.info(f"🚀 Starting extraction from {quotes_path.absolute()}")
    
    flat_records, grouped_records = extract_all_quotes(quotes_path)
    
    if not flat_records:
        logger.warning("⚠️  No records extracted — check folder structure & file types")
        return 0
    
    # ── Optional AI validation pass on grouped records ──────────
    grouped_records = validate_with_ai(grouped_records)
    
    # ── Optional CatalogBuilder pass (validation + dedup + stats) ──
    if use_catalog_builder:
        try:
            from .catalog_builder import CatalogBuilder
            
            logger.info("\n🏗️  Running through CatalogBuilder…")
            builder = CatalogBuilder()
            added = builder.add_records(flat_records)
            logger.info(f"   ✅ Added {added} of {len(flat_records)} records")
            
            # Save flat catalog (overwrites OUTPUT_FILE from config)
            builder.save()
            builder.print_summary()
            
            # Use the cleaned/deduped records for downstream output
            flat_records = builder.records
        
        except ImportError:
            logger.info("ℹ️  catalog_builder not available — skipping")
        except Exception as e:
            logger.error(f"❌ CatalogBuilder failed: {e}", exc_info=True)
    
    # ── Write outputs ───────────────────────────────────────────
    write_outputs(
        flat_records    = flat_records,
        grouped_records = grouped_records,
        output_path     = output_path,
        grouped_path    = flat_output_path,
    )
    
    # ── Final summary ───────────────────────────────────────────
    by_project = {}
    for r in grouped_records:
        by_project.setdefault(r["proj"], 0)
        by_project[r["proj"]] += 1
    
    sku_count = sum(
        1 for r in grouped_records
        for s in r.get("services", [])
        if s.get("sku")
    )
    total_lines = sum(len(r.get("services", [])) for r in grouped_records)
    total_value = sum(r.get("price", 0) for r in grouped_records)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ EXTRACTION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"📊 Files:        {len(grouped_records)}")
    logger.info(f"📦 Line items:   {total_lines} ({sku_count} with SKU)")
    logger.info(f"💰 Total value:  ${total_value:,.2f}")
    logger.info(f"📁 By project:   {by_project}")
    logger.info(f"{'='*60}\n")
    
    return len(grouped_records)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    quotes_dir = sys.argv[1] if len(sys.argv) > 1 else "quotes"
    output     = sys.argv[2] if len(sys.argv) > 2 else "catalog_data.json"
    flat_out   = sys.argv[3] if len(sys.argv) > 3 else "catalog_flat.json"
    
    count = run_extraction(
        quotes_dir       = quotes_dir,
        output_path      = output,
        flat_output_path = flat_out,
    )
    sys.exit(0 if count > 0 else 1)
