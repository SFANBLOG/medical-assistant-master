"""
文件解析工具：支持 txt/md/pdf/docx/pptx 文件提取纯文本。
"""
import os
from pathlib import Path


def parse_file(file_path: str) -> str:
    """根据扩展名调用对应的解析器，返回纯文本。"""
    file_path = str(file_path)
    ext = Path(file_path).suffix.lower()

    if ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if ext == ".pdf":
        return _parse_pdf(file_path)

    if ext == ".docx":
        return _parse_docx(file_path)

    if ext == ".pptx":
        return _parse_pptx(file_path)

    # 兜底：尝试以文本读取
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _parse_pdf(file_path: str) -> str:
    """解析 PDF 文件。"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        texts = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                texts.append(txt)
        return "\n\n".join(texts)
    except ImportError:
        return "[PDF 解析需要 PyPDF2 库]"
    except Exception as e:
        return f"[PDF 解析失败: {e}]"


def _parse_docx(file_path: str) -> str:
    """解析 DOCX 文件。"""
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return "[DOCX 解析需要 python-docx 库]"
    except Exception as e:
        return f"[DOCX 解析失败: {e}]"


def _parse_pptx(file_path: str) -> str:
    """解析 PPTX 文件。"""
    try:
        from pptx import Presentation
        prs = Presentation(file_path)
        texts = []
        for slide in prs.slides:
            slide_texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        t = para.text.strip()
                        if t:
                            slide_texts.append(t)
            if slide_texts:
                texts.append("\n".join(slide_texts))
        return "\n\n---\n\n".join(texts)
    except ImportError:
        return "[PPTX 解析需要 python-pptx 库]"
    except Exception as e:
        return f"[PPTX 解析失败: {e}]"


def get_file_type(filename: str) -> str:
    """从文件名提取类型标识。"""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in ("txt", "md", "pdf", "docx", "pptx"):
        return ext
    return "txt"
