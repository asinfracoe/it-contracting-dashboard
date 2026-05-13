"""
Multi-format file processor.
Routes each file type to the best local parser → returns clean text + tables.
"""
import os
from pathlib import Path
from typing import Dict, Optional


# ============================================================================
# PDF — via PyMuPDF (fast, handles complex layouts, tables)
# ============================================================================

def extract_pdf(file_path: Path) -> Dict:
    """Extract text + tables from PDF using PyMuPDF."""
    import fitz  # PyMuPDF
    
    text_parts = []
    tables_text = []
    
    try:
        doc = fitz.open(str(file_path))
        
        for page_num, page in enumerate(doc, 1):
            # Extract plain text
            text = page.get_text("text")
            if text.strip():
                text_parts.append(f"--- Page {page_num} ---\n{text}")
            
            # Extract tables (PyMuPDF 1.23+ has built-in table detection)
            try:
                tables = page.find_tables()
                for t_idx, table in enumerate(tables):
                    rows = table.extract()
                    if rows:
                        table_md = "\n".join([" | ".join(str(c) if c else "" for c in row) for row in rows])
                        tables_text.append(f"--- Table p{page_num}.{t_idx+1} ---\n{table_md}")
            except Exception:
                pass  # Table extraction optional
        
        doc.close()
        
        full_text = "\n\n".join(text_parts)
        if tables_text:
            full_text += "\n\n=== TABLES ===\n\n" + "\n\n".join(tables_text)
        
        return {"text": full_text, "pages": len(doc), "ok": bool(full_text.strip())}
    
    except Exception as e:
        return {"text": "", "pages": 0, "ok": False, "error": str(e)}


# ============================================================================
# DOCX — via python-docx
# ============================================================================

def extract_docx(file_path: Path) -> Dict:
    """Extract text + tables from Word documents."""
    from docx import Document
    
    try:
        doc = Document(str(file_path))
        
        # Paragraphs
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        
        # Tables
        tables_text = []
        for t_idx, table in enumerate(doc.tables):
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(" | ".join(cells))
            if rows:
                tables_text.append(f"--- Table {t_idx+1} ---\n" + "\n".join(rows))
        
        full_text = "\n\n".join(paragraphs)
        if tables_text:
            full_text += "\n\n=== TABLES ===\n\n" + "\n\n".join(tables_text)
        
        return {"text": full_text, "pages": 1, "ok": bool(full_text.strip())}
    
    except Exception as e:
        return {"text": "", "pages": 0, "ok": False, "error": str(e)}


# ============================================================================
# XLSX / XLS — via openpyxl + pandas
# ============================================================================

def extract_xlsx(file_path: Path) -> Dict:
    """Extract all sheets from Excel as markdown-formatted text."""
    import pandas as pd
    
    try:
        # Read ALL sheets into a dict
        sheets = pd.read_excel(str(file_path), sheet_name=None, engine="openpyxl")
        
        text_parts = []
        for sheet_name, df in sheets.items():
            if df.empty:
                continue
            
            # Clean NaN → empty string for LLM readability
            df = df.fillna("").astype(str)
            
            # Convert to markdown-like table
            sheet_text = f"--- Sheet: {sheet_name} ---\n"
            sheet_text += df.to_string(index=False, max_rows=200, max_cols=20)
            text_parts.append(sheet_text)
        
        full_text = "\n\n".join(text_parts)
        return {"text": full_text, "pages": len(sheets), "ok": bool(full_text.strip())}
    
    except Exception as e:
        return {"text": "", "pages": 0, "ok": False, "error": str(e)}


# ============================================================================
# CSV — via pandas
# ============================================================================

def extract_csv(file_path: Path) -> Dict:
    import pandas as pd
    try:
        df = pd.read_csv(str(file_path), encoding_errors="replace").fillna("").astype(str)
        text = df.to_string(index=False, max_rows=500, max_cols=20)
        return {"text": text, "pages": 1, "ok": True}
    except Exception as e:
        return {"text": "", "pages": 0, "ok": False, "error": str(e)}


# ============================================================================
# TXT
# ============================================================================

def extract_txt(file_path: Path) -> Dict:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return {"text": text, "pages": 1, "ok": bool(text.strip())}
    except Exception as e:
        return {"text": "", "pages": 0, "ok": False, "error": str(e)}


# ============================================================================
# IMAGE OCR (optional — for scanned PDFs or images)
# ============================================================================

def extract_image(file_path: Path) -> Dict:
    """Extract text from images using Tesseract OCR."""
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(str(file_path))
        text = pytesseract.image_to_string(img)
        return {"text": text, "pages": 1, "ok": bool(text.strip())}
    except Exception as e:
        return {"text": "", "pages": 0, "ok": False, "error": str(e)}


# ============================================================================
# MAIN ROUTER
# ============================================================================

EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".xlsx": extract_xlsx,
    ".xls": extract_xlsx,
    ".xlsb": extract_xlsx,
    ".csv": extract_csv,
    ".txt": extract_txt,
    ".png": extract_image,
    ".jpg": extract_image,
    ".jpeg": extract_image,
}


def process_file(file_path: Path) -> Dict:
    """Route file to correct parser. Returns {text, pages, ok, error?}."""
    ext = file_path.suffix.lower()
    extractor = EXTRACTORS.get(ext)
    
    if not extractor:
        return {"text": "", "pages": 0, "ok": False, "error": f"Unsupported format: {ext}"}
    
    result = extractor(file_path)
    
    # If PDF parsing returned almost nothing, try OCR fallback
    if ext == ".pdf" and result["ok"] and len(result["text"].strip()) < 100:
        print(f"  ⚠️ PDF has little text — may be scanned. Consider OCR.")
    
    return result


def is_supported(file_path: Path) -> bool:
    return file_path.suffix.lower() in EXTRACTORS
