"""
extractor/main.py

Main orchestrator for the IT Contracting extraction pipeline.

Pipeline:
  1. Scan quotes/ folder for new files
  2. For each new file:
       a. Parse with LlamaParse (or local fallback)
       b. Run heuristic extraction (vendor, SKUs, qty, unit prices)
       c. Convert to flat per-line records + grouped per-file record
  3. Run flat records through CatalogBuilder (validation, dedup, stats)
  4. Run records through AI validator (optional, requires API key)
  5. Save dashboard JSON (grouped) + flat catalog JSON

Outputs:
  • catalog_data.json    — grouped per-file format (consumed by index.html dashboard)
  • catalog_flat.json    — flat per-line format (for analytics)
  • catalog_stats.json   — extraction statistics
  • catalog_errors.json  — extraction errors
  • validation_report.json — AI/structural validation report

Usage:
  python -m extractor.main                       # extract new files only
  python -m extractor.main --force               # re-extract all files
  python -m extractor.main --project panasonic   # only one project
  python -m extractor.main --skip-ai             # skip AI validation pass
  python -m extractor.main --quotes-dir custom/  # custom quotes directory
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Package-aware imports (works whether run as script or module) ──
try:
    from .ai_extractor import extract_quote
    from .catalog_builder import CatalogBuilder
    from .ai_validator import validate_records
    from .file_processor import is_supported
except ImportError:
    # Fallback when run as plain script (python main.py)
    from ai_extractor import extract_quote
    from catalog_builder import CatalogBuilder
    from ai_validator import validate_records
    from file_processor import is_supported


# ============================================================================
# CONFIGURATION
# ============================================================================

QUOTES_DIR    = Path("quotes")
OUTPUT_FILE   = Path("catalog_data.json")     # GROUPED format for dashboard
FLAT_FILE     = Path("catalog_flat.json")     # FLAT format for analytics
STATE_FILE    = Path(".extraction_state.json") # Tracks processed files

logger = logging.getLogger(__name__)


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def _file_key(file_path: Path, project_folder: str) -> str:
    """Unique key for a file across project folders."""
    return f"{project_folder}/{file_path.name}"


def load_existing_state() -> Tuple[List[Dict], List[Dict], Dict]:
    """
    Load existing grouped records, flat records, and processing state.
    Returns: (grouped_records, flat_records, state_dict)
    """
    grouped = []
    flat    = []
    state   = {"processed": [], "last_run": None}
    
    if OUTPUT_FILE.exists():
        try:
            grouped = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
            logger.info(f"📂 Loaded {len(grouped)} existing grouped records")
        except Exception as e:
            logger.warning(f"⚠️  Could not parse {OUTPUT_FILE}: {e}")
    
    if FLAT_FILE.exists():
        try:
            flat = json.loads(FLAT_FILE.read_text(encoding="utf-8"))
            logger.info(f"📂 Loaded {len(flat)} existing flat records")
        except Exception as e:
            logger.warning(f"⚠️  Could not parse {FLAT_FILE}: {e}")
    
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    return grouped, flat, state


def save_grouped(records: List[Dict]) -> None:
    """Save grouped records (dashboard format)."""
    OUTPUT_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def save_flat(records: List[Dict]) -> None:
    """Save flat per-line records."""
    FLAT_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def save_state(state: Dict) -> None:
    """Save processing state for incremental runs."""
    state["last_run"] = datetime.now().isoformat()
    STATE_FILE.write_text(
        json.dumps(state, indent=2, default=str),
        encoding="utf-8",
    )


# ============================================================================
# FILE SCANNING
# ============================================================================

def scan_files(
    quotes_dir: Path,
    project_filter: Optional[str] = None,
) -> List[Tuple[Path, str]]:
    """
    Scan the quotes directory and return list of (file_path, project_folder_name).
    
    Args:
        quotes_dir:     root quotes directory
        project_filter: if set, only return files in this project folder
    """
    if not quotes_dir.exists():
        quotes_dir.mkdir(parents=True, exist_ok=True)
        logger.warning(f"⚠️  Created empty quotes directory: {quotes_dir.absolute()}")
        return []
    
    if not quotes_dir.is_dir():
        logger.error(f"❌ {quotes_dir} is not a directory")
        return []
    
    all_files = []
    
    for proj_folder in sorted(quotes_dir.iterdir()):
        if not proj_folder.is_dir():
            continue
        if proj_folder.name.startswith((".", "_")):
            continue
        if project_filter and proj_folder.name.lower() != project_filter.lower():
            continue
        
        for f in proj_folder.rglob("*"):
            if not f.is_file():
                continue
            if f.name.startswith(("~$", ".")):
                continue
            if not is_supported(f):
                continue
            all_files.append((f, proj_folder.name))
    
    return all_files


# ============================================================================
# EXTRACTION
# ============================================================================

def process_file(
    file_path: Path,
    proj_folder: str,
) -> Tuple[List[Dict], Optional[Dict]]:
    """
    Process a single file. Returns (flat_records, grouped_record).
    """
    try:
        flat, grouped = extract_quote(file_path, proj_folder)
        return flat, grouped
    except Exception as e:
        logger.error(f"  ❌ Crash on {file_path.name}: {e}", exc_info=False)
        return [], None


def merge_with_existing(
    new_grouped: List[Dict],
    new_flat: List[Dict],
    existing_grouped: List[Dict],
    existing_flat: List[Dict],
    force: bool = False,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Merge new records with existing ones.
    
    Dedup strategy:
      - Grouped: dedup by (folder, file)
      - Flat:    dedup by (folder, file, sku, service)
    
    If `force=True`, new records replace existing ones for the same files.
    """
    # ── Identify which files we just processed ─────────────────
    new_file_keys = {(r["folder"], r["file"]) for r in new_grouped if r.get("file")}
    
    if force:
        # Drop existing records for any file we just re-processed
        merged_grouped = [
            r for r in existing_grouped
            if (r.get("folder"), r.get("file")) not in new_file_keys
        ]
        merged_flat = [
            r for r in existing_flat
            if (r.get("folder"), r.get("file")) not in new_file_keys
        ]
    else:
        merged_grouped = list(existing_grouped)
        merged_flat    = list(existing_flat)
    
    # Append new records
    merged_grouped.extend(new_grouped)
    merged_flat.extend(new_flat)
    
    # Final dedup pass
    seen_grouped = set()
    deduped_grouped = []
    for r in merged_grouped:
        key = (r.get("folder"), r.get("file"))
        if key not in seen_grouped:
            seen_grouped.add(key)
            deduped_grouped.append(r)
    
    seen_flat = set()
    deduped_flat = []
    for r in merged_flat:
        key = (
            r.get("folder"),
            r.get("file"),
            r.get("sku"),
            r.get("service"),
            r.get("unit_price"),
        )
        if key not in seen_flat:
            seen_flat.add(key)
            deduped_flat.append(r)
    
    return deduped_grouped, deduped_flat


