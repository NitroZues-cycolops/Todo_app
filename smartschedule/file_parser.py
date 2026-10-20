"""
File parsing utilities for AI Planner.
Supports PDF and image file extraction.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


class FileParseError(Exception):
    """Raised when file parsing fails."""
    pass


def parse_file(file_path: str) -> Tuple[str, str]:
    """
    Parse a file and extract its content.

    Args:
        file_path: Path to the file to parse

    Returns:
        Tuple of (content, file_type)
        - content: Extracted text (for PDF/text) or base64 (for images)
        - file_type: One of "text", "pdf", "image", "unknown"

    Raises:
        FileParseError: If file cannot be parsed
    """
    path = Path(file_path)

    if not path.exists():
        raise FileParseError(f"File not found: {file_path}")

    # Check file size (10MB limit)
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > 10:
        raise FileParseError(f"File exceeds 10MB limit ({file_size_mb:.1f}MB)")

    mime_type, _ = mimetypes.guess_type(str(path))

    # PDF files
    if mime_type == "application/pdf" or str(path).lower().endswith(".pdf"):
        return _parse_pdf(file_path), "pdf"

    # Image files
    if mime_type and mime_type.startswith("image/"):
        return _parse_image(file_path), "image"

    # Plain text files
    if mime_type in ("text/plain", "text/markdown") or str(path).lower().endswith((".txt", ".md")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read(), "text"
        except Exception as e:
            raise FileParseError(f"Failed to read text file: {e}")

    raise FileParseError(f"Unsupported file type: {mime_type}")


def _parse_pdf(file_path: str) -> str:
    """Extract text from PDF file."""
    if pdfplumber is not None:
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                    text += "\n"
                return text.strip()
        except Exception as e:
            pass  # Fall back to pypdf

    if PdfReader is not None:
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
                text += "\n"
            return text.strip()
        except Exception as e:
            raise FileParseError(f"Failed to parse PDF: {e}")

    raise FileParseError("PDF parsing not available (install pypdf or pdfplumber)")


def _parse_image(file_path: str) -> str:
    """Convert image to base64 for vision models."""
    try:
        with open(file_path, "rb") as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode("utf-8")
    except Exception as e:
        raise FileParseError(f"Failed to read image: {e}")


def get_file_extension(file_path: str) -> str:
    """Get file extension without the dot."""
    return Path(file_path).suffix.lstrip(".").lower()


def validate_supported_file(file_path: str) -> bool:
    """Check if file type is supported for parsing."""
    try:
        parse_file(file_path)
        return True
    except FileParseError:
        return False
