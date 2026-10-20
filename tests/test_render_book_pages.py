import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_book_pages import extract_page_text, parse_crop, parse_pages, render


def synthetic_pdf(path):
    """Two self-authored pages: vectors/text, then vectors without a text layer."""
    contents = [
        b"1 0 0 rg 50 50 100 80 re f\nBT /F1 18 Tf 30 170 Td (Figure A) Tj ET",
        b"0 0 1 rg 50 50 100 80 re f",
    ]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << >> /Contents 7 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        *[b"<< /Length " + str(len(c)).encode() + b" >>\nstream\n" + c + b"\nendstream" for c in contents],
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(data)


class PageSelectionTests(unittest.TestCase):
    def test_missing_text_extractor_is_not_misreported_as_empty_source(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "page.txt"
            with patch("render_book_pages.shutil.which", return_value=None), patch.dict(sys.modules, {"pypdf": None}):
                self.assertEqual(extract_page_text(Path("unused.pdf"), 1, dest), "unavailable")
            self.assertEqual(dest.read_bytes(), b"")

    def test_selection_is_bounded_and_deduplicated(self):
        self.assertEqual(parse_pages("3,1-2,2", 3), [1, 2, 3])
        for spec in ("0", "2-1", "1-999999999", "1,", "abc", "-1"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                parse_pages(spec, 3)

    def test_crop_rejects_outside_reversed_and_nonfinite(self):
        self.assertEqual(parse_crop("0.1,0.2,0.8,0.9"), [0.1, 0.2, 0.8, 0.9])
        for spec in ("-0.1,0,1,1", "0,0,0,1", "0,0,1,2", "0,0,nan,1", "0,1", "x"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                parse_crop(spec)


@unittest.skipUnless(all(shutil.which(t) for t in ("pdfinfo", "pdftoppm")) and
                     (shutil.which("pdftotext") or importlib.util.find_spec("pypdf")), "requires Poppler and text extraction")
class RenderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root / "source with spaces.pdf"
        synthetic_pdf(self.pdf)

    def test_vectors_text_page_identity_and_unreviewed_state(self):
        out = self.root / "pages"
        manifest = render(self.pdf, out, "1-2", "src-test", max_edge=800)
        self.assertEqual(manifest["source_sha256"], hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        self.assertEqual([p["pdf_page"] for p in manifest["pages"]], [1, 2])
        for page in manifest["pages"]:
            self.assertEqual(page["review_status"], "unreviewed")
            self.assertIsNone(page["printed_page"])
            self.assertEqual(hashlib.sha256((out / page["image"]).read_bytes()).hexdigest(), page["image_sha256"])
        self.assertIn("Figure A", (out / "page-0001.txt").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pages"][1]["text_status"], "empty-needs-visual-reading-or-ocr")
        with Image.open(out / "page-0001.png") as image:
            r, g, b = image.convert("RGB").getpixel((260, 260))
            self.assertGreater(r, 200)
            self.assertLess(g, 50)
            self.assertLess(b, 50)
        self.assertEqual(json.loads((out / "manifest.json").read_text(encoding="utf-8")), manifest)
        with self.assertRaises(ValueError):
            render(self.pdf, out, "1", "src-test")

    def test_crop_keeps_original_context(self):
        out = self.root / "crop"
        manifest = render(self.pdf, out, "1", "src-test", max_edge=800,
                          crop="0.1,0.2,0.7,0.9", printed_page="iii")
        page = manifest["pages"][0]
        self.assertEqual(page["printed_page"], "iii")
        with Image.open(out / page["image"]) as full, Image.open(out / page["detail_image"]) as detail:
            self.assertGreater(full.width, detail.width)
            self.assertEqual(detail.tobytes(), full.crop(tuple(page["crop_pixels_xyxy"])).tobytes())

    def test_failure_does_not_create_final_output(self):
        out = self.root / "bad"
        for kwargs in ({"pages": "3"}, {"pages": "1-2", "crop": "0,0,1,1"}, {"pages": "1", "max_edge": 10000}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                render(self.pdf, out, source_id="src-test", **kwargs)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
