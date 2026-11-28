"""문제집·답지 파일 읽기: PDF, HWPX(한글 2014+ XML), HWP(한글 5.0 바이너리).

손실을 줄이는 원칙
- PDF: 쪽 그림(200dpi) + 글자 층(좌표 포함)을 함께 AI에 준다. 스캔본이면 그림만.
  문제 그림은 나중에 원본 벡터에서 고해상도로 다시 잘라 낸다.
- HWPX/HWP: 글자와 수식은 원본 그대로 읽는다(수식은 LaTeX로 바꾸고 원본 스크립트도 남김).
  그림은 문서에 들어 있는 원본 이미지 파일을 그대로 꺼낸다.
- Windows에 한글 프로그램이 있으면 HWP를 한글로 열어 HWPX로 바꾼 뒤 읽는다 (가장 정확).

결과는 Page 목록. 한글 파일은 쪽 개념이 없어서 일정 길이로 나눈 '조각'을 Page로 쓴다.
"""
import io
import os
import re
import struct
import sys
import zipfile
import zlib
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwpeq import hwp_to_latex  # noqa: E402


@dataclass
class Page:
    no: int
    source: str                     # 원본 파일 이름
    text: str = ""                  # 글자 층 (수식은 $LaTeX$)
    image: str | None = None        # 쪽 그림 (PDF)
    blocks: list = field(default_factory=list)   # PDF 글자 덩어리 [(x0,y0,x1,y1 비율 0~1000, 글자)]
    figures: dict = field(default_factory=dict)  # 한글: {"그림3": 파일경로}
    pdf: tuple | None = None        # (pdf 경로, 쪽 번호 0부터) — 벡터에서 다시 자르기용


class ReadError(Exception):
    pass


# ------------------------------------------------------------------ PDF

def read_pdf(path, workdir, dpi=200):
    import pymupdf
    doc = pymupdf.open(path)
    pages = []
    name = os.path.basename(path)
    for i, pg in enumerate(doc):
        img = os.path.join(workdir, f"{_safe(name)}_p{i + 1:03d}.png")
        pg.get_pixmap(dpi=dpi).save(img)
        w, h = pg.rect.width, pg.rect.height
        blocks = []
        for b in pg.get_text("blocks"):
            x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
            txt = " ".join(txt.split())
            if txt:
                blocks.append((int(x0 / w * 1000), int(y0 / h * 1000), int(x1 / w * 1000), int(y1 / h * 1000), txt))
        pages.append(Page(no=i + 1, source=name, text=pg.get_text().strip(), image=img, blocks=blocks,
                          pdf=(path, i)))
    return pages


def crop_pdf(pdf_ref, bbox, dpi=250, pad=12):
    """PDF 원본(벡터)에서 비율 좌표 영역을 고해상도로 잘라 PNG 바이트로."""
    import pymupdf
    path, index = pdf_ref
    pg = pymupdf.open(path)[index]
    w, h = pg.rect.width, pg.rect.height
    x0, y0, x1, y1 = [max(0, min(1000, int(v))) for v in bbox]
    if x1 - x0 < 15 or y1 - y0 < 15:
        return None
    rect = pymupdf.Rect(max(0, (x0 - pad) * w / 1000), max(0, (y0 - pad) * h / 1000),
                        min(w, (x1 + pad) * w / 1000), min(h, (y1 + pad) * h / 1000))
    return pg.get_pixmap(dpi=dpi, clip=rect).tobytes("png")


# ------------------------------------------------------------------ 한글 공통

