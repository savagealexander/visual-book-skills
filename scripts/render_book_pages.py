#!/usr/bin/env python3
"""Prepare selected PDF pages for visual reading; never claims to interpret them.

Requires Poppler (pdfinfo, pdftoppm) and Pillow.
Text extraction uses pdftotext or optional pypdf; unavailable text is explicitly recorded.
PDF page numbers are 1-based file positions, not printed book page numbers.
Output must be a new directory; source revisions must not overwrite review evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from visual_resources import validate_image


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_tool(name: str, args: list[str], timeout: int = 120) -> str:
    binary = shutil.which(name)
    if not binary:
        raise ValueError(f"缺少 Poppler 工具 {name}，请安装 Poppler 并加入 PATH")
    env = {**os.environ, "LC_ALL": "C", "LANG": "C"}
    result = subprocess.run([binary, *args], capture_output=True, env=env, timeout=timeout)
    if result.returncode:
        raise ValueError(f"{name} 失败: {result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout.decode("utf-8", errors="replace")


def parse_pages(spec: str, count: int) -> list[int]:
    pages = set()
    for part in spec.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:-(\d+))?\s*", part)
        if not match:
            raise ValueError("页码格式为 1,4-6（从 1 开始的 PDF 页序）")
        start, end = int(match[1]), int(match[2] or match[1])
        if not 1 <= start <= end <= count:
            raise ValueError(f"页序超出范围或顺序反向: {part}，PDF 共 {count} 页")
        pages.update(range(start, end + 1))
    return sorted(pages)


def parse_crop(spec: str | None) -> list[float] | None:
    if spec is None:
        return None
    try:
        values = [float(n) for n in spec.split(",")]
    except ValueError as exc:
        raise ValueError("crop 为相对页面左上角的 x0,y0,x1,y1（0..1）") from exc
    if len(values) != 4 or not (0 <= values[0] < values[2] <= 1 and 0 <= values[1] < values[3] <= 1):
        raise ValueError("crop 必须满足 0<=x0<x1<=1 且 0<=y0<y1<=1")
    return values


def extract_page_text(pdf: Path, number: int, dest: Path) -> str:
    if shutil.which("pdftotext"):
        run_tool("pdftotext", ["-f", str(number), "-l", str(number), "-layout",
                              "-enc", "UTF-8", str(pdf), str(dest)])
        return "pdftotext"
    try:
        from pypdf import PdfReader
    except ImportError:
        dest.write_text("", encoding="utf-8")
        return "unavailable"
    with pdf.open("rb") as stream:
        reader = PdfReader(stream)
        dest.write_text(reader.pages[number - 1].extract_text() or "", encoding="utf-8")
    return "pypdf"


def render(pdf: Path, out: Path, pages: str, source_id: str,
           max_edge: int = 3200, crop: str | None = None,
           printed_page: str | None = None) -> dict:
    from PIL import Image

    pdf, out = pdf.resolve(), out.absolute()
    if not pdf.is_file():
        raise ValueError(f"PDF 不存在: {pdf}")
    if out.exists() or out.is_symlink():
        raise ValueError(f"输出目录已存在，请选择新目录以保留旧证据: {out}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", source_id):
        raise ValueError("source-id 使用小写字母、数字和连字符")
    if not 512 <= max_edge <= 6000:
        raise ValueError("max-edge 范围为 512..6000 像素")
    crop_box = parse_crop(crop)
    info = run_tool("pdfinfo", [str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if not match:
        raise ValueError("无法确定 PDF 总页数")
    total = int(match[1])
    selected = parse_pages(pages, total)
    if (crop_box or printed_page is not None) and len(selected) != 1:
        raise ValueError("crop / printed-page 只用于单页任务，避免错误关联")
    source_sha = file_digest(pdf)
    manifest = {
        "schema_version": 1, "source_id": source_id, "source_filename": pdf.name,
        "source_sha256": source_sha, "pdf_page_count": total,
        "selected_pdf_pages": selected, "max_edge": max_edge, "pages": [],
        "note": "仅页面准备，未执行 OCR 或视觉理解；printed_page 需人工核对。路径相对于本清单。",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    # Work in a sibling directory; failures do not leave a plausible finished corpus.
    with tempfile.TemporaryDirectory(prefix=".render-", dir=out.parent) as temp:
        staging = Path(temp) / "pages"
        staging.mkdir()
        for number in selected:
            stem = f"page-{number:04d}"
            image_path = staging / f"{stem}.png"
            text_path = staging / f"{stem}.txt"
            run_tool("pdftoppm", ["-f", str(number), "-l", str(number), "-singlefile",
                                 "-scale-to", str(max_edge), "-png", str(pdf), str(staging / stem)])
            text_method = extract_page_text(pdf, number, text_path)
            data = image_path.read_bytes()
            validate_image(data, image_path.name)
            text = text_path.read_text(encoding="utf-8")
            record = {
                "page_id": f"{source_id}-{source_sha[:12]}-p{number:04d}",
                "pdf_page": number, "printed_page": printed_page,
                "image": image_path.name, "image_sha256": hashlib.sha256(data).hexdigest(),
                "text": text_path.name, "text_sha256": hashlib.sha256(text_path.read_bytes()).hexdigest(),
                "text_method": text_method,
                "text_status": ("unavailable" if text_method == "unavailable" else
                                "present" if text.strip() else "empty-needs-visual-reading-or-ocr"),
                "review_status": "unreviewed",
            }
            with Image.open(image_path) as image:
                record["width"], record["height"] = image.size
                if crop_box:
                    box = (round(crop_box[0] * image.width), round(crop_box[1] * image.height),
                           round(crop_box[2] * image.width), round(crop_box[3] * image.height))
                    if box[0] >= box[2] or box[1] >= box[3]:
                        raise ValueError("裁切区域小于一个像素")
                    detail = staging / f"{stem}-detail.png"
                    image.crop(box).save(detail)
                    record["detail_image"] = detail.name
                    record["detail_sha256"] = hashlib.sha256(detail.read_bytes()).hexdigest()
                    record["crop_normalized_xyxy"] = crop_box
                    record["crop_pixels_xyxy"] = list(box)
            manifest["pages"].append(record)
        if file_digest(pdf) != source_sha:
            raise ValueError("源 PDF 在渲染期间发生变化，请重新运行")
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if out.exists():
            raise ValueError(f"输出目录已被其他任务创建: {out}")
        staging.rename(out)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pages", required=True, help="PDF 页序，例如 1,4-6")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--max-edge", type=int, default=3200)
    parser.add_argument("--crop", help="单页局部裁切 x0,y0,x1,y1，归一化坐标；始终保留完整图")
    parser.add_argument("--printed-page", help="人工核实的书本页码，仅单页可用；默认未知")
    args = parser.parse_args()
    try:
        result = render(args.pdf, args.out, args.pages, args.source_id,
                        args.max_edge, args.crop, args.printed_page)
    except (ValueError, OSError, ImportError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"图页准备失败: {exc}\n")
    print(f"已准备 {len(result['pages'])} 页: {args.out / 'manifest.json'}")
    print("状态: unreviewed。必须实际打开图页并核对正文，才能建立 visual_evidence。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
