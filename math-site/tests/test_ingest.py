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


def test_pair_answers_reserves_exact_pairs_and_keeps_number_separators():
    probs = [dict(number="01"), dict(section="A", number="1"),
             dict(section="C", number="1"), dict(section="A", number="01-02"),
             dict(section="A", number="1.2"), dict(section="A", number="12")]
    answers = [dict(section="A", number="001"), dict(section="B", number="1"),
               dict(section="A", number="1-2"), dict(section="A", number="1.2")]
    assert pair_answers(probs, answers) == []
    assert [p.get("_answer") for p in probs] == [answers[1], answers[0], None, answers[2], answers[3], None]


def test_hwpx_keeps_inline_notes_and_shapes(tmp_path, monkeypatch):
    import ingest

    path = tmp_path / "notes.hwpx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Contents/section0.xml", """
        <sec><p><run><t>앞<footNote><subList><p><run><t>각주</t></run></p></subList></footNote>중간</t>
        <rect/><endNote><subList><p><run><t>미주</t></run></p></subList></endNote><t>뒤</t>
        <container><ellipse/></container></run></p></sec>""")
    pages, meta = docread.read_any(str(path), str(tmp_path))
    assert "앞(주: 각주)중간 [도형: 원본 확인 필요] (주: 미주)뒤" in pages[0].text
    assert meta["shapes"] == 3
    monkeypatch.setattr(ingest.engines, "ask", lambda *args: {
        "problems": [{"number": "1", "body": pages[0].text, "unit_id": 1}],
    })
    items, report = ingest.process([str(path)], "math", "중1", "교재",
                                   [{"id": 1, "name": "단원"}], "codex", str(tmp_path))
    assert "한글 도형 개체가 있어 그림이 빠졌을 수 있음 — 원본 확인" in items[0]["review_note"]
    assert "'shapes': 3" in report


def test_hwp_scripts_stay_attached_inside_fractions():
    assert hwp_to_latex("x^2 over y") == r"\frac{x^{2}}{y}"
    assert hwp_to_latex("a_n over 2") == r"\frac{a_{n}}{2}"
    assert hwp_to_latex("x_i^2 over y_1") == r"\frac{x_{i}^{2}}{y_{1}}"


def test_pdf_continuation_uses_previous_tail_and_stacks_crops(tmp_path, monkeypatch):
    import ingest
    from PIL import Image

    pages = [docread.Page(no=i, source="book.pdf", text=t, image=f"p{i}.png", pdf=("book.pdf", i - 1))
             for i, t in enumerate(("빼" + "앞" * 800, "뒷부분", "다른 쪽", "다시 시작"), 1)]
    monkeypatch.setattr(docread, "read_any", lambda *args: (pages, {}))
    prompts = []
    results = iter([
        {"problems": [dict(number="1", body="첫 구절", bbox=[0, 0, 90, 90], unit_id=1)]},
        {"problems": [dict(number="01", body="첫 구절과 이어진 본문", bbox=[0, 0, 90, 90], unit_id=1)]},
        {},
        {"problems": [dict(number="1", body="연속하지 않는 문제", unit_id=1)]},
    ])

    def ask(engine, prompt, images, workdir):
        prompts.append(prompt)
        return next(results)

    def crop(ref, bbox):
        out = io.BytesIO()
        Image.new("RGB", (12, 20), ("red", "blue")[ref[1]]).save(out, "PNG")
        return out.getvalue()

    monkeypatch.setattr(ingest.engines, "ask", ask)
    monkeypatch.setattr(docread, "crop_pdf", crop)
    items, _ = ingest.process(["book.pdf"], "math", "중1", "교재",
                              [{"id": 1, "name": "단원"}], "codex", str(tmp_path))
    assert "⟪앞 쪽의 끝부분(참고용)⟫" not in prompts[0]
    assert "⟪앞 쪽의 끝부분(참고용)⟫\n" + "앞" * 800 + "\n" in prompts[1]
    assert "빼" not in prompts[1]
    assert [i["body"] for i in items] == ["첫 구절과 이어진 본문", "연속하지 않는 문제"]
    assert items[0]["image_kind"] == "full"
    im = Image.open(io.BytesIO(items[0]["image"]))
    assert im.size == (12, 50)
    assert im.getpixel((0, 0)) == (255, 0, 0) and im.getpixel((0, 49)) == (0, 0, 255)


def test_process_filters_duplicates_and_moves_answer(tmp_path, monkeypatch):
    import ingest

    page = docread.Page(no=1, source="교재.hwp", text="본문")
    monkeypatch.setattr(docread, "read_any", lambda *args: ([page], {}))
    body = "abcdefghijklmnopqrst"
    problems = [
        dict(number="1", body=r"① $X\,\;\!\quad Y$⟦hwp:원본⟧.", unit_id=1),
        dict(number="2", body="① $xy$！", unit_id=1),
        dict(number="3", body="② $xy$", unit_id=1),
        dict(number="4", body="사이트에 있는 문제.", unit_id=1),
        dict(number="5", body=body, unit_id=1),
        dict(number="6", body=body[:-2] + "ZZ", unit_id=1),
    ]
    answers = [dict(number=str(n), answer="정답", solution="답지 풀이") for n in (2, 3, 5, 6)]
    existing = [dict(id=42, body="사이트에 있는 문제", source="기존 교재", has_image=False),
                dict(id=43, body=body[:-2] + "QQ", source="다른 교재", has_image=False)]

    def ask(engine, prompt, images, workdir):
        assert "학생 학년 수준의 정석 풀이" not in prompt
        return dict(problems=problems, answers=answers)

    monkeypatch.setattr(ingest.engines, "ask", ask)
    items, report = ingest.process(["교재.hwp"], "math", "중1", "교재",
                                   [{"id": 1, "name": "단원"}], "codex", str(tmp_path), existing=existing)
    assert [item["source"].split("#")[-1] for item in items] == ["1", "3", "5", "6"]
    assert (items[0]["answer"], items[0]["solution"]) == ("정답", "답지 풀이")
    assert "답지 없음" not in items[0]["review_note"]
    assert "중복 의심: 기존 #43 (다른 교재)" in items[2]["review_note"]
    assert "중복으로 건너뜀 2개" in report
    assert "#2 → 같은 묶음의 교재 · 교재.hwp 조각1 #1" in report
    assert "#4 → 기존 #42" in report
    assert "중복 의심 2개" in report