class _Doc:
    """한글 문서를 글자열 + 그림 파일로 모은다."""

    def __init__(self, name, workdir):
        self.name, self.workdir = name, workdir
        self.parts = []      # 글자 조각
        self.figures = {}    # 표시 → 파일
        self.n_eq = 0
        self.n_shapes = 0

    def text(self, s):
        self.parts.append(s)

    def equation(self, script):
        script = (script or "").strip()
        if not script:
            return
        self.n_eq += 1
        latex = hwp_to_latex(script)
        # 원본 스크립트를 같이 남겨서 변환이 틀려도 AI가 바로잡을 수 있게
        self.parts.append(f" ${latex}$⟦hwp:{script}⟧ ")

    def figure(self, data, ext):
        if not data:
            return
        key = f"그림{len(self.figures) + 1}"
        path = os.path.join(self.workdir, f"{_safe(self.name)}_{key}.{ext or 'png'}")
        with open(path, "wb") as f:
            f.write(data)
        self.figures[key] = _to_png(path)
        self.parts.append(f" [{key}] ")

    def pages(self, chunk=6000, overlap=800):
        text = re.sub(r"\n{3,}", "\n\n", "".join(self.parts)).strip()
        pages, start, no = [], 0, 1
        while start < len(text):
            end = min(len(text), start + chunk)
            if end < len(text):  # 문단 경계에서 자르기
                cut = text.rfind("\n", start + chunk // 2, end)
                end = cut if cut > 0 else end
            body = text[start:end]
            head = text[max(0, start - overlap):start] if start else ""
            figs = {k: v for k, v in self.figures.items() if f"[{k}]" in body}
            page_text = (f"⟪앞 조각의 끝부분(참고용)⟫\n{head}\n⟪여기부터 이번 조각⟫\n" if head else "") + body
            pages.append(Page(no=no, source=self.name, text=page_text, figures=figs))
            start, no = end, no + 1
        return pages


def _to_png(path):
    """BMP/WMF 등 AI가 못 읽는 형식은 PNG로 바꿔 본다."""
    if path.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
        return path
    try:
        from PIL import Image
        out = os.path.splitext(path)[0] + ".png"
        Image.open(path).convert("RGB").save(out)
        return out
    except Exception:
        return path


def _safe(s):
    return re.sub(r"[^\w가-힣.-]+", "_", s)[:60]


# ------------------------------------------------------------------ HWPX

def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def read_hwpx(path, workdir):
    name = os.path.basename(path)
    doc = _Doc(name, workdir)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        bindata = {}
        if "Contents/content.hpf" in names:  # 그림 id → 파일 경로
            man = ET.fromstring(z.read("Contents/content.hpf"))
            for el in man.iter():
                if _local(el.tag) == "item" and el.get("id") and el.get("href"):
                    bindata[el.get("id")] = el.get("href")
        for n in names:
            if n.startswith("BinData/"):
                bindata.setdefault(os.path.splitext(os.path.basename(n))[0], n)
        sections = sorted((n for n in names if re.match(r"Contents/section\d+\.xml$", n)),
                          key=lambda n: int(re.findall(r"\d+", n)[-1]))
        if not sections:
            raise ReadError("HWPX 안에 본문(section)이 없어요")

        def walk(el):
            tag = _local(el.tag)
            if tag in ("header", "footer", "secPr", "pagePr", "linesegarray"):
                return
            if tag in ("footNote", "endNote"):
                sub = _Doc(name, workdir)
                sub.figures = doc.figures
                _walk_into(el, sub)
                doc.n_eq += sub.n_eq
                doc.n_shapes += sub.n_shapes
                doc.text("(주: " + " ".join("".join(sub.parts).split()) + ")")
                return
            if tag in ("rect", "ellipse", "line", "arc", "polygon", "curve", "connectLine",
                       "container", "textart", "textArt", "ole"):
                doc.n_shapes += 1
                doc.text(" [도형: 원본 확인 필요] ")
                if tag == "container":
                    for ch in el:
                        walk(ch)
                return
            if tag == "t":
                if el.text:
                    doc.text(el.text)
                for ch in el:
                    ct = _local(ch.tag)
                    if ct in ("tab", "lineBreak"):
                        doc.text("\t" if ct == "tab" else "\n")
                    else:
                        walk(ch)
                    if ch.tail:
                        doc.text(ch.tail)
                return
            if tag == "equation":
                script = next((c.text for c in el.iter() if _local(c.tag) == "script"), "")
                doc.equation(script)
                return
            if tag == "pic":
                ref = next((c.get("binaryItemIDRef") for c in el.iter() if _local(c.tag) == "img"), None)
                href = bindata.get(ref or "")
                if href and href in names:
                    doc.figure(z.read(href), os.path.splitext(href)[1].lstrip(".").lower())
                return
            if tag == "tbl":
                doc.text("\n[표]\n")
                for tr in (c for c in el.iter() if _local(c.tag) == "tr"):
                    cells = []
                    for tc in (c for c in tr if _local(c.tag) == "tc"):
                        sub = _Doc(name, workdir)
                        sub.figures = doc.figures
                        _walk_into(tc, sub)
                        doc.n_shapes += sub.n_shapes
                        cells.append(" ".join("".join(sub.parts).split()))
                    doc.text("| " + " | ".join(cells) + " |\n")
                    doc.n_eq += sum(1 for c in cells if "⟦hwp:" in c)
                doc.text("[표 끝]\n")
                return
            for ch in el:
                walk(ch)
            if tag == "p":
                doc.text("\n")

        def _walk_into(root, target):
            nonlocal doc
            saved, doc = doc, target
            try:
                for ch in root:
                    walk(ch)
            finally:
                doc = saved

        for s in sections:
            walk(ET.fromstring(z.read(s)))
            doc.text("\n")
    return doc


# ------------------------------------------------------------------ HWP (5.0 바이너리)
# 한컴 공개 문서 형식(HWP 5.0) 기준. 레코드 = 32비트 머리(tag 10비트, level 10비트, size 12비트) + 데이터.

TAG_PARA_HEADER, TAG_PARA_TEXT, TAG_CTRL_HEADER = 66, 67, 71
TAG_PICTURE, TAG_EQEDIT = 85, 88
_EXT_CTRL = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}  # 8글자 차지 + 개체
_INLINE_CTRL = {4, 5, 6, 7, 8, 9, 19, 20}                     # 8글자 차지


