"""
文件解析工具：支持数百种主流文档 / 图片 / 文本 / 数据 / 代码类格式提取纯文本。

- 纯文本 / 标记 / 数据 / 代码类：直接 UTF-8 读取
- PDF：pypdf；无文本层的扫描件自动渲染成图片走 OCR
- DOCX：python-docx
- PPTX：python-pptx
- XLSX / XLSM：openpyxl
- HTML / HTM / XHTML：BeautifulSoup + lxml 去标签
- 图片 PNG/JPG/BMP/TIFF/WEBP/GIF：RapidOCR（rapidocr-onnxruntime，纯 ONNX 无需外部程序）
- DOC / XLS / PPT（旧版 OLE）：LibreOffice headless 转成新格式后再解析

扩展名白名单见 ALLOWED_EXTENSIONS；不在白名单内的格式会被上传接口直接拒绝。
注意：解析器缺依赖或确实无文字时返回空串 / 抛错，绝不把占位文字写进知识库。
"""
import re
from collections import Counter
from pathlib import Path

# 有效字符：中日韩统一表意文字 + 字母 + 数字
_MEANINGFUL_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ffA-Za-z0-9]")


def _has_meaningful_text(text: str, min_chars: int = 20, min_ratio: float = 0.3) -> bool:
    """
    判断提取到的文本是否『有实际内容』。

    部分 PDF（扫描件、字体缺失、坏 OCR 文本层）会吐出一堆无意义符号（如 '····'、
    '□□□'）。只看长度会把这些当成正文返回，所以额外校验有效字符占比。
    """
    stripped = (text or "").strip()
    if len(stripped) < min_chars:
        return False
    meaningful = len(_MEANINGFUL_RE.findall(stripped))
    if meaningful < min_chars:
        return False
    return meaningful / len(stripped) >= min_ratio


# ---------------------------------------------------------------------------
# 扩展名白名单（主流文档 / 图片 / 文本 / 数据 / 代码 / 标记类格式）
# ---------------------------------------------------------------------------
# 纯文本 / 标记 / 数据 / 代码 / Web 类
_TEXT_EXTS = frozenset(
    {
        # 纯文本 & 标记语言
        "txt", "text", "md", "markdown", "mdown", "mkd", "rst", "adoc", "asciidoc",
        "tex", "latex", "org", "creole", "rtf",
        # 数据 & 配置
        "csv", "tsv", "json", "jsonl", "ndjson", "xml", "xsl", "xslt", "yaml", "yml",
        "toml", "ini", "cfg", "conf", "config", "properties", "env", "plist", "dat",
        "tab", "fixed", "dtd", "xsd", "rng",
        # Web（html 系列有专用解析器，见下方 _DEDICATED_EXTS）
        "vue", "ejs", "haml", "slim", "twig", "jsp",
        "asp", "aspx",
        # 日志 & 差异
        "log", "out", "err", "trace", "stack", "diff", "patch",
        # 代码（常见 + 小众语言，便于把源码也纳入知识库）
        "py", "pyw", "js", "jsx", "mjs", "cjs", "ts", "tsx", "java", "kt", "kts",
        "scala", "sc", "go", "rs", "c", "h", "cc", "cpp", "cxx", "hpp", "hxx", "cs",
        "vb", "fs", "f", "f90", "f95", "for", "pas", "pp", "m", "mm", "swift", "groovy",
        "rb", "rake", "php", "php3", "php4", "php5", "pl", "pm", "lua", "sh", "bash",
        "zsh", "fish", "ps1", "psm1", "psd1", "bat", "cmd", "r", "rdata", "jld", "dart",
        "ex", "exs", "erl", "hrl", "el", "clj", "cljs", "cljc", "edn", "ml", "mli",
        "mll", "mly", "nim", "cr", "coffee", "sql", "ddl", "dml", "graphql", "gql",
        "proto", "thrift", "idl", "sol", "vy", "ahk", "au3", "tcl", "tk", "abap", "cob",
        "cobol", "cbl", "jcl", "rexx", "awk", "sed", "vim", "nano", "gitignore",
        "dockerfile", "makefile", "cmake", "bazel", "bzl", "build", "gradle", "pom",
        "ipynb", "editorconfig", "gitattributes", "gitmodules", "npmrc", "yarnrc",
        "pypirc", "condarc", "bashrc", "zshrc", "profile", "bash_profile", "nginx",
        "httpd", "service", "timer", "socket", "feature", "story", "less", "scss",
        "sass", "styl", "css", "scm", "lisp", "lsp", "rkt", "scrbl", "wolf", "fun",
        "sig", "sml", "ng",
    }
)

