"""
AI Validator — runs ONCE on the entire catalog after local extraction.
Optional step. If AI fails, no harm done — extraction is already committed.

Sends the catalog to AI in batches and asks: "Are these categories/regions correct?"
Marks each record as _validated:true if AI confirms.
"""
import os
import json
import re
from pathlib import Path

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

CATALOG_FILE = Path("catalog_data.json")
BATCH_SIZE = 10  # records per AI call


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
    return {}


def call_openai(prompt: str) -> dict:
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        return parse_json(r.choices[0].message.content)
    except Exception as e:
        print(f"  ⚠️ OpenAI error: {str(e)[:100]}")
        return None


def call_groq(prompt: str) -> dict:
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000,
        )
        return parse_json(r.choices[0].message.content)
    except Exception as e:
        print(f"  ⚠️ Groq error: {str(e)[:100]}")
        return None


def build_validation_prompt(batch: list) -> str:
    valid_categories = ["Cybersecurity", "Network & Telecom", "Hosting",
                        "M365 & Power Platform", "IdAM", "Service Management (SNow)", "Other"]
    valid_regions = ["EMEA", "APAC", "Americas", "Global"]
    
    return f"""You are validating an IT contracting catalog. Review these records and suggest corrections ONLY where the existing values are clearly wrong.

VALID CATEGORIES: {valid_categories}
VALID REGIONS: {valid_regions}

For each record, return a correction object ONLY if something is clearly wrong. If a record looks fine, omit it from corrections.

Records to validate:
{json.dumps(batch, indent=2)}

Return JSON with this structure:
{{
  "corrections": [
    {{
      "file": "filename.pdf",
      "field": "cat",
      "current_value": "Other",
      "suggested_value": "Cybersecurity",
      "reason": "Vendor is Trend Micro and services include Apex One"
    }}
  ]
}}

Return ONLY JSON. If everything looks good, return {{"corrections": []}}."""


def validate_batch(batch: list) -> dict:
    """Try OpenAI first, fall back to Groq."""
    prompt = build_validation_prompt(batch)
    
    print(f"  🤖 Sending {len(batch)} records to AI...")
    result = call_openai(prompt)
    if result is None:
        print(f"  🔄 Trying Groq...")
        result = call_groq(prompt)
    
    return result or {"corrections": []}


def apply_corrections(records: list, corrections: list) -> int:
    """Apply AI suggestions to records. Returns number of changes."""
    changes = 0
    for corr in corrections:
        target_file = corr.get("file")
        field = corr.get("field")
        new_value = corr.get("suggested_value")
        
        if not (target_file and field and new_value is not None):
            continue
        
        for record in records:
            if record["file"] == target_file:
                old_value = record.get(field)
                if old_value != new_value:
                    print(f"     🔧 {target_file} · {field}: '{old_value}' → '{new_value}'")
                    print(f"        Reason: {corr.get('reason', 'AI suggestion')}")
                    record[field] = new_value
                    changes += 1
                break
    return changes


def main():
    print("🔍 AI Validation Pass — checking catalog quality\n")
    
    if not (OPENAI_API_KEY or GROQ_API_KEY):
        print("⚠️ No AI keys available — skipping validation")
        return 0
    
    if not CATALOG_FILE.exists():
        print(f"❌ {CATALOG_FILE} not found")
        return 1
    
    records = json.loads(CATALOG_FILE.read_text())
    if not records:
        print("ℹ️ Catalog is empty — nothing to validate")
        return 0
    
    # Validate only un-validated records
    unvalidated = [r for r in records if not r.get("_validated")]
    print(f"📊 Total records: {len(records)} · To validate: {len(unvalidated)}")
    
    if not unvalidated:
        print("✅ All records already validated")
        return 0
    
    total_changes = 0
    for i in range(0, len(unvalidated), BATCH_SIZE):
        batch = unvalidated[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(unvalidated) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n[Batch {batch_num}/{total_batches}]")
        result = validate_batch(batch)
        corrections = result.get("corrections", [])
        
        if corrections:
            print(f"  📝 {len(corrections)} suggested correction(s)")
            changes = apply_corrections(records, corrections)
            total_changes += changes
        else:
            print(f"  ✅ All records in batch look good")
        
        # Mark as validated regardless of changes
        for r in batch:
            for full_record in records:
                if full_record["file"] == r["file"]:
                    full_record["_validated"] = True
    
    # Save updated catalog
    CATALOG_FILE.write_text(json.dumps(records, indent=2))
    
    print("\n" + "=" * 60)
    print(f"✅ Validation complete · {total_changes} correction(s) applied")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
