"""
catalogue_extractor.py

Generalized extractor for product catalogues shaped like the Kanha Brothers
"Memorial Culture" PDF: repeating pages with N product photos, each labeled
with a SKU code and a "Size A/B/C -> Total Size WxH" table.

Works on any catalogue as long as:
  - Product codes appear as text near their image, matching a pattern like
    "KB12", "CP1598", "SKU-004" etc. (letters followed by digits, optionally
    hyphenated)
  - Each product has one large photo on the page
  - Size/dimension rows follow the code as plain text

Output: products.csv, variants.csv, products.json, import.sql, photos/*.jpg
"""

try:
    import pymupdf as fitz
except ImportError:
    import fitz
import re
import os
import csv
import json
import zipfile
from collections import defaultdict

SKU_PATTERN = re.compile(r'\b([A-Z]{1,4}-?\d{1,5})\b')


def to_cm_pair(token):
    """Parse a raw dimension token into (width_cm, height_cm)."""
    token = (token or "").strip()
    # Strip optional prefix like 'Size A:', 'Size 1 -', 'A.', 'B:'
    token = re.sub(r'^(?:size\s+[a-z\d]+|[a-z])[\s:->=.]+\s*', '', token, flags=re.I).strip()

    # 10cm x 15cm, 10 cm x 15 cm, 10x15cm, 10 x 15 cm
    m = re.search(r'([\d.]+)\s*(?:cm)?\s*[xX*×]\s*([\d.]+)\s*cm', token, re.I)
    if m:
        return float(m.group(1)), float(m.group(2))

    # 10 in x 15 in, 10 x 15 in, 10" x 15"
    m = re.search(r'([\d.]+)\s*(?:in|\"|\'\')?\s*[xX*×]\s*([\d.]+)\s*(?:in|\"|\'\')', token, re.I)
    if m:
        return round(float(m.group(1)) * 2.54, 2), round(float(m.group(2)) * 2.54, 2)

    # 10 x 15 (bare dimension pair)
    m = re.search(r'([\d.]+)\s*[xX*×]\s*([\d.]+)', token, re.I)
    if m:
        return round(float(m.group(1)) * 2.54, 2), round(float(m.group(2)) * 2.54, 2)

    # 10 cm (single dimension in cm)
    m = re.search(r'([\d.]+)\s*cm', token, re.I)
    if m:
        return None, float(m.group(1))

    # 10 in or 10" (single dimension in in)
    m = re.search(r'([\d.]+)\s*(?:in|\"|\'\')', token, re.I)
    if m:
        return None, round(float(m.group(1)) * 2.54, 2)

    # bare number
    m = re.match(r'^([\d.]+)$', token)
    if m:
        return None, round(float(m.group(1)) * 2.54, 2)

    return None, None


def extract_page_blocks(page):
    """
    Return list of (sku, [dimension_tokens]) for a page, in the order SKUs
    appear in the text stream, plus the sorted product image xrefs by
    reading-order position (top-to-bottom, left-to-right).
    """
    text = page.get_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    blocks = []  # (sku, [dims])
    current_sku = None
    current_dims = []

    for line in lines:
        sku_match = SKU_PATTERN.fullmatch(line)
        if sku_match:
            if current_sku:
                blocks.append((current_sku, current_dims))
            current_sku = sku_match.group(1)
            current_dims = []
        else:
            # collect anything that looks like a dimension token
            if current_sku and re.search(r'\d', line) and ('cm' in line.lower() or 'in' in line.lower() or '"' in line or re.search(r'\d+\s*[xX*×]\s*\d+', line) or re.fullmatch(r'[\d.]+', line)):
                if line.lower() not in ('size', 'total size', 'a', 'b', 'c', 'd', 'e'):
                    current_dims.append(line)
    if current_sku:
        blocks.append((current_sku, current_dims))

    return blocks


def extract_images_in_order(page):
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:
        return []
    product_imgs = [im for im in infos if im.get("width", 0) >= 100 and im.get("height", 0) >= 100 and im.get("bbox")]
    product_imgs.sort(key=lambda im: (round(im["bbox"][1] / 50), im["bbox"][0]))
    return product_imgs


