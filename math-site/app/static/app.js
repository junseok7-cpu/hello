// 수식 렌더링
document.addEventListener("DOMContentLoaded", () => {
  const render = (el) => window.renderMathInElement && renderMathInElement(el, {
    delimiters: [{left: "$$", right: "$$", display: true}, {left: "$", right: "$", display: false},
                 {left: "\\(", right: "\\)", display: false}, {left: "\\[", right: "\\]", display: true}],
    throwOnError: false});
  const t = setInterval(() => { if (window.renderMathInElement) { clearInterval(t);
    document.querySelectorAll(".math").forEach(render); } }, 50);

  // 사진 미리보기 + 업로드 전 줄이기 (폰 사진 5MB → 300KB 정도)
  document.querySelectorAll(".submit-form").forEach((form) => {
    const input = form.querySelector("input[type=file]");
    const box = form.querySelector(".previews");
    let files = [];
    let generation = 0;
    input.addEventListener("change", async () => {
      const current = ++generation;
      const selected = [];
      files = [];
      box.innerHTML = "";
      for (const f of [...input.files].slice(0, 3)) {
        const small = await shrink(f, 1800).catch(() => f);
        if (current !== generation) return;
        selected.push(small);
        const img = document.createElement("img");
        img.src = URL.createObjectURL(small);
        box.appendChild(img);
      }
      files = selected;
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!files.length) { alert("풀이 사진을 올려 주세요"); return; }
      const btn = form.querySelector("button[type=submit]");
      btn.disabled = true; btn.textContent = "올리는 중…";
      const fd = new FormData();
      files.forEach((f, i) => fd.append("photos", f, `page${i + 1}.jpg`));
      fd.append("typed_answer", form.querySelector("[name=typed_answer]").value);
      try {
        const r = await fetch(form.action, {method: "POST", body: fd});
        if (r.ok || r.redirected) {
          location.href = r.url || "/s?sent=1";
          return;
        }
        alert("제출 실패: " + (await r.text()).slice(0, 200));
      } catch {
        alert("제출 실패: 연결을 확인해 주세요");
      }
      btn.disabled = false;
      btn.textContent = "제출하기";
    });
  });
});

function shrink(file, max) {
  return new Promise((ok, fail) => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      c.toBlob((b) => b ? ok(b) : fail(), "image/jpeg", 0.82);
    };
    img.onerror = fail;
    img.src = URL.createObjectURL(file);
  });
}
