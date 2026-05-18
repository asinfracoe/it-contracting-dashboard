"""
Optional AI validation pass.
Uses xAI Grok (or any OpenAI-compatible API) to review extracted records
and correct obvious errors in category, line items, SKUs, etc.

To enable: set XAI_API_KEY or OPENAI_API_KEY environment variable.
"""
import os
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def _call_grok(prompt: str, model: str = "grok-2-latest") -> str:
    """Call xAI Grok API with the given prompt."""
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("XAI_API_KEY not set")
    
    try:
        import requests
    except ImportError:
        raise RuntimeError("`requests` library required for AI validation")
    
    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a meticulous IT contracting auditor. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _build_validation_prompt(batch: List[Dict]) -> str:
    """Construct a validation prompt for a batch of records."""
    return f"""You are auditing IT contracting quote extractions. Review each record and suggest corrections only when you are highly confident.

Check:
1. **Category** — does the assigned category match the services/vendor?
2. **Vendor** — is the vendor name correctly canonicalised?
3. **Line items** — for each line: does qty × unit_price ≈ line_total (within 1%)?
4. **SKUs** — do they look like real part numbers (alphanumeric, with dashes)?
5. **Country/Region** — consistent with file content?

Records to audit:
{json.dumps(batch, indent=2, ensure_ascii=False)}

Return STRICTLY this JSON format (no markdown, no commentary):
{{
  "corrections": [
    {{
      "file": "filename.pdf",
      "field": "cat",
      "current_value": "Other",
      "suggested_value": "Cybersecurity",
      "reason": "Services list contains Trend Micro and Apex One — clearly cybersecurity"
    }}
  ]
}}

If no corrections needed, return: {{"corrections": []}}
"""


def _apply_corrections(records: List[Dict], corrections: List[Dict]) -> List[Dict]:
    """Apply suggested corrections in-place and mark records as validated."""
    by_file = {r["file"]: r for r in records}
    applied = 0
    
    for c in corrections:
        fname = c.get("file")
        field = c.get("field", "")
        new_val = c.get("suggested_value")
        
        if fname not in by_file or new_val is None:
            continue
        
        rec = by_file[fname]
        
        # Handle nested fields like "lines[0].unit_price"
        if "." in field or "[" in field:
            try:
                # Simple parser for lines[idx].field
                if field.startswith("lines["):
                    idx_end = field.index("]")
                    idx = int(field[6:idx_end])
                    sub_field = field[idx_end + 2:]  # skip "]."
                    if 0 <= idx < len(rec.get("lines", [])):
                        rec["lines"][idx][sub_field] = new_val
                        applied += 1
                        logger.info(f"  ✏️ {fname}: lines[{idx}].{sub_field} → {new_val}")
            except (ValueError, IndexError, KeyError) as e:
                logger.warning(f"  ⚠️ Could not apply nested correction: {e}")
        else:
            # Simple top-level field
            if field in rec:
                old_val = rec[field]
                rec[field] = new_val
                applied += 1
                logger.info(f"  ✏️ {fname}: {field}: {old_val!r} → {new_val!r} ({c.get('reason', '')[:60]})")
    
    # Mark all touched records as validated
    for fname in {c.get("file") for c in corrections}:
        if fname in by_file:
            by_file[fname]["_validated"] = True
    
    logger.info(f"✅ Applied {applied} AI corrections")
    return records

def validate_unit_pricing(record: dict) -> tuple[bool, list]:
    """
    Validate that the record has proper unit pricing structure.
    Returns (is_valid, list_of_warnings).
    """
    warnings = []
    
    services = record.get('services', [])
    if not services:
        return False, ['No services in record']
    
    # Check if services are in NEW format (objects) vs OLD format (strings)
    if isinstance(services[0], str):
        warnings.append('Services are in legacy string format — should be objects with sku/qty/unitPrice')
        return False, warnings
    
    for i, svc in enumerate(services):
        if not isinstance(svc, dict):
            warnings.append(f'Service #{i+1} is not a dict')
            continue
        
        if not svc.get('name'):
            warnings.append(f'Service #{i+1}: missing "name" field')
        
        if not svc.get('sku'):
            warnings.append(f'Service #{i+1} ({svc.get("name", "?")}): missing SKU')
        
        qty = svc.get('qty', 0)
        unit_price = svc.get('unitPrice', 0)
        line_total = svc.get('lineTotal', 0)
        
        if qty <= 0:
            warnings.append(f'Service #{i+1} ({svc.get("name", "?")}): invalid quantity ({qty})')
        
        if unit_price <= 0:
            warnings.append(f'Service #{i+1} ({svc.get("name", "?")}): invalid unit price ({unit_price})')
        
        # Cross-check math: qty × unitPrice should ≈ lineTotal
        if qty > 0 and unit_price > 0 and line_total > 0:
            expected = qty * unit_price
            if abs(expected - line_total) / line_total > 0.05:
                warnings.append(
                    f'Service #{i+1} ({svc.get("name", "?")}): math mismatch — '
                    f'{qty} × ${unit_price} = ${expected:.2f}, but lineTotal = ${line_total}'
                )
    
    # Check sum of line totals vs total price
    line_sum = sum(s.get('lineTotal', 0) for s in services if isinstance(s, dict))
    total_price = record.get('price', 0)
    if total_price > 0 and line_sum > 0:
        deviation = abs(line_sum - total_price) / total_price
        if deviation > 0.10:
            warnings.append(
                f'Sum of line totals (${line_sum:.0f}) deviates from quote total '
                f'(${total_price}) by {deviation*100:.1f}%'
            )
    
    is_valid = len([w for w in warnings if 'invalid' in w or 'missing' in w]) == 0
    return is_valid, warnings



def validate_records(records: List[Dict], batch_size: int = 5) -> List[Dict]:
    """
    Validate records in batches via AI.
    Skips silently if no API key configured.
    """
    if not os.environ.get("XAI_API_KEY"):
        logger.info("XAI_API_KEY not set — skipping AI validation")
        return records
    
    if not records:
        return records
    
    logger.info(f"🤖 AI validating {len(records)} records in batches of {batch_size}...")
    
    all_corrections = []
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        
        # Slim down each record for the prompt (drop verbose fields)
        slim_batch = [
            {
                "file": r["file"],
                "vendor": r["vendor"],
                "cat": r["cat"],
                "services": r["services"],
                "lines": r.get("lines", [])[:5],  # first 5 lines only
                "price": r["price"],
                "country": r["country"],
                "region": r["region"],
            }
            for r in batch
        ]
        
        try:
            prompt = _build_validation_prompt(slim_batch)
            response = _call_grok(prompt)
            
            # Parse response (strip code fences if present)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()
            
            parsed = json.loads(response)
            corrections = parsed.get("corrections", [])
            all_corrections.extend(corrections)
            
            logger.info(f"  Batch {i // batch_size + 1}: {len(corrections)} suggestions")
        except Exception as e:
            logger.error(f"  ❌ Batch {i // batch_size + 1} failed: {e}")
            continue
    
    return _apply_corrections(records, all_corrections)