def _records(data):
    i = 0
    while i + 4 <= len(data):
        h = struct.unpack_from("<I", data, i)[0]
        i += 4
        tag, level, size = h & 0x3FF, (h >> 10) & 0x3FF, (h >> 20) & 0xFFF
        if size == 0xFFF:
            size = struct.unpack_from("<I", data, i)[0]
            i += 4
        yield tag, level, data[i:i + size]
        i += size


def _para_tokens(data):
    """PARA_TEXT → [글자 | ('ctrl', id)]"""
    out, buf, i = [], [], 0
    n = len(data) // 2
    while i < n:
        c = struct.unpack_from("<H", data, i * 2)[0]
        if c >= 32:
            buf.append(chr(c))
            i += 1
            continue
        if c in _EXT_CTRL or c in _INLINE_CTRL:
            if buf:
                out.append("".join(buf))
                buf = []
            if c == 9:
                out.append("\t")
            elif c in _EXT_CTRL:
                cid = data[i * 2 + 2:i * 2 + 6][::-1].decode("latin-1", "replace")
                out.append(("ctrl", cid))
            i += 8
            continue
        if c in (10, 13):
            buf.append("\n")
        elif c in (24, 30, 31):
            buf.append(" ")
        i += 1
    if buf:
        out.append("".join(buf))
    return out