# 二进制 / 富格式文档类（有专用解析器，解析优先级高于纯文本分支）
_DEDICATED_EXTS = frozenset(
    {"pdf", "docx", "pptx", "xlsx", "xlsm", "html", "htm", "xhtml", "shtml"}
)

# 图片类（走 OCR 提取文字，适合扫描件、报告单、处方截图等）
_IMAGE_EXTS = frozenset({"png", "jpg", "jpeg", "jpe", "jfif", "bmp", "gif", "tif", "tiff", "webp"})

# 旧版 Office（OLE 二进制，需 LibreOffice headless 转换为新格式后再解析）
_LEGACY_OFFICE_EXTS = frozenset({"doc", "xls", "ppt"})

# 白名单全集
ALLOWED_EXTENSIONS = _TEXT_EXTS | _DEDICATED_EXTS | _IMAGE_EXTS | _LEGACY_OFFICE_EXTS


def get_ext(filename: str) -> str:
    """返回小写扩展名（不含点），如 'pdf'；无扩展名返回 ''。"""
    return Path(filename).suffix.lower().lstrip(".")


def is_allowed(filename: str) -> bool:
    """该文件扩展名是否在支持白名单内。"""
    return get_ext(filename) in ALLOWED_EXTENSIONS


def get_file_type(filename: str) -> str:
    """从文件名提取类型标识（用于 documents.file_type 字段）。"""
    ext = get_ext(filename)
    if ext in ("txt", "text", "md", "markdown", "mdown", "mkd"):
        return "md"
    if ext in ("pdf", "docx", "pptx", "xlsx", "xlsm", "doc", "xls", "ppt"):
        return ext
    if ext in ("html", "htm", "xhtml", "shtml"):
        return "html"
    if ext in _IMAGE_EXTS:
        return "image"
    return "txt"


def parse_file(file_path: str) -> str:
    """根据扩展名调用对应的解析器，返回纯文本。"""
    file_path = str(file_path)
    ext = get_ext(file_path)

    if ext == "pdf":
        return _parse_pdf(file_path)
    if ext == "docx":
        return _parse_docx(file_path)
    if ext == "pptx":
        return _parse_pptx(file_path)
    if ext in ("xlsx", "xlsm"):
        return _parse_xlsx(file_path)
    if ext in ("html", "htm", "xhtml", "shtml"):
        return _parse_html(file_path)
    if ext in _IMAGE_EXTS:
        return _parse_image(file_path)
    if ext == "doc":
        return _parse_legacy_office(file_path, "docx")
    if ext == "xls":
        return _parse_legacy_office(file_path, "xlsx")
    if ext == "ppt":
        return _parse_legacy_office(file_path, "pptx")

    # 其余白名单内格式：按纯文本读取（代码 / 数据 / 标记 / 日志等）
    if ext in _TEXT_EXTS:
        return _read_text(file_path)

    # 白名单内但无专用解析器（理论上不会到达）：兜底按文本读取
    return _read_text(file_path)


# ---------------------------------------------------------------------------
# OCR（RapidOCR，懒加载并缓存引擎）
# ---------------------------------------------------------------------------
_OCR_ENGINE = None


