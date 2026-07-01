"""
Catalog API — Sprint 3
Serves the product catalog with search, category filter, pagination.
Loads from catalog_data.json at startup and caches in memory.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

_CATALOG_PATHS = [
    Path(__file__).parent.parent.parent / "catalog_data.json",  # workspace root
    Path(__file__).parent.parent / "data" / "catalog_data.json",
]


@lru_cache(maxsize=1)
def _load_catalog() -> list:
    """Load catalog JSON once and cache in memory."""
    for path in _CATALOG_PATHS:
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                # Support both array root and {"items": [...]} wrapper
                if isinstance(raw, list):
                    return raw
                if isinstance(raw, dict):
                    for key in ("items", "catalog", "products", "data"):
                        if isinstance(raw.get(key), list):
                            return raw[key]
                    # Flat dict: {sku: {fields}}
                    return [{"sku": k, **v} for k, v in raw.items() if isinstance(v, dict)]
            except Exception:
                pass
    return []


def _matches(item: dict, search: str) -> bool:
    """Case-insensitive substring match across key fields."""
    haystack = " ".join(str(v) for v in [
        item.get("description", ""),
        item.get("sku", ""),
        item.get("vendor", ""),
        item.get("category", ""),
        item.get("part_number", ""),
    ]).lower()
    return search.lower() in haystack


@router.get("")
async def list_catalog(
    category: Optional[str] = Query(None, description="Filter by category"),
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    search: Optional[str] = Query(None, description="Full-text search across SKU/description/vendor"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """
    List catalog items with optional category/vendor filter and search.
    Supports pagination. Returns total count for UI pagination controls.
    """
    items = _load_catalog()

    # --- Filters ---
    if category:
        items = [i for i in items if i.get("category", "").lower() == category.lower()]
    if vendor:
        items = [i for i in items if vendor.lower() in i.get("vendor", "").lower()]
    if search and search.strip():
        items = [i for i in items if _matches(i, search.strip())]

    total = len(items)

    # --- Pagination ---
    start = (page - 1) * limit
    page_items = items[start: start + limit]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),  # ceiling division
    }


@router.get("/categories")
async def list_categories():
    """Return all distinct categories in the catalog."""
    items = _load_catalog()
    cats = sorted({i.get("category", "Other") for i in items if i.get("category")})
    return {"categories": cats}


@router.get("/vendors")
async def list_vendors():
    """Return all distinct vendors in the catalog."""
    items = _load_catalog()
    vendors = sorted({i.get("vendor", "") for i in items if i.get("vendor")})
    return {"vendors": vendors}


@router.get("/sku/{sku}")
async def get_by_sku(sku: str):
    """Look up a specific item by exact SKU (case-insensitive)."""
    items = _load_catalog()
    sku_lower = sku.lower()
    for item in items:
        if item.get("sku", "").lower() == sku_lower or item.get("part_number", "").lower() == sku_lower:
            return item
    return {"error": f"SKU '{sku}' not found in catalog", "found": False}