# ============================================================================
# SUMMARY REPORTING
# ============================================================================

def print_summary(
    grouped_records: List[Dict],
    flat_records: List[Dict],
    success: int,
    fail: int,
    skipped: int,
) -> None:
    """Print a comprehensive summary of the extraction run."""
    
    # Aggregate stats
    by_project   = {}
    by_category  = {}
    by_vendor    = {}
    total_value  = 0
    total_lines  = 0
    sku_count    = 0
    confidence_sum = 0
    
    for r in grouped_records:
        proj = r.get("proj", "Unknown")
        cat  = r.get("cat", "Unknown")
        ven  = r.get("vendor", "Unknown")
        
        by_project[proj]  = by_project.get(proj, 0)  + 1
        by_category[cat]  = by_category.get(cat, 0)  + 1
        by_vendor[ven]    = by_vendor.get(ven, 0)    + 1
        
        total_value += r.get("price", 0)
        services = r.get("services", [])
        total_lines += len(services)
        sku_count += sum(1 for s in services if s.get("sku") and not s["sku"].startswith("UNKNOWN"))
        confidence_sum += r.get("confidence", 0)
    
    avg_conf = confidence_sum / len(grouped_records) if grouped_records else 0
    
    print("\n" + "=" * 70)
    print("📊  EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"   ✅ Success this run:    {success}")
    print(f"   ❌ Failed this run:     {fail}")
    print(f"   ⏭️  Skipped (existing):  {skipped}")
    print()
    print(f"   📦 Files in catalog:     {len(grouped_records)}")
    print(f"   🏷️  Line items:          {len(flat_records)}")
    print(f"   📜 Services nested:     {total_lines}  ({sku_count} with valid SKU)")
    print(f"   💰 Total catalog value: ${total_value:,.2f}")
    print(f"   📈 Avg confidence:      {avg_conf:.1f}%")
    print()
    
    if by_project:
        print("   📁 By Project:")
        for proj, count in sorted(by_project.items(), key=lambda x: -x[1]):
            print(f"      {proj[:25]:<25} {count:>4} files")
        print()
    
    if by_category:
        print("   🗂️  By Category:")
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            print(f"      {cat[:30]:<30} {count:>4} files")
        print()
    
    if by_vendor:
        print("   🏢 Top 10 Vendors:")
        top_vendors = sorted(by_vendor.items(), key=lambda x: -x[1])[:10]
        for ven, count in top_vendors:
            print(f"      {ven[:25]:<25} {count:>4} files")
        print()
    
    print(f"   💾 Dashboard data:  {OUTPUT_FILE}")
    print(f"   💾 Flat analytics:  {FLAT_FILE}")
    print("=" * 70)


# ============================================================================
# CLI
# ============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="IT Contracting quote extraction pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m extractor.main
  python -m extractor.main --force
  python -m extractor.main --project panasonic
  python -m extractor.main --skip-ai --skip-builder
  python -m extractor.main --quotes-dir /path/to/quotes
""",
    )
    parser.add_argument(
        "--quotes-dir", "-q",
        type=str,
        default=str(QUOTES_DIR),
        help=f"Directory containing project sub-folders of quotes (default: {QUOTES_DIR})",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Re-extract ALL files, replacing existing records",
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        default=None,
        help="Only process files in this project sub-folder (e.g., panasonic)",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip the AI validation pass (faster, no API calls)",
    )
    parser.add_argument(
        "--skip-builder",
        action="store_true",
        help="Skip the CatalogBuilder validation/dedup pass",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=5,
        help="Save progress to disk every N files (default: 5)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args()


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    """Main entry point. Returns exit code."""
    args = parse_args()
    
    # ── Logging setup ──────────────────────────────────────────
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    
    quotes_path = Path(args.quotes_dir)
    
    print("\n" + "=" * 70)
    print("🚀  IT CONTRACTING EXTRACTION PIPELINE")
    print("=" * 70)
    print(f"   📂 Quotes:        {quotes_path.absolute()}")
    print(f"   💾 Dashboard out: {OUTPUT_FILE.absolute()}")
    print(f"   💾 Flat out:      {FLAT_FILE.absolute()}")
    print(f"   🔄 Force rerun:   {args.force}")
    if args.project:
        print(f"   🎯 Project:       {args.project}")
    print(f"   🤖 AI validation: {'OFF' if args.skip_ai else 'ON'}")
    print(f"   🏗️  CatalogBuild:  {'OFF' if args.skip_builder else 'ON'}")
    
    # ── API key check ──────────────────────────────────────────
    has_llama = bool(os.environ.get("LLAMA_CLOUD_API_KEY"))
    has_ai    = bool(os.environ.get("XAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    print(f"   🔑 LlamaParse:    {'✅' if has_llama else '⚠️  not set (will use local fallback)'}")
    print(f"   🔑 AI validator:  {'✅' if has_ai else '⚠️  not set (validation will skip AI pass)'}")
    print("=" * 70 + "\n")
    
    # ── Load existing state ────────────────────────────────────
    existing_grouped, existing_flat, state = load_existing_state()
    
    if args.force:
        done_keys = set()
        logger.info("🔥 FORCE mode: re-processing all files")
    else:
        done_keys = {
            (r.get("folder"), r.get("file"))
            for r in existing_grouped
            if r.get("file")
        }
        logger.info(f"📂 {len(done_keys)} file(s) already in catalog")
    
    # ── Scan for files ─────────────────────────────────────────
    all_files = scan_files(quotes_path, args.project)
    
    pending = [
        (f, proj) for f, proj in all_files
        if (proj, f.name) not in done_keys
    ]
    skipped = len(all_files) - len(pending)
    
    # File type summary
    by_type = {}
    for f, _ in pending:
        ext = f.suffix.lower()
        by_type[ext] = by_type.get(ext, 0) + 1
    type_summary = ", ".join(f"{v} {k}" for k, v in sorted(by_type.items())) or "none"
    
    print(f"📁 {len(all_files)} total files · {skipped} already done · {len(pending)} new ({type_summary})\n")
    
    if not pending:
        print("✅ Nothing new to process")
        # Still run validation/save to refresh stats
        if not args.force and existing_grouped:
            print("ℹ️  Tip: use --force to re-extract everything\n")
        return 0
    
    # ── Process files ──────────────────────────────────────────
    new_flat:    List[Dict] = []
    new_grouped: List[Dict] = []
    success     = 0
    fail        = 0
    
    try:
        for idx, (file_path, proj_folder) in enumerate(pending, 1):
            print(f"\n[{idx}/{len(pending)}] {proj_folder}/{file_path.name}")
            
            flat_recs, grouped_rec = process_file(file_path, proj_folder)
            
            if grouped_rec:
                new_grouped.append(grouped_rec)
                new_flat.extend(flat_recs)
                success += 1
                
                # Periodic save (resilience against crashes)
                if success % args.save_every == 0:
                    merged_g, merged_f = merge_with_existing(
                        new_grouped, new_flat,
                        existing_grouped, existing_flat,
                        force=args.force,
                    )
                    save_grouped(merged_g)
                    save_flat(merged_f)
                    logger.info(f"     💾 Checkpoint saved ({len(merged_g)} files in catalog)")
            else:
                fail += 1
                logger.warning(f"     ⏭️  No data extracted from {file_path.name}")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user — saving progress before exit")
    
    # ── Merge with existing ────────────────────────────────────
    final_grouped, final_flat = merge_with_existing(
        new_grouped, new_flat,
        existing_grouped, existing_flat,
        force=args.force,
    )
    
    # ── CatalogBuilder pass (validation, dedup, normalisation) ──
    if not args.skip_builder and final_flat:
        print("\n🏗️  Running CatalogBuilder validation & dedup…")
        try:
            builder = CatalogBuilder()
            added = builder.add_records(final_flat)
            logger.info(f"   ✅ Validated {added} of {len(final_flat)} flat records")
            builder.save()  # writes to OUTPUT_FILE per config (catalog_flat.json)
            builder.print_summary()
            
            # Use cleaned/normalised flat records
            final_flat = builder.records
        except Exception as e:
            logger.error(f"❌ CatalogBuilder failed: {e}", exc_info=True)
    
    # ── AI validation pass (optional) ──────────────────────────
    if not args.skip_ai and final_grouped:
        print("\n🤖 Running AI / structural validation…")
        try:
            final_grouped = validate_records(
                final_grouped,
                batch_size=5,
                min_confidence=70,
                write_report=True,
                report_path="validation_report.json",
            )
        except Exception as e:
            logger.error(f"❌ AI validation failed: {e}", exc_info=True)
    
    # ── Final save ─────────────────────────────────────────────
    save_grouped(final_grouped)
    save_flat(final_flat)
    
    # Update state file
    state["processed"] = sorted({
        f"{r.get('folder')}/{r.get('file')}"
        for r in final_grouped
        if r.get("file")
    })
    save_state(state)
    
    # ── Print final summary ────────────────────────────────────
    print_summary(
        grouped_records = final_grouped,
        flat_records    = final_flat,
        success         = success,
        fail            = fail,
        skipped         = skipped,
    )
    
    # ── Exit code logic ────────────────────────────────────────
    # 0 = success, 1 = no records extracted, 2 = partial failure (>50% fail rate)
    if not final_grouped:
        return 1
    if pending and (fail / len(pending)) > 0.5:
        logger.warning(f"⚠️  Failure rate {fail / len(pending) * 100:.0f}% — exiting with code 2")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
