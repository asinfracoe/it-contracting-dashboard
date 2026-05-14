"""
Pure local extractor — NO AI CALLS.
Uses heuristic regex extraction only.
Always succeeds (or skips gracefully) — never blocked by rate limits.
"""
from pathlib import Path
from file_processor import process_file
from heuristic_extractor import heuristic_extract


PROJECT_MAP = {
    "panasonic": "Panasonic",
    "idemia": "Idemia",
    "tenneco": "Tenneco",
}


def extract_quote(file_path: Path, project_folder: str) -> dict:
    """Extract a single quote — local-only, zero AI calls."""
    print(f"  📄 {file_path.name}")
    project = PROJECT_MAP.get(project_folder.lower(), project_folder.title())
    
    # Step 1: Parse the file locally (PDF/DOCX/XLSX)
    parsed = process_file(file_path)
    if not parsed["ok"]:
        print(f"     ❌ Parse failed: {parsed.get('error', 'unknown')[:100]}")
        return None
    
    text = parsed["text"]
    if len(text.strip()) < 50:
        print(f"     ⚠️ Empty/scanned document ({len(text)} chars)")
        return None
    
    method = parsed.get("method", "default")
    print(f"     📊 Parsed: {len(text):,} chars ({method})")
    
    # Step 2: Heuristic extraction — local only
    data = heuristic_extract(text, file_path.name)
    
    # Step 3: Build final record
    record = {
        "proj": project,
        "region": data["region"],
        "country": data["country"],
        "cat": data["category"],
        "vendor": data["vendor"],
        "file": file_path.name,
        "folder": project_folder.lower(),
        "services": data["services"],
        "price": data["price"],
        "year": data["year"],
        "quarter": data["quarter"],
        "_validated": False,  # Will be set to True after AI validation pass
    }
    
    # Quality check: must have at least vendor OR price OR services
    if record["vendor"] == "Unknown" and record["price"] == 0 and not record["services"]:
        print(f"     ⚠️ No useful data — skipping")
        return None
    
    # Show what we got
    confidence = []
    if record["vendor"] != "Unknown": confidence.append("vendor")
    if record["price"] > 0: confidence.append("price")
    if record["services"]: confidence.append(f"{len(record['services'])} services")
    
    print(f"     ✅ {record['vendor']} · ${record['price']:,} · {' + '.join(confidence)}")
    return record
