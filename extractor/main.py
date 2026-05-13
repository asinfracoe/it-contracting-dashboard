"""
Main orchestrator: scans quotes/ folder, extracts every file, builds catalog_data.json
"""
import os
import json
from pathlib import Path
from ai_extractor import extract_quote

QUOTES_DIR = Path("quotes")
OUTPUT_FILE = Path("catalog_data.json")
SUPPORTED_EXTS = {".pdf", ".xlsx", ".xls", ".docx", ".csv", ".txt"}


def scan_quotes() -> list:
    """Walk quotes/ folder and process every supported file."""
    records = []
    if not QUOTES_DIR.exists():
        print(f"⚠️ {QUOTES_DIR} not found — creating it.")
        QUOTES_DIR.mkdir(exist_ok=True)
        return records
    
    project_folders = [d for d in QUOTES_DIR.iterdir() if d.is_dir()]
    print(f"📁 Found {len(project_folders)} project folder(s)")
    
    for proj_folder in project_folders:
        print(f"\n📂 Project: {proj_folder.name}")
        files = [f for f in proj_folder.rglob("*") 
                 if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
        print(f"   {len(files)} file(s) to process")
        
        for file_path in files:
            record = extract_quote(file_path, proj_folder.name)
            if record:
                records.append(record)
    
    return records


def merge_with_existing(new_records: list) -> list:
    """Preserve existing records; replace ones with same filename."""
    if not OUTPUT_FILE.exists():
        return new_records
    try:
        existing = json.loads(OUTPUT_FILE.read_text())
    except Exception:
        return new_records
    
    new_files = {r["file"] for r in new_records}
    kept = [r for r in existing if r.get("file") not in new_files]
    return kept + new_records


def main():
    print("🚀 Starting quote extraction pipeline\n")
    
    if not os.getenv("LLAMA_API_KEY"):
        print("❌ LLAMA_API_KEY not set"); return
    if not os.getenv("GROQ_API_KEY"):
        print("❌ GROQ_API_KEY not set"); return
    
    new_records = scan_quotes()
    print(f"\n✅ Extracted {len(new_records)} new records")
    
    if not new_records:
        print("ℹ️ No new records — exiting")
        return
    
    final = merge_with_existing(new_records)
    OUTPUT_FILE.write_text(json.dumps(final, indent=2))
    print(f"💾 Wrote {len(final)} total records → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
