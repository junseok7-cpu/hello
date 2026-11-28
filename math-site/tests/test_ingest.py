"""문제집 읽기(HWP/HWPX/수식/짝짓기) 테스트. AI 호출 없음."""
import io
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "grader"))
import docread  # noqa: E402
from hwpeq import hwp_to_latex  # noqa: E402
from ingest import pair_answers, _gaps  # noqa: E402


def test_hwp_equations():
    assert hwp_to_latex("{x+1} over 2 = 3") == r"\frac{x+1}{2}=3"
    assert hwp_to_latex("sqrt {x^2 +1}") == r"\sqrt{x^{2}+1}"
    assert hwp_to_latex("root 3 of {8}") == r"\sqrt[3]{8}"
    assert hwp_to_latex("LEFT ( a over 2 RIGHT ) ^2") == r"\left(\frac{a}{2}\right)^{2}"
    assert hwp_to_latex("cases{x+y=5 # x-y=1}") == r"\begin{cases}x+y=5 \\ x-y=1\end{cases}"
    assert hwp_to_latex("angle A = 60 deg") == r"\angle A=60^{\circ}"
    assert hwp_to_latex("1 over 2 + 3 over 4") == r"\frac{1}{2}+\frac{3}{4}"
    assert hwp_to_latex("x le 3") == r"x\le 3"


def _rec(tag, level, data):
    return struct.pack("<I", tag | (level << 10) | (len(data) << 20)) + data


def _ctrl(cid):
    body = struct.pack("<H", 11) + cid[::-1].encode("latin-1") + b"\0" * 8 + struct.pack("<H", 11)
    assert len(body) == 16
    return body


def test_hwp_binary_section(tmp_path):
    text1 = "문제 1 ".encode("utf-16-le") + _ctrl("eqed") + " 를 구하시오.".encode("utf-16-le") + struct.pack("<H", 13)
    script = "a over b"
    eq = struct.pack("<IH", 0, len(script)) + script.encode("utf-16-le")
    text2 = "그림: ".encode("utf-16-le") + _ctrl("gso ") + struct.pack("<H", 13)
    pic = b"\0" * 71 + struct.pack("<H", 1)
    data = (_rec(66, 0, b"\0" * 22) + _rec(67, 1, text1) + _rec(71, 1, b"deqe") + _rec(88, 2, eq)
            + _rec(66, 0, b"\0" * 22) + _rec(67, 1, text2) + _rec(71, 1, b" osg") + _rec(85, 3, pic))
    png = io.BytesIO()
    from PIL import Image
    Image.new("RGB", (10, 10), "red").save(png, "PNG")
    doc = docread._Doc("t.hwp", str(tmp_path))
    docread.parse_hwp_section(data, doc, lambda bid: (png.getvalue(), "png") if bid == 1 else (None, None))
    text = "".join(doc.parts)
    assert r"$\frac{a}{b}$⟦hwp:a over b⟧" in text and "를 구하시오." in text
    assert "[그림1]" in text and os.path.exists(doc.figures["그림1"])


def test_hwpx_reads_text_equation_figure_table(tmp_path):
    hp = 'xmlns:hp="urn:p" xmlns:hc="urn:c"'
    sec = (f'<sec {hp}><hp:p><hp:run><hp:t>001 식 </hp:t></hp:run><hp:run><hp:equation><hp:script>x^2</hp:script>'
           '</hp:equation></hp:run></hp:p><hp:p><hp:run><hp:pic><hc:img binaryItemIDRef="image1"/></hp:pic></hp:run></hp:p>'
           '<hp:p><hp:run><hp:tbl><hp:tr><hp:tc><hp:p><hp:run><hp:t>A</hp:t></hp:run></hp:p></hp:tc>'
           '<hp:tc><hp:p><hp:run><hp:t>B</hp:t></hp:run></hp:p></hp:tc></hp:tr></hp:tbl></hp:run></hp:p></sec>')
    png = io.BytesIO()
    from PIL import Image
    Image.new("RGB", (10, 10)).save(png, "PNG")
    f = tmp_path / "a.hwpx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("Contents/section0.xml", sec)
        z.writestr("Contents/content.hpf", '<package><manifest><item id="image1" href="BinData/image1.png"/></manifest></package>')
        z.writestr("BinData/image1.png", png.getvalue())
    pages, meta = docread.read_any(str(f), str(tmp_path))
    t = pages[0].text
    assert "001 식" in t and "$x^{2}$⟦hwp:x^2⟧" in t and "[그림1]" in t and "| A | B |" in t
    assert meta["equations"] == 1 and meta["figures"] == 1


def test_pair_answers_by_section_and_order():
    probs = [dict(section="유형1", number="01"), dict(section="유형2", number="01"),
             dict(section="", number="5"), dict(section="", number="5"), dict(section="", number="7")]
    ans = [dict(section="유형2", number="1", answer="B"), dict(section="유형1", number="001", answer="A"),
           dict(section="", number="5", answer="첫째"), dict(section="", number="5", answer="둘째"),
           dict(section="", number="9", answer="남음")]
    left = pair_answers(probs, ans)
    assert [p.get("_answer", {}).get("answer") for p in probs] == ["A", "B", "첫째", "둘째", None]
    assert [a["number"] for a in left] == ["9"]
    assert "순서대로" in probs[2]["_notes"][0]


def test_gaps():
    assert _gaps(["1", "2", "4", "6"]) == [3, 5]
