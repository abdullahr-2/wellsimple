"""Package the two public demo portals for Cloudflare Pages using an explicit asset list."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "wellsimple/static"
DEST = ROOT / "dist-pages"


def build():
    files = {f"static/{name}": (STATIC / name).read_bytes() for name in
             ("app.css", "manager.js", "crew.js", "common.js", "wellsimple-logo.png")}
    files["static/demo.js"] = (ROOT / "pages/demo.js").read_bytes()
    for portal, filename in (("manager", "index.html"), ("crew", "crew/index.html")):
        page = (STATIC / f"{portal}.html").read_text(encoding="utf-8")
        start = page.index('<div class="banner">')
        end = page.index("</div>", start) + len("</div>")
        page = page[:start] + ('<div class="banner">Public demo with fictional wells, repair notes and scores. '
                               'Assignments are saved in this browser. <button id="reset-demo" class="ghost">Reset demo</button></div>') + page[end:]
        page = page.replace('<script src="/static/common.js">', '<script src="/static/demo.js"></script>\n<script src="/static/common.js">')
        if portal == "crew":
            page = page.replace('<span class="grow"></span>', '<span class="grow"></span><a class="small" href="/">Manager</a>')
        files[filename] = page.encode()
    DEST.mkdir(exist_ok=True)
    with ZipFile(DEST / "wellsimple-pages.zip", "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    print(DEST / "wellsimple-pages.zip")


if __name__ == "__main__":
    build()