def read_hwp(path, workdir):
    if os.name == "nt":  # 한글 프로그램이 있으면 HWPX로 바꿔서 읽는다 (가장 정확)
        hwpx = _hwp_to_hwpx_with_hancom(path, workdir)
        if hwpx:
            return read_hwpx(hwpx, workdir)
    import olefile
    if not olefile.isOleFile(path):
        raise ReadError("HWP 파일 형식이 아니에요 (HWPX면 확장자를 .hwpx로 바꿔 주세요)")
    ole = olefile.OleFileIO(path)
    head = ole.openstream("FileHeader").read()
    if not head.startswith(b"HWP Document File"):
        raise ReadError("HWP 5.0 문서가 아니에요")
    props = struct.unpack_from("<I", head, 36)[0]
    compressed, encrypted, distribution = props & 1, props & 2, props & 4
    if encrypted:
        raise ReadError("암호가 걸린 HWP예요. 암호를 풀고 다시 저장해 주세요")
    if distribution:
        raise ReadError("배포용 HWP는 읽을 수 없어요. 한글에서 일반 문서(또는 PDF)로 저장해 주세요")

    def stream(nm):
        raw = ole.openstream(nm).read()
        if compressed:
            try:
                return zlib.decompress(raw, -15)
            except zlib.error:
                return raw
        return raw

    bins = {}
    for entry in ole.listdir():
        if len(entry) == 2 and entry[0] == "BinData":
            m = re.match(r"BIN([0-9A-Fa-f]{4})\.(\w+)", entry[1])
            if m:
                bins[int(m.group(1), 16)] = ("BinData/" + entry[1], m.group(2).lower())

    name = os.path.basename(path)
    doc = _Doc(name, workdir)
    sections = sorted((e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText"),
                      key=lambda e: int(re.findall(r"\d+", e[1])[0]))
    def get_bin(bid):
        if bid not in bins:
            return None, None
        nm, ext = bins[bid]
        try:
            return stream(nm), ext
        except Exception:
            return None, None

    for sec in sections:
        parse_hwp_section(stream("/".join(sec)), doc, get_bin)
    return doc


def parse_hwp_section(data, doc, get_bin):
    """BodyText/SectionN 한 개(압축 푼 바이트)를 doc에 옮긴다."""
    paras = []  # 문단별 [글자 | 개체] 목록
    for tag, level, rec in _records(data):
        if tag == TAG_PARA_TEXT:
            paras.append(_para_tokens(rec))
        elif tag == TAG_EQEDIT and len(rec) >= 6:
            ln = struct.unpack_from("<H", rec, 4)[0]
            _fill(paras, "eqed", ("eq", rec[6:6 + ln * 2].decode("utf-16-le", "replace")))
        elif tag == TAG_PICTURE and len(rec) >= 73:
            _fill(paras, "gso ", ("pic", struct.unpack_from("<H", rec, 71)[0]))
    for toks in paras:
        for t in toks:
            if isinstance(t, str):
                doc.text(t)
            elif t[0] == "eq":
                doc.equation(t[1])
            elif t[0] == "pic":
                data_, ext = get_bin(t[1])
                doc.figure(data_, ext)
        doc.text("\n")


def _fill(paras, cid, value):
    """가장 최근 문단부터 거슬러 올라가며 비어 있는 같은 종류의 개체 자리를 채운다."""
    for toks in reversed(paras):
        for k, t in enumerate(toks):
            if isinstance(t, tuple) and t[0] == "ctrl" and t[1] == cid:
                toks[k] = value
                return


def _hwp_to_hwpx_with_hancom(path, workdir):
    """Windows + 한글 설치 시: 한글을 자동으로 열어 HWPX로 저장."""
    try:
        import win32com.client  # pywin32
        hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        out = os.path.join(workdir, os.path.splitext(os.path.basename(path))[0] + ".hwpx")
        hwp.Open(os.path.abspath(path), "HWP", "forceopen:true")
        hwp.SaveAs(out, "HWPX", "")
        hwp.Quit()
        return out if os.path.exists(out) else None
    except Exception:
        return None


# ------------------------------------------------------------------ 입구

def read_any(path, workdir):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        pages = read_pdf(path, workdir)
        scanned = sum(len(p.text) for p in pages) < 30 * len(pages)
        return pages, {"kind": "pdf", "pages": len(pages), "scanned": scanned}
    if ext in (".hwpx", ".hwp"):
        doc = read_hwpx(path, workdir) if ext == ".hwpx" else read_hwp(path, workdir)
        pages = doc.pages()
        if not pages:
            raise ReadError("문서에서 글자를 하나도 찾지 못했어요")
        return pages, {"kind": ext[1:], "chunks": len(pages), "equations": doc.n_eq, "figures": len(doc.figures),
                       "shapes": doc.n_shapes}
    raise ReadError(f"지원하지 않는 형식: {ext} (PDF, HWP, HWPX만)")
