import copy
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml
from PIL import Image
from jsonschema import Draft202012Validator

import test_compile_resources as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_skill_patch import apply_patch, restore
from cangjie_common import detect_local_edits, sha256_file
from visual_resources import validate_image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def image_bytes(color="red", format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(output, format=format)
    return output.getvalue()


class VisualResourceTests(unittest.TestCase):
    setUp = fixtures.ResourceCompileTests.setUp
    write = fixtures.ResourceCompileTests.write
    compile = fixtures.ResourceCompileTests.compile

    def prepare_images(self):
        self.write("book/overview.md", "# Synthetic overview\n")
        self.write("book/glossary.md", "# Synthetic glossary\n")
        self.write("resources/figures/notes.md", "# Evidence\n\n[Full page](page.png)\nVisible red rectangle.\n")
        self.image = self.root / "resources/figures/page.png"
        self.image.write_bytes(image_bytes())
        self.cap = self.bundle["capabilities"][0]
        self.cap["resources"] = ["resources/figures/page.png", "resources/figures/notes.md"]
        self.cap["visual_evidence"] = [{
            "figure_id": "fig-synthetic", "source_id": "src-test", "source_sha256": "a" * 64,
            "pdf_page": 3, "printed_page": None, "image": "resources/figures/page.png",
            "notes": "resources/figures/notes.md", "review_status": "reviewed",
        }]

    def test_all_delivery_modes_preserve_images_and_resolve_evidence_links(self):
        self.prepare_images()
        self.write("verified.yaml", yaml.safe_dump(self.bundle))
        for mode in ("single", "pack"):
            out = self.root / ("out-" + mode)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "cangjie.py"), "compile", "--bundle", str(self.root),
                 "--out", str(out), "--output", mode], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            roots = [out] if mode == "single" else [out / "handbook", out / "calculate"]
            for root in roots:
                self.assertEqual((root / "resources/figures/page.png").read_bytes(), self.image.read_bytes())
                card = root / ("SKILL.md" if root.name == "calculate" else "references/capabilities/calculate.md")
                self.assertIn("图文证据", card.read_text(encoding="utf-8"))
                self.assertIn("PDF 页序 3", card.read_text(encoding="utf-8"))
            manifest = json.loads((out / "BUILD_MANIFEST.json").read_text(encoding="utf-8"))
            rel = str((roots[0] / "resources/figures/page.png").relative_to(out))
            self.assertEqual(manifest["published_hashes"][rel], sha256_file(self.image))
            self.assertEqual(detect_local_edits(out), [])
            (roots[0] / "resources/figures/page.png").write_bytes(image_bytes("blue"))
            self.assertIn(rel, detect_local_edits(out))

    def test_visual_evidence_requires_review_provenance_and_declared_files(self):
        self.prepare_images()
        original = copy.deepcopy(self.cap["visual_evidence"][0])
        for change in ({"review_status": "needs_review"}, {"pdf_page": 0}, {"pdf_page": True},
                       {"source_sha256": "unknown"}, {"image": "resources/missing.png"},
                       {"notes": "resources/figures/page.png"}, {"detail_image": "missing.png"}):
            with self.subTest(change=change):
                self.cap["visual_evidence"] = [{**original, **change}]
                with self.assertRaises(ValueError):
                    self.compile()
        self.cap["visual_evidence"] = [original, original]
        with self.assertRaises(ValueError):
            self.compile()

    def test_visual_evidence_schema_matches_metadata(self):
        self.prepare_images()
        schema = json.loads((SCRIPTS.parent / "schemas/capability.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(self.cap)
        for key in ("source_sha256", "pdf_page", "image", "notes", "review_status"):
            broken = copy.deepcopy(self.cap)
            del broken["visual_evidence"][0][key]
            self.assertTrue(list(validator.iter_errors(broken)), key)

    def test_undeclared_images_are_not_published(self):
        self.prepare_images()
        (self.root / "resources/figures/private.png").write_bytes(image_bytes("green"))
        self.assertNotIn("resources/figures/private.png", self.compile())
        self.assertFalse(any(p.endswith("private.png") for p in self.compile(pack=True)))

    def test_invalid_images_cannot_hide_as_utf8(self):
        for data, name in ((b"not an image", "fake.png"),
                           (b"\x89PNG\r\n\x1a\n", "truncated.png"),
                           (image_bytes(format="JPEG"), "wrong.png")):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_image(data, name)
        for format, suffix in (("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")):
            validate_image(image_bytes(format=format), "valid." + suffix)

    def test_png_animation_rejected(self):
        output = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(
            output, format="PNG", save_all=True,
            append_images=[Image.new("RGB", (8, 8), "blue")], duration=100, loop=0)
        with self.assertRaises(ValueError):
            validate_image(output.getvalue(), "animation.png")

    def test_binary_patch_and_rollback_preserve_original_image(self):
        self.prepare_images()
        target, patch, snapshots = self.root / "target", self.root / "patch", self.root / "snapshots"
        from compile_single import write_tree
        write_tree(self.compile(), target)
        edited = patch / "resources/figures/page.png"
        edited.parent.mkdir(parents=True)
        edited.write_bytes(image_bytes("blue"))
        self.assertEqual(apply_patch(target, patch, snapshots), 0)
        self.assertEqual((target / "resources/figures/page.png").read_bytes(), edited.read_bytes())
        snapshot = next(snapshots.iterdir())
        restore(target, snapshot)
        self.assertEqual((target / "resources/figures/page.png").read_bytes(), self.image.read_bytes())

    def test_corrupt_image_patch_rolls_back(self):
        self.prepare_images()
        from compile_single import write_tree
        target, patch = self.root / "target", self.root / "patch"
        write_tree(self.compile(), target)
        broken = patch / "resources/figures/page.png"
        broken.parent.mkdir(parents=True)
        broken.write_bytes(b"broken")
        with self.assertRaises(SystemExit):
            apply_patch(target, patch, self.root / "snapshots")
        self.assertEqual((target / "resources/figures/page.png").read_bytes(), self.image.read_bytes())


if __name__ == "__main__":
    unittest.main()
