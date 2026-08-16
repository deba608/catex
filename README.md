# Catalogue Importer

A fast, **fully-local** tool that converts a product catalogue **PDF** into a clean,
import-ready dataset. Drop in your PDF and get back a product list, a size-variant
list, a database import script, and every product photo — ready to load into an
e-commerce website.

It runs in two ways, depending on your preference:

- **Web App** — a browser-based interface (Flask) at `http://localhost:5000`
- **Native Desktop App** — a standalone windowed GUI (CustomTkinter), no browser needed

Both modes share the **same extraction engine** (`catalogue_extractor.process_catalogue`),
so output is identical no matter how you run it.

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Running the Web App](#running-the-web-app)
5. [Running the Native Desktop App](#running-the-native-desktop-app)
6. [What You Get (Output Files)](#what-you-get-output-files)
7. [Smart Features & Error Handling](#smart-features--error-handling)
8. [Importing SQL into PostgreSQL / Supabase](#importing-sql-into-postgresql--supabase)
9. [Building a Standalone Executable (PyInstaller)](#building-a-standalone-executable-pyinstaller)
10. [Project Structure](#project-structure)
11. [Limitations](#limitations)
12. [License](#license)

---

## How It Works

The tool expects catalogues shaped like **Kanha Brothers'** catalogue, where each
product appears as:

- A **product code (SKU)** — e.g. `KB1`, `KB12`, `CP1598`, `SKU-004`
- A **photo** of the item
- A **size table** per item (e.g. `10 x 15 cm`, `10 x 15 in`, `8"`)

The extractor scans every page, matches SKU codes, reads the dimension rows, and
pulls out the product photos. It works on **any similarly-structured catalogue** —
not just Kanha Brothers.

Because everything runs on your own machine, **no data ever leaves your computer**.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.9 or newer | Tested on Windows, Linux, macOS |
| **pip** | Recent | Bundled with Python |

---

## Installation

Clone the repository and install the Python dependencies:

```bash
git clone https://github.com/deba608/catex.git
cd catex

# Create a virtual environment (recommended)
python -m venv .venv

# Activate it
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

`requirements.txt` installs:

| Package | Purpose |
|---|---|
| `flask` | Powers the local web server |
| `pymupdf` | PDF text + image extraction |
| `customtkinter` | Native desktop GUI |
| `pyinstaller` | Bundling the desktop app into an `.exe` |

> **Note:** The repository includes a `.venv` directory. If you cloned the repo with
> an existing virtual environment, you can reuse it with `source .venv/bin/activate`
> (Linux/macOS) or `.venv\Scripts\Activate.ps1` (Windows).

---

## Running the Web App

**Option A (recommended for browser users):**

1. Start the server:

   ```bash
   python app.py
   ```

   - On Linux/macOS you can also use the helper script:

     ```bash
     ./run.sh
     ```

     (`run.sh` installs dependencies on first run, then starts the server.)

2. Open your browser and go to: **http://localhost:5000**

3. **Drag & drop** your catalogue PDF onto the upload zone, or **click** to browse
   for a file.

4. Watch the **real-time extraction progress** in the UI.

5. When finished, **download** each generated file (CSV, JSON, SQL, photos) using the
   buttons, or **open the output folder** directly.

> The web server listens on `127.0.0.1:5000` and is local-only by design.
> Uploads are capped at **100 MB**.

---

## Running the Native Desktop App

If you prefer a standalone window instead of a browser:

```bash
python desktop_app.py
```

A desktop window will open. From there you can:

1. **Browse** for a PDF (or see the drop-zone prompt).
2. Watch the **progress bar** as pages are processed.
3. Review the **summary cards** (products found, size variants, photos extracted,
   missing photos).
4. **Save As…** any generated file to a location of your choice, or **open the
   output folder**.

The desktop app stores its output under a timestamped `run-YYYYMMDD-HHMMSS`
folder inside your app-data directory (see [Project Structure](#project-structure)).

---

## What You Get (Output Files)

After processing, the tool writes the following into the output folder:

| File | Format | Description |
|---|---|---|
| **Product list** | `products.csv` | Every SKU found: name, status (`active`/`coming_soon`), photo availability, and variant count. Ready for Excel / Google Sheets. |
| **Sizes list** | `variants.csv` | Every size variant per product, converted to centimetres (W × H). |
| **Full data file** | `products.json` | Structured JSON with nested `variants` and metadata for developers. |
| **Database file** | `import.sql` | Production-ready **PostgreSQL / Supabase** script that creates tables and seeds products + variants. |
| **All photos** | `photos.zip` | Extracted product photos, automatically named by SKU (e.g. `KB1.jpg`). |
| **Summary** | `summary.json` | Statistics: total products, photos extracted, active/coming-soon counts, missing-photo SKUs. |

> In the web app, these are downloadable from the results screen. In the desktop app,
> use the **Save As…** button next to each file. The web app also exposes an
> **Open Folder** button to view the raw output directory.

---

## Smart Features & Error Handling

- **Missing Photo Detection** — Flags products that have size specifications but no
  photo (e.g. placeholder or "Coming Soon" listings), and reports the exact list of
  SKUs that still need photography.
- **Flexible Dimension Parsing** — Recognises centimetres (`10cm x 15cm`), inches
  (`10 x 15 in`, `8"`), and bare dimension pairs, automatically converting everything
  to centimetres.
- **Robust Upload & Processing Pipeline** — Prevents browser navigation hijacks on
  drag-and-drop, retries transient polling gracefully, and avoids UI lockups or
  unexpected page resets.
- **Live Progress** — Both UIs report per-page progress in real time.
- **Clear Errors** — Uploading a non-PDF, or processing a PDF with no detected SKUs,
  produces a friendly, actionable message instead of a silent failure.

---

## Importing SQL into PostgreSQL / Supabase

The generated `import.sql` is designed for PostgreSQL and Supabase.

1. It creates two tables if they don't already exist:

   - `products` — `id`, `sku` (unique), `name`, `status`, `has_photo`, `created_at`
   - `product_variants` — `id`, `product_id` (FK), `variant_label`, `width_cm`,
     `height_cm`, `raw_dimension`, `price`, `created_at`

2. It inserts products and variants using a `JOIN ... ON sku` approach so variants
   are correctly linked to their parent product rows.

To import via the `psql` command line:

```bash
psql "YOUR_DATABASE_CONNECTION_STRING" -f import.sql
```

To import in the **Supabase SQL editor**:

1. Open your Supabase project → **SQL Editor**.
2. Copy the entire contents of `import.sql` into the editor.
3. Click **Run**.

> Note: `product_variants` includes an empty `price` column (NULL by default) — fill
> this in with your own wholesale/retail pricing after import.

---

## Building a Standalone Executable (PyInstaller)

To package the **native desktop app** into a single Windows executable so it runs
without Python installed:

```bash
pip install pyinstaller
pyinstaller build.spec
```

This produces **`CatalogueImporter.exe`** (with the `icon.ico` icon) inside the
`dist/` folder. You can then distribute that single file to end users — it bundles
the CustomTkinter GUI, PyMuPDF native libraries, and theme/font assets.

- Use `build.spec` for the standalone (single-file) desktop build.
- The spec excludes the Flask/werkzeug/jinja2 stack (not needed for the desktop app)
  to keep the executable smaller.

> A `CatalogueImporter_debug.spec` is also present for debugging builds.

---

## Project Structure

```
catex/
├── app.py                    # Flask web server + REST API (upload/status/download)
├── desktop_app.py            # Native CustomTkinter GUI
├── catalogue_extractor.py    # Shared extraction engine (PDF → CSV/JSON/SQL/photos)
├── build.spec                # PyInstaller spec → single-file desktop .exe
├── CatalogueImporter_debug.spec
├── requirements.txt          # Python dependencies
├── run.sh                    # One-command launcher for Linux/macOS
├── icon.ico                  # App icon
├── templates/                # Web UI HTML templates
├── static/                   # Web UI CSS/JS assets
├── build/                    # PyInstaller build output (generated)
└── dist/                     # PyInstaller distributable .exe (generated)
```

**Where output & uploaded files are stored:**

| Platform | Web app data dir | Desktop app data dir |
|---|---|---|
| Windows | `%APPDATA%\CatalogueImporter\` | `%APPDATA%\CatalogueImporter\native\` |
| macOS / Linux | `~/.catalogue_importer/` | `~/.catalogue_importer/native/` |

- **Web app:** uploads go to `.../uploads/`, outputs to `.../outputs/<job-id>/`.
- **Desktop app:** each run is saved in a timestamped `run-YYYYMMDD-HHMMSS/` folder.

You can override the data location for the web app with the environment variable
`CATALOGUE_DATA_DIR`.

---

## Limitations

- **Image Extraction** — Only extracts photos that are *embedded* in the PDF itself.
  Scanned, non-text PDFs (no selectable text) or missing catalogue photos cannot be
  auto-generated.
- **SKU Formats** — Matches alphanumeric SKU formats like `KB12`, `CP1598`, `SKU-004`
  (1–4 letters followed by 1–5 digits). Unusual SKU patterns may not be detected.
- **Pricing** — Catalogues usually omit dynamic wholesale/retail pricing. The generated
  `import.sql` includes an empty `price` column ready for manual or bulk updates.

---

## License

MIT License.
