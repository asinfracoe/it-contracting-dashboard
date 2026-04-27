# extractor/ai_extractor.py
# Uses Groq (FREE) for AI extraction

import re
import json
import asyncio
import os
from groq import Groq
from config import (
    GROQ_API_KEY,
    LLAMA_API_KEY,
    LLAMA_TIER,
    LLAMA_EXPAND,
    KNOWN_VENDORS,
    KNOWN_SERVICES,
    MIN_VALID_PRICE,
    MAX_VALID_PRICE,
)

# Groq client
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# LlamaCloud client
llama = None
if LLAMA_API_KEY:
    try:
        from llama_cloud import AsyncLlamaCloud
        llama = AsyncLlamaCloud(api_key=LLAMA_API_KEY)
    except ImportError:
        print("LlamaCloud not installed — PDF parsing will use fallback")


class AIExtractor:

    def __init__(self):
        self.stats = {
            "llama_success":  0,
            "llama_failed":   0,
            "groq_success":   0,
            "groq_failed":    0,
            "regex_fallback": 0,
        }

    # ══════════════════════════════════════
    #  LLAMACLOUD — PDF PARSING
    # ══════════════════════════════════════
    async def parse_pdf_with_llama(self, file_bytes, filename):
        if not llama:
            return ""
        try:
            print(f"    📄 LlamaCloud: {filename[:40]}...")
            file_obj = await llama.files.create(
                file=(filename, file_bytes, "application/pdf"),
                purpose="parse"
            )
            result = await llama.parsing.parse(
                file_id=file_obj.id,
                tier=LLAMA_TIER,
                expand=LLAMA_EXPAND,
            )
            markdown = result.markdown_full or ""
            if markdown and len(markdown) > 100:
                self.stats["llama_success"] += 1
                print(f"    ✅ LlamaCloud: {len(markdown):,} chars")
                return markdown
            self.stats["llama_failed"] += 1
            return ""
        except Exception as e:
            self.stats["llama_failed"] += 1
            print(f"    ⚠️  LlamaCloud failed: {e}")
            return ""

    # ══════════════════════════════════════
    #  GROQ — FREE AI EXTRACTION
    # ══════════════════════════════════════
    def extract_with_groq(self, text, filename, category):
        if not groq_client:
            print("    ⚠️  Groq not configured — using regex")
            return self._empty_result()

        text_truncated = text[:6000]
        vendor_hints   = ", ".join(KNOWN_VENDORS[:15])
        service_hints  = ", ".join(KNOWN_SERVICES[:20])

        prompt = f"""You are an IT contract pricing analyst at PwC.
Extract per-unit/per-license pricing from this vendor quote document.

Filename: {filename}
Category: {category}
Known Vendors: {vendor_hints}
Known Services: {service_hints}

Document:
{text_truncated}

Extract EACH product or service as a SEPARATE item.
For each item find the UNIT PRICE which means the price per
one license, seat, or device. If only a total price exists,
divide it by the quantity to get the unit price.

Return ONLY this JSON with no other text:
{{
  "vendor": "Vendor Company Name",
  "category": "one of: Cybersecurity / Network & Telecom / Hosting / M365 & Power Platform / IdAM / Service Management (SNow) / MSP",
  "year": 2025,
  "quarter": "Q2",
  "currency": "USD",
  "confidence": "high",
  "line_items": [
    {{
      "service": "Exact Service or Product Name",
      "unit_price": 57.00,
      "quantity": 1000,
      "unit": "per license",
      "total_line_price": 57000.00,
      "description": "brief description"
    }}
  ]
}}

Rules:
unit_price must be a number only with no dollar signs or commas.
quantity is the number of licenses or seats.
unit describes what the unit price covers such as per license or per seat.
Return ONLY the JSON object and nothing else."""

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an IT contract pricing analyst. Return only valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1500,
            )
            raw    = response.choices[0].message.content.strip()
            result = self._parse_json_response(raw)

            if result and result.get("line_items"):
                self.stats["groq_success"] += 1
                print(f"    ✅ Groq: {len(result['line_items'])} items")
                return result

            self.stats["groq_failed"] += 1
            return self._empty_result()

        except Exception as e:
            self.stats["groq_failed"] += 1
            print(f"    ⚠️  Groq failed: {e}")
            return self._empty_result()

    # ══════════════════════════════════════
    #  JSON PARSER
    # ══════════════════════════════════════
    def _parse_json_response(self, raw_text):
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        try:
            fixed = re.sub(r',\s*}', '}', raw_text)
            fixed = re.sub(r',\s*]', ']', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        return None

    def _empty_result(self):
        return {
            "vendor":     "Unknown",
            "category":   "",
            "year":       2025,
            "quarter":    "Q1",
            "currency":   "USD",
            "confidence": "low",
            "line_items": [],
        }

    # ══════════════════════════════════════
    #  REGEX FALLBACKS
    # ══════════════════════════════════════
    def extract_price_regex(self, text):
        prices = []
        patterns = [
            r'(?:total|amount|price|quote|cost|value)'
            r'[:\s$]*(?:USD\s*)?([\d,]+(?:\.\d{1,2})?)',
            r'USD\s*([\d,]+(?:\.\d{1,2})?)',
            r'\$\s*([\d,]{4,}(?:\.\d{1,2})?)',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    n = float(m.group(1).replace(',', ''))
                    if MIN_VALID_PRICE <= n <= MAX_VALID_PRICE:
                        prices.append(n)
                except (ValueError, IndexError):
                    continue
        if prices:
            self.stats["regex_fallback"] += 1
            prices.sort(reverse=True)
            return prices[0]
        return 0

    def extract_vendor_regex(self, text, filename):
        text_lower  = text.lower()
        fname_lower = filename.lower()
        for vendor in KNOWN_VENDORS:
            if (vendor.lower() in text_lower
                    or vendor.lower() in fname_lower):
                return vendor
        return "Unknown"

    def extract_services_regex(self, text):
        found   = []
        t_lower = text.lower()
        for service in KNOWN_SERVICES:
            if service.lower() in t_lower:
                found.append(service)
        return list(set(found))

    def extract_year_regex(self, text, filename):
        years = re.findall(
            r'\b(202[0-9])\b', text + " " + filename
        )
        return int(max(years)) if years else 2025

    def extract_quarter_regex(self, text):
        months = re.findall(
            r'\b(jan|feb|mar|apr|may|jun|jul|'
            r'aug|sep|oct|nov|dec)\w*\b',
            text.lower()
        )
        qmap = {
            "jan": "Q1", "feb": "Q1", "mar": "Q1",
            "apr": "Q2", "may": "Q2", "jun": "Q2",
            "jul": "Q3", "aug": "Q3", "sep": "Q3",
            "oct": "Q4", "nov": "Q4", "dec": "Q4",
        }
        return qmap.get(months[0], "Q1") if months else "Q1"

    # ══════════════════════════════════════
    #  MASTER EXTRACTION
    # ══════════════════════════════════════
    async def extract_full(
        self, file_bytes, filename, category,
        text_from_processor=None
    ):
        print(f"\n  🔍 Extracting: {filename}")
        text = ""

        from pathlib import Path
        if Path(filename).suffix.lower() == ".pdf":
            llama_text = await self.parse_pdf_with_llama(
                file_bytes, filename
            )
            if llama_text:
                text = llama_text

        if not text and text_from_processor:
            text = text_from_processor

        if not text:
            print(f"    ❌ No text extracted")
            return []

        print(f"    🤖 Groq extraction...")
        extracted  = self.extract_with_groq(text, filename, category)
        line_items = extracted.get("line_items", [])
        vendor     = extracted.get("vendor", "Unknown")
        cat        = extracted.get("category", "") or category
        year       = extracted.get("year", 0)
        quarter    = extracted.get("quarter", "Q1")

        if vendor == "Unknown":
            vendor = self.extract_vendor_regex(text, filename)
        if not year or year < 2020:
            year = self.extract_year_regex(text, filename)
        if not quarter:
            quarter = self.extract_quarter_regex(text)

        if not line_items:
            total_price = self.extract_price_regex(text)
            services    = self.extract_services_regex(text)
            if total_price > 0:
                if services:
                    per_s
