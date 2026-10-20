"""Raster resource checks shared by compilation and published-pack validation."""
from __future__ import annotations

import io
import re
import warnings
from pathlib import Path

IMAGE_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def validate_image(data: bytes, name: str) -> None:
    """Decode a bounded, static raster; an extension/signature alone is insufficient."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("图片资源需要 Pillow: python3 -m pip install Pillow") from exc
    expected = IMAGE_FORMATS.get(Path(name).suffix.lower())
    if not expected or len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"不支持的图片格式或图片超过 25 MiB: {name}")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != expected or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("格式不匹配或图片超过 40MP")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("只支持静态图片")
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
    except Exception as exc:
        raise ValueError(f"无效图片 {name}: {exc}") from exc


def validate_visual_evidence(cap: dict, resources: dict[str, str | bytes]) -> None:
    """Check provenance/packaging contracts; this does not prove visual understanding."""
    evidence = cap.get("visual_evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("visual_evidence 必须是列表")
    ids = set()
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("visual_evidence 条目必须是 mapping")
        figure_id = item.get("figure_id")
        if not isinstance(figure_id, str) or not figure_id.strip() or figure_id in ids:
            raise ValueError("图例 figure_id 必须非空且在能力内唯一")
        ids.add(figure_id)
        if not isinstance(item.get("source_id"), str) or not item["source_id"].strip():
            raise ValueError(f"{figure_id}: 缺少 source_id")
        if not re.fullmatch(r"[a-f0-9]{64}", str(item.get("source_sha256", ""))):
            raise ValueError(f"{figure_id}: 需要原文件 source_sha256")
        page = item.get("pdf_page")
        if type(page) is not int or page < 1:
            raise ValueError(f"{figure_id}: pdf_page 必须是从 1 开始的 PDF 页序")
        if item.get("review_status") != "reviewed":
            raise ValueError(f"{figure_id}: 图文证据尚未核查，不能编译为 active 能力")
        for key in ("image", "detail_image", "notes"):
            if key == "detail_image" and key not in item:
                continue
            rel = item.get(key)
            if not isinstance(rel, str) or rel not in resources:
                raise ValueError(f"{figure_id}: {key} 必须在 resources 中显式声明")
            if key == "notes":
                if not isinstance(resources[rel], str) or not resources[rel].strip():
                    raise ValueError(f"{figure_id}: notes 必须是非空 UTF-8 图文核查记录")
            elif Path(rel).suffix.lower() not in IMAGE_FORMATS or not isinstance(resources[rel], bytes):
                raise ValueError(f"{figure_id}: {key} 必须是受支持的图片")


def visual_evidence_links(cap: dict, prefix: str = "") -> str:
    if not cap.get("visual_evidence"):
        return ""
    lines = ["", "## 图文证据", "",
             "涉及图形、编号或图文对应时，先实际打开完整图与核查记录，再按需放大局部。"
             "当前宿主不能看图时说明限制；记录中的推断不能冒充图中事实。", ""]
    for item in cap["visual_evidence"]:
        lines.extend([
            f"- 图例 {item['figure_id']} — 来源 {item['source_id']}，PDF 页序 {item['pdf_page']}，"
            f"书本页码 {item.get('printed_page') or '未核对'}；源文件 SHA256 `{item['source_sha256']}`",
            f"  - [完整图]({prefix}{item['image']}) · [图文核查记录]({prefix}{item['notes']})",
        ])
        if item.get("detail_image"):
            lines.append(f"  - [局部放大图]({prefix}{item['detail_image']})（结合完整图阅读）")
    return "\n".join(lines) + "\n"
