# Visual Book Skills · 图文知行

Turn a book's text, figures and worked examples into source-linked Agent Skills.

[中文](./README.md) · [Skill entrypoint](./SKILL.md) · [Visual reading workflow](./methodology/08-visual-reading.md) · [MIT License](./LICENSE)

## Purpose

Methods in technical books often depend on a diagram, a chart and the surrounding explanation. Visual Book Skills keeps that evidence connected, then turns supported methods into reusable capability cards with inputs, steps, conditions, counterexamples and completion criteria.

This is an agent-driven reading and skill-building workflow. The model interprets and checks sources; local Python tools prepare PDF pages, compile declared resources and manage output versions. It works with chart-heavy books, manuals and course notes, as well as prose and transcripts already obtained by the user.

## Capabilities

- Render selected PDF pages, including vector graphics and annotations; retain a full page alongside optional crops.
- Link figures to source fingerprints, PDF page positions, verified printed page labels and explanatory text.
- Record visible facts, author explanations, model inferences and unresolved issues separately.
- Compile explicitly declared static PNG/JPEG/WebP images and review notes into both single and pack outputs.
- Include image bytes in publication hashes, local-edit detection, snapshots, patch validation and rollback.
- Require context preservation and future-information masking for time-series judgment tasks.

Brooks price-action books informed the chart-reading workflow. This does not establish trading performance or general chart-analysis accuracy.

## Installation

Use a host that supports local Agent Skills, file access and Python commands. Visual tasks also require an image-viewing tool.

Place the complete source tree in the host's supported skill directory, using `visual-book-skills` as the directory name. From that directory:

```bash
git clone https://github.com/savagealexander/visual-book-skills.git visual-book-skills
cd visual-book-skills
python -m pip install pyyaml
python scripts/cangjie.py doctor
```

For visual work:

```bash
python -m pip install Pillow pypdf
```

Install Poppler and expose `pdfinfo` and `pdftoppm` on PATH. Text extraction uses `pdftotext` when available, otherwise optional `pypdf`. If neither is available, pages still render and the manifest explicitly records unavailable text extraction.

The legacy `scripts/cangjie.py` command, `.cangjie/` storage and schema names remain compatible with the inherited toolchain. Reload skills using the host's mechanism after installation. Upstream release archives and older installations do not include this fork's changes.

## Use with an agent

For example:

> Use visual-book-skills to read chapter one of this book. Inspect the original figures alongside captions and explanatory text. Extract methods with source locations, conditions, counterexamples and unresolved questions.

The workflow establishes scope, locates figure/text relationships, opens the relevant images, reviews supported methods, constructs capability cards and tests representative tasks before delivery.

A generated skill can then be asked to apply the book's methods to a new case and explain supporting evidence, opposing evidence and missing inputs. Its accuracy depends on source coverage, compilation quality, the underlying model and evaluation.

## Prepare pages directly

```bash
python scripts/cangjie.py render-pages --pdf "/path/book.pdf" --pages 18-20 --source-id src-book --out "/path/new-page-directory"
```

Page selection uses 1-based PDF positions, which may differ from printed page labels. Printed labels must be verified separately.

After inspecting the full page, create a crop when useful:

```bash
python scripts/cangjie.py render-pages --pdf "/path/book.pdf" --pages 18 --source-id src-book --max-edge 4800 --crop "0.08,0.12,0.94,0.70" --out "/path/new-detail-directory"
```

Crop coordinates are normalized `x0,y0,x1,y1` from the full page's top-left corner; choose values from the actual page. The full page is retained and the output directory must be new.

Outputs include PNGs, optional crops, extracted text and a source manifest. Preparation does not perform OCR or interpret figures. Pages start as `unreviewed`; an agent or reader must actually inspect them and check the relevant text.

## Deliverables

The reading workspace retains the overview, candidate methods, source checks, glossary, coverage audit and unresolved issues. Verified methods are stored in a Capability Bundle and compiled as:

- **single**: one discoverable entrypoint with internal capability cards.
- **pack**: one source router plus a small number of promoted standalone skills.

Visual capabilities may carry full images, details, source locations and review notes. Only declared resources are packaged.

[Capability construction](./methodology/04-stage2-ria-plus.md) · [Visual evidence template](./templates/FIGURE_EVIDENCE.md.template) · [Delivery](./methodology/07-stage5-deliver.md)

## Limits and validation

The tools do not automatically perform OCR, identify figure numbers or establish semantic correctness. A `reviewed` flag is a recorded review decision; successful compilation is not proof of correct interpretation. Missing conditions or unreadable evidence must remain unresolved.

Supported image resources are static PNG/JPEG/WebP, at most 25 MiB and 40MP each. The text-oriented `update --add` command does not track image changes automatically; update the Bundle, re-review affected evidence and recompile.

At the visual enhancement commit, 40 local tests passed and one symlink test was skipped for Windows permissions. Tests cover rendering, crops, resource integrity, output variants, image patches and rollback. One local Brooks figure was visually inspected. Whole-book comprehension, unseen-chart accuracy and trading outcomes have not been established.

```bash
python -m pip install pyyaml Pillow pypdf jsonschema
python -m unittest discover -s tests -v
```

Rendering integration tests require Poppler and are skipped when dependencies are unavailable.

## Origin and license

Maintained by [savagealexander](https://github.com/savagealexander), based on [kangarooking/cangjie-skill](https://github.com/kangarooking/cangjie-skill).

The upstream project supplied the method-extraction, verification, capability-card and compilation foundation. This fork adds source-linked visual reading, PDF page preparation, raster-resource support and regression tests, with its own project name and documentation. Inherited examples, historical documentation and website code have not necessarily been revalidated for this fork.

The project retains the upstream [MIT License](./LICENSE). Books, courses and figures remain subject to their own rights; the software license does not grant redistribution rights to source materials.
