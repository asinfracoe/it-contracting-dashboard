# extractor/catalog_builder.py
# Updated for per-license records

import json
import re
from datetime import datetime
from config import (
    OUTPUT_FILE,
    ERROR_LOG_FILE,
    PROGRESS_FILE,
    MIN_VALID_PRICE,
    MAX_VALID_PRICE,
)


class CatalogBuilder:

    def __init__(self):
        self.records    = []
        self.errors     = []
        self.skipped    = []
        self.duplicates = []

    def add_records(self, records_list):
        """Add a list of records (one per line item)"""
        added = 0
        for record in records_list:
            if self.add_record(record):
                added += 1
        return added

    def add_record(self, record):
        if not record:
            return False
        issues = self._validate(record)
        if issues:
            self.skipped.append({
                "file":   record.get("file", "unknown"),
                "issues": issues,
            })
            return False
        cleaned = self._clean(record)
        if self._is_duplicate(cleaned):
            self.duplicates.append(cleaned.get("file", ""))
            return False
        self.records.append(cleaned)
        return True

    def add_error(self, filename, category, error_msg):
        self.errors.append({
            "file":     filename,
            "category": category,
            "error":    str(error_msg),
            "time":     datetime.now().isoformat(),
        })

    def _validate(self, record):
        issues = []
        if not record.get("cat"):
            issues.append("missing category")
        if not record.get("file"):
            issues.append("missing filename")
        if not record.get("service"):
            issues.append("missing service")

        price = record.get("unit_price", 0)
        try:
            price = float(price)
        except (TypeError, ValueError):
            issues.append(f"invalid price: {price}")
            return issues

        if price <= 0:
            issues.append("price is zero or negative")
        elif price > MAX_VALID_PRICE:
            issues.append(f"price too high: ${price:,.0f}")

        return issues

    def _clean(self, record):
        cleaned = dict(record)
        cleaned["vendor"]  = self._normalise_vendor(
            str(cleaned.get("vendor", "Unknown")).strip()
        )
        cleaned["cat"]     = str(cleaned.get("cat", "")).strip()
        cleaned["service"] = str(cleaned.get("service", "")).strip()
        cleaned["unit_price"] = round(
            float(cleaned.get("unit_price", 0)), 2
        )
        try:
            cleaned["year"] = int(cleaned.get("year", 2025))
        except (TypeError, ValueError):
            cleaned["year"] = 2025

        q = str(cleaned.get("quarter", "Q1")).upper().strip()
        if q not in ["Q1", "Q2", "Q3", "Q4"]:
            q = "Q1"
        cleaned["quarter"] = q

        # Remove internal fields
        for field in ["source", "confidence"]:
            cleaned.pop(field, None)

        return cleaned

    def _normalise_vendor(self, vendor):
        normalise_map = {
            "ntt data":       "NTT Data",
            "ntt docomo":     "NTT DOCOMO",
            "nttdata":        "NTT Data",
            "trendmicro":     "TrendMicro",
            "trend micro":    "TrendMicro",
            "knowbe4":        "KnowBe4",
            "know be4":       "KnowBe4",
            "shi":            "SHI",
            "pc connection":  "PC Connection",
            "cdw":            "CDW",
            "equinix":        "Equinix",
            "quest":          "Quest",
            "servicenow":     "ServiceNow",
            "service now":    "ServiceNow",
            "microsoft":      "Microsoft",
            "proquire":       "Proquire LLC",
            "ricoh":          "Ricoh",
            "honeywell":      "Honeywell",
        }
        v_lower = vendor.lower().strip()
        for key, canonical in normalise_map.items():
            if key in v_lower:
                return canonical
        return vendor

    def _is_duplicate(self, record):
        for existing in self.records:
            if (existing.get("file")    == record.get("file")
                    and existing.get("service") == record.get("service")
                    and existing.get("unit_price") == record.get("unit_price")):
                return True
        return False

    def deduplicate(self):
        seen   = set()
        unique = []
        for r in self.records:
            key = (
                f"{r.get('file','')}|"
                f"{r.get('service','')}|"
                f"{r.get('unit_price',0)}"
            )
            if key not in seen:
                seen.add(key)
                unique.append(r)
        removed = len(self.records) - len(unique)
        if removed > 0:
            print(f"   🔄 Removed {removed} duplicates")
        self.records = unique

    def save(self):
        self.deduplicate()
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved {len(self.records)} records → {OUTPUT_FILE}")
        if self.errors:
            with open(ERROR_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.errors, f, indent=2)
            print(f"⚠️  {len(self.errors)} errors → {ERROR_LOG_FILE}")
        stats = self.get_stats()
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        return OUTPUT_FILE

    def get_stats(self):
        by_category = {}
        by_vendor   = {}
        for r in self.records:
            cat = r.get("cat", "Unknown")
            ven = r.get("vendor", "Unknown")
            p   = r.get("unit_price", 0)
            if cat not in by_category:
                by_category[cat] = {
                    "count": 0, "prices": [],
                    "min": float("inf"), "max": 0
                }
            by_category[cat]["count"]  += 1
            by_category[cat]["prices"].append(p)
            by_category[cat]["min"] = min(by_category[cat]["min"], p)
            by_category[cat]["max"] = max(by_category[cat]["max"], p)
            if ven not in by_vendor:
                by_vendor[ven] = {"count": 0}
            by_vendor[ven]["count"] += 1
        return {
            "total_records":     len(self.records),
            "total_errors":      len(self.errors),
            "total_skipped":     len(self.skipped),
            "duplicates_removed": len(self.duplicates),
            "by_category":       by_category,
            "by_vendor":         by_vendor,
            "generated_at":      datetime.now().isoformat(),
        }

    def print_summary(self):
        stats = self.get_stats()
        print(f"\n{'='*60}")
        print(f"📊 EXTRACTION SUMMARY")
        print(f"{'='*60}")
        print(f"✅ Records: {stats['total_records']}")
        print(f"❌ Errors:  {stats['total_errors']}")
        print(f"⏭️  Skipped: {stats['total_skipped']}")
        print(f"\n📁 By Category:")
        for cat, data in stats["by_category"].items():
            prices = data.get("prices", [])
            avg    = sum(prices)/len(prices) if prices else 0
            print(
                f"  {cat[:30]:<30} "
                f"{data['count']:>3} items | "
                f"Avg: ${avg:>10,.2f}/unit"
            )
        print(f"\n🏢 By Vendor:")
        for ven, data in sorted(
            stats["by_vendor"].items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:10]:
            print(f"  {ven[:25]:<25} {data['count']:>3} items")
