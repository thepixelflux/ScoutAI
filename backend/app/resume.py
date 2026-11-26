"""Bounded, in-memory text extraction for resume uploads."""
from io import BytesIO
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile
from fastapi import HTTPException

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 30000
MAX_EXPANDED_BYTES = 10 * 1024 * 1024

def extract_resume(filename: str, data: bytes) -> str:
    if not data:
        raise HTTPException(422, 'The file is empty.')
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Resume must be 2 MB or smaller.')
    ext = PurePath(filename).suffix.lower()
    try:
        if ext == '.txt':
            if b'\x00' in data: raise ValueError('Not plain text')
            text = data.decode('utf-8-sig')
        elif ext == '.pdf':
            if not data.startswith(b'%PDF-'): raise ValueError('Invalid PDF signature')
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted: raise ValueError('Encrypted PDF')
            if len(reader.pages) > 20: raise ValueError('Too many pages')
            text = '\n'.join(page.extract_text(extraction_mode='plain') or '' for page in reader.pages)
        elif ext == '.docx':
            if not data.startswith(b'PK\x03\x04'): raise ValueError('Invalid DOCX signature')
            with ZipFile(BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 1000 or sum(x.file_size for x in infos) > MAX_EXPANDED_BYTES: raise ValueError('Document is too large when expanded')
                if 'word/document.xml' not in archive.namelist(): raise ValueError('Invalid DOCX structure')
            from docx import Document
            document = Document(BytesIO(data))
            parts = [paragraph.text for paragraph in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    parts.extend(cell.text for cell in row.cells)
            text = '\n'.join(parts)
        else:
            raise HTTPException(415, 'Use a PDF, DOCX, or UTF-8 TXT file.')
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, 'Could not read the resume. Use an unencrypted, valid file.') from exc
    text = text.strip()
    if not text: raise HTTPException(422, 'No selectable text found. Scanned images are not supported.')
    if len(text) > MAX_TEXT: raise HTTPException(422, 'Extracted text exceeds 30,000 characters.')
    return text
