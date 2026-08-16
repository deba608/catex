# Catalogue Importer

A fast local tool (available as both a **Web App** and a **Native Desktop App**): drop in a product catalogue PDF, get back a clean product list, size list, database import SQL, and all product photos — ready to load into an e-commerce website.

Built for catalogues shaped like Kanha Brothers' — a product code (e.g. `KB1`), a photo, and a size table per item, repeated across pages. It works on any similarly-structured catalogue.

---

## Quick Start

### Prerequisites
- Python 3.9+ installed

### Installation
```bash
git clone https://github.com/deba608/catex.git
cd catex
pip install -r requirements.txt
```

---

## How to Run

### Option A: Local Web App (Recommended for Browser)
1. Run the web server:
   ```bash
   python app.py
   ```
   *(or run `./run.sh` on Linux/macOS)*
2. Open **[http://localhost:5000](http://localhost:5000)** in your browser.
3. Drag & drop your catalogue PDF onto the upload zone (or click to browse).
4. Watch real-time extraction progress and download your files when complete.

### Option B: Native Desktop App (CustomTkinter GUI)
If you prefer a standalone desktop window without a web browser:
```bash
python desktop_app.py
```

---

## What You Get

| File | Format | Description |
|---|---|---|
| **Product list** | `products.csv` | Every product code found, photo availability, and variant count (ready for Excel/Google Sheets). |
| **Sizes list** | `variants.csv` | Every size option per product, converted to centimetres (W × H). |
| **Full data file** | `products.json` | Structured JSON with nested variants and metadata for developers. |
| **Website database file** | `import.sql` | Production-ready PostgreSQL / Supabase SQL script with idempotent `ON CONFLICT` upserts. |
| **All photos** | `photos.zip` | Extracted product photos automatically named by SKU (e.g. `KB1.jpg`). |
| **Summary** | `summary.json` | Statistical overview including total products, photos extracted, and missing photo counts. |

---

## Smart Features & Error Handling

- **Missing Photo Detection**: Flags products that have size specifications in the catalogue but lack a photo (e.g., placeholder or "Coming Soon" listings), providing an exact list of SKUs that need photography.
- **Flexible Dimension Parsing**: Recognizes `cm` (e.g., `10cm x 15cm`), inches (e.g., `10 x 15 in`, `8"`), and bare dimension pairs automatically converting all sizes to centimetres.
- **Robust Upload & Processing Pipeline**: Prevents browser navigation hijacks on drag-and-drop, handles transient polling retries gracefully, and avoids UI lockups or unexpected page resets.

---

## Limitations

- **Image Extraction**: Only extracts photos embedded in the PDF itself. Scanned non-OCR PDFs or missing catalogue photos cannot be auto-generated.
- **SKU Formats**: Matches alphanumeric SKU formats like `KB12`, `CP1598`, `SKU-004`.
- **Pricing**: Catalogues usually omit dynamic wholesale/retail pricing; the generated `import.sql` includes an empty `price` column ready for manual or bulk updates.

---

## License

MIT License.