def test_process_image_duplicate_rules_and_hwp_solve(tmp_path, monkeypatch):
    import ingest
    from PIL import Image

    figure = tmp_path / "figure.png"
    Image.new("RGB", (10, 10), "red").save(figure)
    page = docread.Page(no=1, source="교재.hwp", text="본문", figures={"그림1": str(figure)})
    monkeypatch.setattr(docread, "read_any", lambda *args: ([page], {}))
    short = "다음 그림의 넓이를 구하시오"
    long = "밑변이 길고 높이가 다른 두 삼각형의 넓이를 각각 구하고 두 넓이의 차이를 계산하시오"
    problems = [
        dict(number=str(n), body=body, unit_id=1, qtype="mc_right",
             has_figure=n != 5, figures=["그림1"] if n != 5 else [])
        for n, body in enumerate([short, short, long, long, long], 1)
    ]
    answers = [dict(number="2", answer="①"), dict(number="3", solution="답지 풀이"),
               dict(number="5", answer="③", solution="답지 풀이")]
    attachments = []

    def ask(engine, prompt, images, workdir):
        if "학생 학년 수준의 정석 풀이" not in prompt:
            return dict(problems=problems, answers=answers)
        assert engine == "codex"
        for value in ("과학", "중1", "단원", "mc_right", short, "각 선지"):
            assert value in prompt
        path, = images
        assert path != str(figure)
        with Image.open(path) as image:
            assert image.getpixel((0, 0)) == (255, 0, 0)
        attachments.append(path)
        if "답지 답: ①" in prompt:
            return dict(answer="②", solution="선지를 확인한다.", confidence="low", note="그림 확인")
        return dict(answer="①", solution="$1+1=2$", confidence="high", note="")

    monkeypatch.setattr(ingest.engines, "ask", ask)
    items, report = ingest.process(["교재.hwp"], "science", "중1", "교재",
                                   [{"id": 1, "name": "단원"}], "codex", str(tmp_path))
    assert [item["source"].split("#")[-1] for item in items] == ["1", "2", "3", "5"]
    assert (items[0]["answer"], items[0]["solution"]) == ("①", "[AI 풀이] $1+1=2$")
    assert "답지 없음 → AI 풀이 (확인 필요)" in items[0]["review_note"]
    assert items[1]["answer"] == "①"
    for note in ("중복 의심: 같은 묶음의", "AI 답과 답지 답이 다름: AI=②, 답지=①",
                 "AI 풀이 확신 낮음", "그림 확인"):
        assert note in items[1]["review_note"]
    assert items[2]["solution"] == "답지 풀이"
    assert "중복 의심: 같은 묶음의" in items[3]["review_note"]
    assert len(attachments) == 2 and not any(os.path.exists(path) for path in attachments)
    assert "중복으로 건너뜀 1개" in report and "중복 의심 2개" in report
    assert "AI가 푼 문제 2개 (확인 필요)" in report


def test_process_pdf_solve_failure_continues(tmp_path, monkeypatch):
    import ingest

    page = docread.Page(no=1, source="교재.pdf", text="본문", image="p.png", pdf=("교재.pdf", 0))
    monkeypatch.setattr(docread, "read_any", lambda *args: ([page], {}))
    monkeypatch.setattr(docread, "crop_pdf", lambda *args: b"cropped")

    def ask(engine, prompt, images, workdir):
        if "학생 학년 수준의 정석 풀이" not in prompt:
            return {"problems": [
                dict(number="1", body="그림의 넓이", unit_id=1, has_figure=True, bbox=[0, 0, 90, 90]),
                dict(number="2", body="계산 문제", unit_id=1),
            ]}
        if "그림의 넓이" in prompt:
            path, = images
            with open(path, "rb") as f:
                assert f.read() == b"cropped"
            raise ingest.engines.EngineError("시간 초과")
        assert images == []
        return dict(answer="7", solution="계산한다.", confidence="medium", note="")

    monkeypatch.setattr(ingest.engines, "ask", ask)
    items, report = ingest.process(["교재.pdf"], "math", "중1", "교재",
                                   [{"id": 1, "name": "단원"}], "codex", str(tmp_path))
    assert items[0]["answer"] == items[0]["solution"] == ""
    assert "AI 풀이 실패: 시간 초과" in items[0]["review_note"]
    assert items[1]["answer"] == "7"
    assert "AI가 푼 문제 1개 (확인 필요)" in report
