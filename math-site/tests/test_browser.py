import shutil
import subprocess
from pathlib import Path

import pytest


def test_photo_reselection_discards_late_conversions_and_recovers_failed_fetch():
    node = shutil.which("node")
    if not node:
        pytest.skip("사진 업로드 테스트에 Node.js가 필요해요")
    script = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
    subprocess.run([node, "-e", r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
let change, submit;
const previews = [];
const alerts = [];
const pending = {};
const uploads = [];
const input = {files: [], addEventListener: (_, handler) => change = handler};
const button = {};
const box = {set innerHTML(_) { previews.length = 0; }, appendChild: img => previews.push(img.src)};
const form = {
  action: "/submit",
  querySelector(sel) {
    return {"input[type=file]": input, ".previews": box, "button[type=submit]": button,
            "[name=typed_answer]": {value: "7"}}[sel];
  },
  addEventListener: (_, handler) => submit = handler
};
const context = vm.createContext({
  document: {
    addEventListener: (_, handler) => handler(),
    querySelectorAll: () => [form],
    createElement: () => ({})
  },
  setInterval: () => 0,
  URL: {createObjectURL: file => file},
  FormData: class {
    constructor() { this.photos = []; }
    append(key, value) { if (key === "photos") this.photos.push(value); }
  },
  fetch: async (_, {body}) => {
    uploads.push(body.photos);
    throw new Error("offline");
  },
  alert: message => alerts.push(message)
});
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), context);
context.shrink = file => new Promise(resolve => pending[file] = resolve);

(async () => {
  input.files = ["old"];
  const old = change();
  input.files = ["new1", "new2"];
  const current = change();
  pending.new1("small1");
  await new Promise(setImmediate);
  pending.new2("small2");
  await current;
  pending.old("stale");
  await old;
  assert.deepEqual(previews, ["small1", "small2"]);
  await submit({preventDefault() {}});
  assert.deepEqual(uploads, [["small1", "small2"]]);
  assert.equal(alerts.length, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, "제출하기");
})().catch(error => { console.error(error); process.exitCode = 1; });
""", str(script)], check=True, timeout=10)