def process_catalogue(pdf_path, output_dir, sku_prefix_hint=None, progress_cb=None):
    """
    Main entry point. Processes the PDF and writes all output files into
    output_dir (products.csv, variants.csv, products.json, import.sql,
    photos/, photos.zip).

    progress_cb(current_page, total_pages, message) is called periodically
    if provided, for UI progress reporting.
    """
    os.makedirs(output_dir, exist_ok=True)
    photos_dir = os.path.join(output_dir, "photos")
    os.makedirs(photos_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    products = {}   # sku -> dict
    variants = defaultdict(list)  # sku -> list of variant dicts
    photo_report = []

    seen_order = []

    for page_num in range(total_pages):
        if progress_cb:
            progress_cb(page_num + 1, total_pages, f"Reading page {page_num + 1} of {total_pages}")

        page = doc[page_num]
        blocks = extract_page_blocks(page)
        if not blocks:
            continue

        images = extract_images_in_order(page)

        for i, (sku, dim_tokens) in enumerate(blocks):
            if sku_prefix_hint and not sku.startswith(sku_prefix_hint):
                pass

            if sku not in products:
                products[sku] = {
                    "sku": sku,
                    "name": f"Product {sku}",
                    "status": "coming_soon",
                    "has_photo": False,
                }
                seen_order.append(sku)

            labels = ["A", "B", "C", "D", "E"]
            for idx, token in enumerate(dim_tokens):
                w, h = to_cm_pair(token)
                if w is None and h is None:
                    continue
                label = labels[idx] if idx < len(labels) else str(idx + 1)
                variants[sku].append({
                    "variant_label": label,
                    "width_cm": w,
                    "height_cm": h,
                    "raw_dimension": token,
                })
            if dim_tokens:
                products[sku]["status"] = "active"

            # extract matching photo by position if available
            extracted_skus = {p[0] for p in photo_report if p[1] == "extracted"}
            if i < len(images) and sku not in extracted_skus:
                xref = images[i].get("xref")
                if xref:
                    try:
                        base = doc.extract_image(xref)
                        data = base["image"]
                        ext = base["ext"]
                        if len(data) >= 3000:
                            fname = os.path.join(photos_dir, f"{sku}.{ext}")
                            with open(fname, "wb") as f:
                                f.write(data)
                            products[sku]["has_photo"] = True
                            photo_report.append((sku, "extracted", fname))
                        else:
                            photo_report.append((sku, "skipped_tiny", len(data)))
                    except Exception as e:
                        photo_report.append((sku, "error", str(e)))

    # ---- write outputs ----
    ordered_skus = seen_order

    products_csv = os.path.join(output_dir, "products.csv")
    with open(products_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku", "name", "status", "has_photo", "variant_count"])
        for sku in ordered_skus:
            p = products[sku]
            w.writerow([p["sku"], p["name"], p["status"], p["has_photo"], len(variants[sku])])

    variants_csv = os.path.join(output_dir, "variants.csv")
    with open(variants_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku", "variant_label", "width_cm", "height_cm", "raw_dimension"])
        for sku in ordered_skus:
            for v in variants[sku]:
                w.writerow([sku, v["variant_label"], v["width_cm"] or "", v["height_cm"] or "", v["raw_dimension"]])

    combined = []
    for sku in ordered_skus:
        p = dict(products[sku])
        p["variants"] = variants[sku]
        combined.append(p)
    products_json = os.path.join(output_dir, "products.json")
    with open(products_json, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    # SQL
    def esc(s):
        if s is None:
            return "null"
        return "'" + str(s).replace("'", "''") + "'"

    sql_lines = []
    sql_lines.append("-- Catalogue import generated by Catalogue Importer")
    sql_lines.append("""create table if not exists products (
  id uuid primary key default gen_random_uuid(),
  sku text unique not null,
  name text not null,
  status text not null default 'active',
  has_photo boolean not null default false,
  created_at timestamptz default now()
);""")
    sql_lines.append("""create table if not exists product_variants (
  id uuid primary key default gen_random_uuid(),
  product_id uuid references products(id) on delete cascade,
  variant_label text not null,
  width_cm numeric,
  height_cm numeric,
  raw_dimension text,
  price numeric,
  created_at timestamptz default now()
);""")
    if ordered_skus:
        sql_lines.append("insert into products (sku, name, status, has_photo) values")
        rows = [f"({esc(products[s]['sku'])}, {esc(products[s]['name'])}, {esc(products[s]['status'])}, {str(products[s]['has_photo']).lower()})" for s in ordered_skus]
        sql_lines.append(",\n".join(rows))
        sql_lines.append("on conflict (sku) do update set name = excluded.name, status = excluded.status, has_photo = excluded.has_photo;")

        vrows = []
        for s in ordered_skus:
            for v in variants[s]:
                w_ = v["width_cm"] if v["width_cm"] is not None else "null"
                h_ = v["height_cm"] if v["height_cm"] is not None else "null"
                vrows.append(f"({esc(s)}, {esc(v['variant_label'])}, {w_}, {h_}, {esc(v['raw_dimension'])})")
        if vrows:
            sql_lines.append("insert into product_variants (product_id, variant_label, width_cm, height_cm, raw_dimension)")
            sql_lines.append("select p.id, v.variant_label, v.width_cm, v.height_cm, v.raw_dimension from (values")
            sql_lines.append(",\n".join(vrows))
            sql_lines.append(") as v(sku, variant_label, width_cm, height_cm, raw_dimension)")
            sql_lines.append("join products p on p.sku = v.sku;")

    import_sql = os.path.join(output_dir, "import.sql")
    with open(import_sql, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))

    # zip photos
    photos_zip = os.path.join(output_dir, "photos.zip")
    with zipfile.ZipFile(photos_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(photos_dir):
            for fname in os.listdir(photos_dir):
                fpath = os.path.join(photos_dir, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, arcname=f"photos/{fname}")

    # summary stats
    total = len(ordered_skus)
    with_photo = sum(1 for s in ordered_skus if products[s]["has_photo"])
    active = sum(1 for s in ordered_skus if products[s]["status"] == "active")
    total_variants = sum(len(variants[s]) for s in ordered_skus)

    summary = {
        "total_products": total,
        "products_with_photo": with_photo,
        "products_missing_photo": total - with_photo,
        "active_products": active,
        "coming_soon_products": total - active,
        "total_variants": total_variants,
        "missing_photo_skus": [s for s in ordered_skus if not products[s]["has_photo"]],
        "coming_soon_skus": [s for s in ordered_skus if products[s]["status"] != "active"],
    }
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if progress_cb:
        progress_cb(total_pages, total_pages, "Done")

    return {
        "products_csv": products_csv,
        "variants_csv": variants_csv,
        "products_json": products_json,
        "import_sql": import_sql,
        "photos_zip": photos_zip,
        "photos_dir": photos_dir,
        "summary": summary,
    }
