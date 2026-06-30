#!/usr/bin/env python3
"""Convert a Markdown file to a clean A4 PDF via google-chrome --headless.

Usage:
    python tools/md_to_pdf.py input.md output.pdf
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import markdown


CSS = """
@page { size: A4; margin: 1.8cm 1.5cm 1.8cm 1.5cm;
        @bottom-center { content: "Pagina " counter(page) " di " counter(pages); font-size: 9pt; color: #888; }
        @top-right { content: "AIFA CDSS — Revisione Clinica"; font-size: 9pt; color: #888; }
}
body { font-family: 'DejaVu Sans', 'Inter', system-ui, sans-serif; font-size: 10.5pt;
       line-height: 1.45; color: #1a1a1a; max-width: 100%; margin: 0; }
h1 { font-size: 22pt; color: #1d3557; border-bottom: 3px solid #1d3557; padding-bottom: 8px; margin-top: 24px; page-break-after: avoid; }
h2 { font-size: 16pt; color: #1d3557; margin-top: 32px; padding-top: 6px; border-top: 2px solid #e7eaf0; page-break-before: auto; page-break-after: avoid; }
h3 { font-size: 13pt; color: #2b3a55; margin-top: 18px; page-break-after: avoid; }
h4 { font-size: 11.5pt; color: #2b3a55; margin-top: 14px; padding: 6px 10px; background: #f3f4f8; border-left: 4px solid #4a6fa5; page-break-after: avoid; }
p { margin: 6px 0; }
code, tt { font-family: 'DejaVu Sans Mono', Menlo, monospace; font-size: 9.5pt;
           background: #f3f4f8; padding: 1px 5px; border-radius: 3px; color: #b04050; }
pre { background: #f8f9fb; border: 1px solid #d8dde8; border-radius: 4px; padding: 10px 12px;
      font-size: 9pt; line-height: 1.35; overflow-x: hidden; white-space: pre-wrap; word-wrap: break-word;
      page-break-inside: avoid; }
pre code { background: transparent; color: #1a1a1a; padding: 0; }
blockquote { border-left: 4px solid #7a96c3; background: #f5f8fc; padding: 8px 14px;
             margin: 10px 0; color: #2b3a55; font-style: italic; page-break-inside: avoid; }
blockquote p { margin: 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 10pt; page-break-inside: avoid; }
th, td { border: 1px solid #d8dde8; padding: 5px 8px; text-align: left; vertical-align: top; }
th { background: #eef0f5; font-weight: 600; }
ul, ol { margin: 6px 0 6px 20px; padding-left: 6px; }
li { margin: 2px 0; }
strong { color: #1a1a1a; }
details { background: #f8f9fb; border: 1px solid #d8dde8; border-radius: 4px;
          padding: 6px 12px; margin: 8px 0; page-break-inside: avoid; }
summary { font-weight: 600; cursor: pointer; color: #2b3a55; }
hr { border: none; border-top: 2px solid #d0d4de; margin: 20px 0; page-break-after: avoid; }
"""


def main(md_path: Path, pdf_path: Path) -> int:
    md_text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc", "md_in_html"],
    )
    html_doc = (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<title>Pacchetto Revisione Clinica</title>"
        f"<style>{CSS}</style></head><body>{html_body}</body></html>"
    )

    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "input.html"
        html_path.write_text(html_doc, encoding="utf-8")
        # Chrome headless print-to-pdf
        cmd = [
            "google-chrome",
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            f"file://{html_path}",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            print("Chrome stderr:", res.stderr, file=sys.stderr)
            return res.returncode
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.md output.pdf", file=sys.stderr)
        sys.exit(2)
    rc = main(Path(sys.argv[1]), Path(sys.argv[2]))
    if rc == 0:
        print(f"OK → {sys.argv[2]}", file=sys.stderr)
    sys.exit(rc)