def _get_ocr_engine():
    """懒加载并缓存 OCR 引擎（首次调用会加载 ONNX 模型，较慢）。"""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def _recognize_image(file_path: str) -> str:
    """对图片做 OCR，返回按行拼接的文本；图中无文字时返回空串。"""
    engine = _get_ocr_engine()          # 缺库时抛 ImportError，由调用方转成明确提示
    result, _ = engine(str(file_path))
    if not result:
        return ""
    lines = []
    for item in result:
        text = (item[1] or "").strip() if len(item) > 1 else ""
        if text:
            lines.append(text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 各类解析器
# ---------------------------------------------------------------------------
def _read_text(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _parse_image(file_path: str) -> str:
    """解析图片（OCR 提取文字）。

    缺 OCR 库或识别失败时抛 RuntimeError（由上传接口转成『解析失败』并标记 failed），
    避免把占位文字当成正文写进知识库。
    """
    try:
        return _recognize_image(file_path)
    except ImportError:
        raise RuntimeError(
            "图片 OCR 需要可选依赖：pip install -r backend/requirements-ocr.txt "
            "（或用 --build-arg INSTALL_OCR=true 重建镜像）"
        )
    except Exception as e:
        raise RuntimeError(f"图片 OCR 失败: {e}")


def _parse_pdf(file_path: str) -> str:
    """解析 PDF：先取文本层；若无文本层（扫描件）则渲染成图片走 OCR。"""
    pages = parse_pdf_pages(file_path)
    return "\n\n".join(t for _, t in pages)


# ---------------------------------------------------------------------------
# PDF 分页解析：保留页边界，供页眉页脚清洗与后续溯源使用
# ---------------------------------------------------------------------------
def parse_pdf_pages(file_path: str) -> list[tuple[int, str]]:
    """
    逐页解析 PDF，返回 [(page_no, page_text)]，page_no 从 1 开始。

    解析顺序：
    1. PyMuPDF（对多栏排版、CID 字体的还原质量优于 pypdf，优先使用）；
    2. pypdf / PyPDF2；
    3. 前两者都拿不到有效文本（扫描件、字体缺失）→ 逐页渲染成图片走 OCR；
    4. 仍无有效文本时返回空列表（避免把乱码 / '····' 写进知识库）。
    """
    fitz_pages = _pdf_pages_by_pymupdf(file_path)
    if _has_meaningful_text(_join_pages(fitz_pages)):
        return fitz_pages

    pypdf_pages = _pdf_pages_by_pypdf(file_path)
    if _has_meaningful_text(_join_pages(pypdf_pages)):
        return pypdf_pages

    # 无文本层 / 解析失败 → 渲染成图片再 OCR
    try:
        ocr_pages = _ocr_pdf_pages_list(file_path)
        if any(t.strip() for _, t in ocr_pages):
            return ocr_pages
    except Exception:
        pass

    # 都不可用：返回字符数更多的一份，由上层依据 PDF_MIN_TEXT_CHARS 判定
    if _join_pages(fitz_pages) or _join_pages(pypdf_pages):
        return fitz_pages if len(_join_pages(fitz_pages)) >= len(_join_pages(pypdf_pages)) else pypdf_pages
    return []


def _join_pages(pages: list[tuple[int, str]]) -> str:
    """把分页文本拼成整篇（仅用于质量判定与兜底拼接）。"""
    return "\n\n".join(t for _, t in pages or [])


def _pdf_pages_by_pymupdf(file_path: str) -> list[tuple[int, str]]:
    """用 PyMuPDF 逐页提取文本层。"""
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf      # 旧版兼容
        except ImportError:
            return []
    try:
        doc = pymupdf.open(file_path)
        pages = []
        for i, page in enumerate(doc, start=1):
            try:
                pages.append((i, page.get_text("text") or ""))
            except Exception:
                pages.append((i, ""))
        doc.close()
        return pages
    except Exception:
        return []


def _pdf_pages_by_pypdf(file_path: str) -> list[tuple[int, str]]:
    """用 pypdf / PyPDF2 逐页提取文本层。"""
    for mod_name in ("pypdf", "PyPDF2"):
        try:
            mod = __import__(mod_name, fromlist=["PdfReader"])
            reader = mod.PdfReader(file_path)
            pages: list[tuple[int, str]] = []
            for i, page in enumerate(reader.pages, start=1):
                try:
                    pages.append((i, page.extract_text() or ""))
                except Exception:
                    pages.append((i, ""))
            if any(t.strip() for _, t in pages):
                return pages
        except ImportError:
            continue
        except Exception:
            continue
    return []


def parse_file_pages(file_path: str) -> list[tuple[int, str]]:
    """
    通用分页解析：PDF 返回逐页文本，其它格式视为单页。

    统一返回结构，便于上层（上传 / 重建索引）用同一套逻辑处理。
    """
    file_path = str(file_path)
    if get_ext(file_path) == "pdf":
        return parse_pdf_pages(file_path)
    return [(1, parse_file(file_path))]


def _ocr_pdf_pages(file_path: str, dpi: int = 160) -> str:
    """把 PDF 每页渲染成图片再 OCR（用于扫描件），返回拼接后的整篇文本。"""
    return "\n\n".join(t for _, t in _ocr_pdf_pages_list(file_path, dpi))


def _ocr_pdf_pages_list(file_path: str, dpi: int = 160) -> list[tuple[int, str]]:
    """把 PDF 每页渲染成图片再 OCR，返回 [(page_no, text)]。"""
    import os
    import tempfile

    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf          # 旧版兼容

    doc = pymupdf.open(file_path)
    out: list[tuple[int, str]] = []
    try:
        for idx, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(pix.tobytes("png"))
                tmp_path = tmp.name
            try:
                out.append((idx, _recognize_image(tmp_path)))
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    finally:
        doc.close()
    return out


# ---------------------------------------------------------------------------
# 页眉 / 页脚 / 页码清洗
# ---------------------------------------------------------------------------
# 独立成行的页码：「12」「- 12 -」「第 12 页」「3 / 20」
_PAGE_NUM_RE = re.compile(
    r"^\s*[-–—.\s]*第?\s*\d{1,4}\s*页?\s*(?:[/|／—-]\s*(?:共)?\s*\d{1,4}\s*页?)?\s*[-–—.\s]*$"
)


def _norm_line(line: str) -> str:
    """行归一化：去掉空白，用于跨页比较（忽略分页造成的空格差异）。"""
    return re.sub(r"\s+", "", line or "")


def strip_header_footer(
    pages: list[tuple[int, str]],
    ratio: float = 0.4,
    max_len: int = 60,
    scan_lines: int = 3,
) -> list[tuple[int, str]]:
    """
    去除 PDF 页眉 / 页脚 / 页码，避免它们混进 chunk 污染检索。

    判定规则：
    1. 取每页首 / 末 scan_lines 行，归一化后统计跨页出现次数；
       出现页数占比 >= ratio 且长度 <= max_len 的行视为页眉页脚；
    2. 单独成行的页码（纯数字、"第 N 页"、"N / M" 等）一律删除。

    页数 < 3 时样本不足，不做跨页统计，仅清理页码行。
    """
    if not pages:
        return []

    if len(pages) < 3:
        return [(no, _drop_noise_lines(t, set())) for no, t in pages]

    head_counter: Counter = Counter()
    foot_counter: Counter = Counter()
    for _no, text in pages:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue
        for ln in lines[:scan_lines]:
            head_counter[_norm_line(ln)] += 1
        for ln in lines[-scan_lines:]:
            foot_counter[_norm_line(ln)] += 1

    threshold = max(3, int(len(pages) * ratio))
    noise = {k for k, c in head_counter.items() if c >= threshold and 0 < len(k) <= max_len}
    noise |= {k for k, c in foot_counter.items() if c >= threshold and 0 < len(k) <= max_len}

    return [(no, _drop_noise_lines(t, noise)) for no, t in pages]


def _drop_noise_lines(text: str, noise: set[str]) -> str:
    """删除命中噪声集合或页码正则的行，保持原有段落结构。"""
    kept = [
        ln for ln in text.splitlines()
        if _norm_line(ln) not in noise and not _PAGE_NUM_RE.match(ln)
    ]
    return "\n".join(kept)


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


def _parse_xlsx(file_path: str) -> str:
    """解析 XLSX / XLSM 表格（openpyxl）。"""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(file_path, read_only=True, data_only=True)
        sheets = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(values_only=True):
                cells = ["" if c is None else str(c) for c in row]
                line = "\t".join(cells).strip()
                if line:
                    rows.append(line)
            if rows:
                sheets.append(f"### Sheet: {ws.title}\n" + "\n".join(rows))
        return "\n\n".join(sheets)
    except ImportError:
        return "[XLSX 解析需要 openpyxl 库]"
    except Exception as e:
        return f"[XLSX 解析失败: {e}]"


def _parse_html(file_path: str) -> str:
    """解析 HTML / HTM，去除标签保留正文（BeautifulSoup + lxml）。"""
    try:
        from bs4 import BeautifulSoup
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [ln.strip() for ln in text.splitlines()]
        return "\n".join(ln for ln in lines if ln)
    except ImportError:
        # 无 bs4 时兜底：简单正则去标签
        return _strip_html_basic(file_path)
    except Exception as e:
        return f"[HTML 解析失败: {e}]"


def _strip_html_basic(file_path: str) -> str:
    import re
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
        html = re.sub(r"(?s)<[^>]+>", " ", html)
        html = re.sub(r"&nbsp;", " ", html)
        html = re.sub(r"&amp;", "&", html)
        html = re.sub(r"&lt;", "<", html)
        html = re.sub(r"&gt;", ">", html)
        lines = [ln.strip() for ln in html.splitlines()]
        return "\n".join(ln for ln in lines if ln)
    except Exception:
        return ""


def _parse_legacy_office(file_path: str, target_ext: str) -> str:
    """把 .doc/.xls/.ppt 用 LibreOffice headless 转成新格式后再解析。"""
    import shutil
    import subprocess
    import tempfile

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("解析 .doc/.xls/.ppt 需要安装 LibreOffice（提供 soffice 命令）")

    with tempfile.TemporaryDirectory() as outdir:
        subprocess.run(
            [soffice, "--headless", "--norestore", "--convert-to", target_ext,
             "--outdir", outdir, file_path],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
        )
        converted = Path(outdir) / f"{Path(file_path).stem}.{target_ext}"
        if not converted.exists():
            raise RuntimeError(f"LibreOffice 转换失败：未生成 {target_ext}")

        # 必须在临时目录被清理前完成解析
        if target_ext == "docx":
            return _parse_docx(str(converted))
        if target_ext == "xlsx":
            return _parse_xlsx(str(converted))
        if target_ext == "pptx":
            return _parse_pptx(str(converted))
    return ""
