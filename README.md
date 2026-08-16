# Catalogue Importer

A small local web app: drag in a product catalogue PDF, get back a clean
product list, size list, database import file, and all product photos —
ready to load into a website.

Built for catalogues shaped like Kanha Brothers' — a product code (e.g. `KB1`),
a photo, and a size table per item, repeated across pages. It should work on
any similarly-structured catalogue, not just this one.

## How to run it

You need Python 3 installed. Then:

1. Open a terminal in this folder
2. Run:
   ```
   ./run.sh
   ```
   (On Windows, run `pip install -r requirements.txt` then `python app.py` instead)
3. Open **http://localhost:5000** in your browser
4. Drag your catalogue PDF onto the page
5. Wait for it to finish (usually a few seconds per 10 pages)
6. Download the files you need

Leave the terminal window open while using the app — closing it stops the app.

## What you get

| File | What it's for |
|---|---|
| **Product list** (`products.csv`) | Every product code found, whether it has a photo, how many sizes it has. Open in Excel. |
| **Sizes list** (`variants.csv`) | Every size option per product, converted to centimetres. |
| **Full data file** (`products.json`) | Same information, structured for a developer to load into the website. |
| **Website database file** (`import.sql`) | Ready to paste into the website's database (Supabase SQL editor) to load everything in one go. |
| **All photos** (`photos.zip`) | Every product photo the tool found in the PDF, automatically named by product code (e.g. `KB1.jpg`). |

## What it flags for you

After processing, the app shows how many products are **missing a photo** —
these are products where a size/price table exists in the catalogue but no
photo was included. Those need a real photo taken before the product can go
live on the website. The product codes are listed right on the results page.

## Limits — what this tool can't do

- **It only extracts what's already in the PDF.** If a product has no photo
  in the catalogue (shown as "Coming Soon" pages), there's nothing to extract —
  someone needs to take that photo.
- **No pricing.** Catalogues like this typically don't include prices, so
  none is generated. Add pricing separately (the database file has an empty
  `price` column ready for it).
- **Best with one catalogue category at a time.** If you have separate PDFs
  for trophies, stationery, printing, etc., run each through separately —
  don't combine them into one PDF first.
- **Reads product codes matching a pattern like `KB12`, `CP1598`, `SKU-004`**
  (letters followed by numbers). If your catalogue labels products very
  differently, it may not detect them — ask your developer to check.

## Running this on another computer

Copy this whole folder (including `app.py`, `catalogue_extractor.py`, the
`templates` folder, `requirements.txt`, and `run.sh`) to the other machine,
then follow "How to run it" above. No internet connection is needed once
Python and the two dependencies (Flask, PyMuPDF) are installed.
