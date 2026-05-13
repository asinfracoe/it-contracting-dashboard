"""
Main orchestrator — local-only extraction.
No AI calls during extraction = never gets blocked.
"""
import json
import sys
from pathlib import Path
from ai_extractor import extract_quote
from file_processor import is_supported

QUOTES_DIR = Path("quotes")
OUTPUT_FILE = Path("catalog_data.json")


def load_existing() -> list:
    if not OUTPUT_FILE.exists():
        return []
    try:
        return json.loads(OUTPUT_FILE.read_text())
    except Exception:
        return []


def save_progress(records: list):
    OUTPUT_FILE.write_text(json.dumps(records, indent=2))


def scan_files() -> list:
    if not QUOTES_DIR.exists():
        QUOTES_DIR.mkdir(exist_ok=True)
        return []
    
    all_files = []
    for proj_folder in QUOTES_DIR.iterdir():
        if not proj_folder.is_dir():
            continue
        for f in proj_folder.rglob("*"):
            if f.is_file() and is_supported(f):
                all_files.append((f, proj_folder.name))
    return all_files


def main():
    print("🚀 Starting LOCAL extraction pipeline (no AI calls)\n")
    print("📦 Parsers: PDF (PyMuPDF + pdfplumber), DOCX, XLSX, CSV, TXT\n")
    
    existing = load_existing()
    done_files = {r["file"] for r in existing}
    print(f"📂 {len(existing)} record(s) already in catalog")
    
    all_files = scan_files()
    pending = [(f, p) for f, p in all_files if f.name not in done_files]
    
    by_type = {}
    for f, _ in pending:
        ext = f.suffix.lower()
        by_type[ext] = by_type.get(ext, 0) + 1
    type_summary = ", ".join(f"{v} {k}" for k, v in sorted(by_type.items())) or "none"
    
    print(f"📁 Found {len(all_files)} total · {len(pending)} new to process ({type_summary})\n")
    
    if not pending:
        print("✅ Nothing new to process — exiting cleanly")
        return
    
    records = list(existing)
    success = 0
    fail = 0
    
    try:
        for idx, (file_path, proj_folder) in enumerate(pending, 1):
            print(f"\n[{idx}/{len(pending)}] {proj_folder}/")
            try:
                record = extract_quote(file_path, proj_folder)
                if record:
                    records.append(record)
                    success += 1
                    save_progress(records)
                    print(f"     💾 Saved ({len(records)} total)")
                else:
                    fail += 1
            except Exception as e:
                print(f"     ❌ Unexpected error: {str(e)[:200]}")
                fail += 1
                continue
    
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    
    finally:
        save_progress(records)
        print("\n" + "=" * 60)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"   ✅ Success:        {success}")
        print(f"   ❌ Failed:         {fail}")
        print(f"   📦 Total records:  {len(records)}")
        print(f"   💾 Saved to:       {OUTPUT_FILE}")
        print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    main()
