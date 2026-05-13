"""
Main orchestrator with progressive save.
Saves catalog_data.json after EVERY successful extraction so we never lose work.
"""
import os
import json
import sys
from pathlib import Path
from ai_extractor import extract_quote, AllLLMsExhausted

QUOTES_DIR = Path("quotes")
OUTPUT_FILE = Path("catalog_data.json")
SUPPORTED_EXTS = {".pdf", ".xlsx", ".xls", ".docx", ".csv", ".txt"}


def load_existing() -> list:
    """Load existing catalog (if any) so we don't re-process."""
    if not OUTPUT_FILE.exists():
        return []
    try:
        return json.loads(OUTPUT_FILE.read_text())
    except Exception:
        return []


def save_progress(records: list):
    """Atomically save current progress."""
    OUTPUT_FILE.write_text(json.dumps(records, indent=2))


def scan_files() -> list:
    """Find all quote files in quotes/ folder."""
    if not QUOTES_DIR.exists():
        QUOTES_DIR.mkdir(exist_ok=True)
        return []
    
    all_files = []
    for proj_folder in QUOTES_DIR.iterdir():
        if not proj_folder.is_dir():
            continue
        for f in proj_folder.rglob("*"):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
                all_files.append((f, proj_folder.name))
    return all_files


def main():
    print("🚀 Starting quote extraction pipeline\n")
    
    # Validate at least one LLM is available
    if not os.getenv("LLAMA_API_KEY"):
        print("❌ LLAMA_API_KEY not set — cannot parse documents"); sys.exit(1)
    
    available_llms = []
    if os.getenv("GROQ_API_KEY"): available_llms.append("Groq")
    if os.getenv("OPENAI_API_KEY"): available_llms.append("OpenAI")
    if os.getenv("CLAUDE_API_KEY"): available_llms.append("Claude")
    
    if not available_llms:
        print("❌ No LLM keys found (need GROQ_API_KEY, OPENAI_API_KEY, or CLAUDE_API_KEY)")
        sys.exit(1)
    
    print(f"🤖 Available LLMs: {' → '.join(available_llms)}")
    
    # Load existing records to skip already-processed files
    existing = load_existing()
    done_files = {r["file"] for r in existing}
    print(f"📂 {len(existing)} record(s) already in catalog\n")
    
    all_files = scan_files()
    pending = [(f, p) for f, p in all_files if f.name not in done_files]
    print(f"📁 Found {len(all_files)} total files · {len(pending)} new to process\n")
    
    if not pending:
        print("✅ Nothing new to process — exiting cleanly")
        return
    
    records = list(existing)
    success_count = 0
    fail_count = 0
    exhausted = False
    
    try:
        for idx, (file_path, proj_folder) in enumerate(pending, 1):
            print(f"\n[{idx}/{len(pending)}] {proj_folder}/")
            try:
                record = extract_quote(file_path, proj_folder)
                if record:
                    records.append(record)
                    success_count += 1
                    # 💾 SAVE AFTER EVERY SUCCESS — protects against mid-run failures
                    save_progress(records)
                    print(f"     💾 Saved progress ({len(records)} total records)")
                else:
                    fail_count += 1
            except AllLLMsExhausted as e:
                print(f"\n🛑 {e}")
                print(f"   Stopping at {idx-1}/{len(pending)} files processed.")
                exhausted = True
                break
            except Exception as e:
                print(f"  ❌ Unexpected error: {str(e)[:200]}")
                fail_count += 1
                continue
    
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    
    finally:
        # Always save final state
        save_progress(records)
        print("\n" + "=" * 60)
        print(f"📊 SUMMARY")
        print("=" * 60)
        print(f"   ✅ Success:     {success_count}")
        print(f"   ❌ Failed:      {fail_count}")
        print(f"   📦 Total in catalog: {len(records)}")
        print(f"   💾 Saved to:    {OUTPUT_FILE}")
        if exhausted:
            print(f"\n   ⚠️  Stopped early due to LLM rate limits.")
            print(f"   🔄 Re-run later — already-processed files will be skipped.")
        print("=" * 60)
        
        # Exit cleanly (0) so workflow can still commit partial progress
        sys.exit(0)


if __name__ == "__main__":
    main()
