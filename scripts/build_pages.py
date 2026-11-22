"""Build the Pages frontend and its authenticated API. All data lives outside this directory."""
from pathlib import Path
from shutil import copyfile

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "wellsimple" / "static"
DEST = ROOT / "dist-pages" / "site"


def build():
    (DEST / "static").mkdir(parents=True, exist_ok=True)
    (DEST / "crew").mkdir(exist_ok=True)
    for name in ("manager.js", "crew.js", "common.js", "app.css", "wellsimple-logo.png"):
        copyfile(STATIC / name, DEST / "static" / name)
    copyfile(ROOT / "pages" / "model.js", DEST / "static" / "model.js")
    manager = (STATIC / "manager.html").read_text(encoding="utf-8")
    manager = manager.replace('<script src="/static/manager.js">', '<script src="/static/model.js"></script>\n<script src="/static/manager.js">')
    (DEST / "index.html").write_text(manager, encoding="utf-8")
    copyfile(STATIC / "crew.html", DEST / "crew" / "index.html")
    copyfile(ROOT / "pages" / "worker.js", DEST / "_worker.js")
    print(DEST)


if __name__ == "__main__":
    build()
