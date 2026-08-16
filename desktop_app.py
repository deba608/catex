"""
Catalogue Importer - native desktop app (CustomTkinter).

A true native GUI (no browser, no Flask). Reuses the same extraction engine
(catalogue_extractor.process_catalogue) the web app used. Run with:

    python desktop_app.py

Or run the packaged executable in dist/.
"""

import os
import sys
import queue
import datetime
import threading

import customtkinter as ctk
from tkinter import filedialog

from catalogue_extractor import process_catalogue


# ---------------------------------------------------------------------------
# Paths (work both from source and from a PyInstaller bundle)
# ---------------------------------------------------------------------------
def get_base_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    app_data = os.environ.get("APPDATA")
    if app_data:
        return os.path.join(app_data, "CatalogueImporter", "native")
    return os.path.join(os.path.expanduser("~"), ".catalogue_importer", "native")


# ---------------------------------------------------------------------------
# Theme (matches the web UI palette)
# ---------------------------------------------------------------------------
COLORS = {
    "ink": "#1f2421",
    "ink_soft": "#5c6460",
    "paper": "#f8faf9",
    "card": "#ffffff",
    "line": "#e2e8e5",
    "accent": "#b5502e",
    "accent_hover": "#9c3f20",
    "accent_soft": "#fbf0eb",
    "good": "#2a6f47",
    "good_bg": "#ebf5ee",
    "good_border": "#c3e2cc",
    "warn": "#965b16",
    "warn_bg": "#fdf5ea",
    "warn_border": "#f6dcba",
    "btn": "#1f2421",
    "btn_hover": "#333a36",
    "surface": "#f0f5f5",
}

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def _open_in_explorer(path):
    if not os.path.exists(path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
        return True
    except Exception:
        return False


# ---------- UI helpers ----------

class StatCard(ctk.CTkFrame):
    """Numbered card used in the results screen."""

    def __init__(self, master, number, label, tone="ink", **kw):
        kw.setdefault("fg_color", COLORS["paper"])
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", COLORS["line"])
        kw.setdefault("corner_radius", 10)
        super().__init__(master, **kw)
        self.grid_columnconfigure(0, weight=1)

        color = {"ink": COLORS["ink"], "good": COLORS["good"], "warn": COLORS["warn"]}.get(tone, COLORS["ink"])
        num = ctk.CTkLabel(self, text=str(number), font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
        num.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        lbl = ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=11), text_color=COLORS["ink_soft"], anchor="w")
        lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))


class InfoBanner(ctk.CTkFrame):
    """Thin highlighted banner (green or amber) used in results."""

    def __init__(self, master, title, subtitle, tone="good", **kw):
        kw.setdefault("fg_color", COLORS[f"{tone}_bg"])
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", COLORS[f"{tone}_border"])
        kw.setdefault("corner_radius", 10)
        super().__init__(master, **kw)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(inner, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS[tone], anchor="w").pack(fill="x")
        ctk.CTkLabel(inner, text=subtitle, font=ctk.CTkFont(size=10), text_color="#4a755b", anchor="w", justify="left").pack(fill="x", pady=(2, 0))


# ---------- Main application ----------

class CatalogueApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Catalogue Importer")
        self.geometry("860x820")
        self.minsize(700, 580)
        self.configure(fg_color=COLORS["paper"])

        icon = os.path.join(get_base_dir(), "icon.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except Exception:
                pass

        self.q = queue.Queue()
        self.out_dir = None
        self._worker_thread = None

        # build all frames once
        self._build_header()
        self._build_drop_zone()
        self._build_progress()
        self._build_results()
        self._build_error()

        self._show_state("drop")
        self.after(100, self._poll_queue)

    # ---------- layout ----------

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(30, 2))

        underline = ctk.CTkFrame(self, height=3, fg_color=COLORS["accent"], corner_radius=0)
        underline.pack(fill="x", padx=32, pady=(0, 6))

        eyebrow = ctk.CTkLabel(header, text="CATALOGUE IMPORTER", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["accent"])
        eyebrow.pack(anchor="w")

        title = ctk.CTkLabel(header, text="PDF to Product Database", font=ctk.CTkFont(size=28, weight="bold"), text_color=COLORS["ink"])
        title.pack(anchor="w", pady=(2, 4))

        subtitle = ctk.CTkLabel(header, text="Drop in your catalogue PDF to extract product codes, dimensions, and high-resolution images for website import.",
                                font=ctk.CTkFont(size=13), text_color=COLORS["ink_soft"], anchor="w", justify="left")
        subtitle.pack(anchor="w")

    def _build_drop_zone(self):
        self.drop_frame = ctk.CTkFrame(self, fg_color=COLORS["card"], border_width=2, border_color=COLORS["line"], corner_radius=16)
        self.drop_inner = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        self.drop_inner.pack(padx=28, pady=60)
        self.drop_inner.grid_columnconfigure(0, weight=1)

        icon = ctk.CTkLabel(self.drop_inner, text="📄", font=ctk.CTkFont(size=48))
        icon.grid(row=0, column=0, pady=(0, 20))

        primary = ctk.CTkLabel(self.drop_inner, text="Choose a catalogue PDF to start", font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["ink"])
        primary.grid(row=1, column=0)

        secondary = ctk.CTkLabel(self.drop_inner, text="We'll extract every product, size variant, and photo for you.",
                                   font=ctk.CTkFont(size=13), text_color=COLORS["ink_soft"])
        secondary.grid(row=2, column=0, pady=(10, 24))

        browse = ctk.CTkButton(self.drop_inner, text="Browse for a PDF…", height=44,
                               font=ctk.CTkFont(size=14, weight="bold"),
                               fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                               command=self._choose_pdf)
        browse.grid(row=4, column=0, pady=(20, 0), sticky="ew")

    def _build_progress(self):
        self.progress_frame = ctk.CTkFrame(self, fg_color=COLORS["card"], border_width=1, border_color=COLORS["line"], corner_radius=16)
        body = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        body.pack(fill="x", padx=24, pady=24)

        self.p_file = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=14), text_color=COLORS["ink_soft"], anchor="w")
        self.p_file.pack(fill="x", pady=(0, 10))

        self.p_bar = ctk.CTkProgressBar(body, height=10, corner_radius=8, fg_color=COLORS["line"], progress_color=COLORS["accent"])
        self.p_bar.set(0)
        self.p_bar.pack(fill="x")

        self.p_msg = ctk.CTkLabel(body, text="Starting…", font=ctk.CTkFont(size=13), text_color=COLORS["ink_soft"], anchor="w")
        self.p_msg.pack(fill="x", pady=(6, 0))

    def _build_results(self):
        # scrollable frame that fills the window
        self.results_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["card"], border_width=1,
                                                    border_color=COLORS["line"], corner_radius=16)
        self.results_frame.pack(fill="both", expand=True, padx=30, pady=28)
        self.results_frame.grid_columnconfigure(0, weight=1)

    def _build_error(self):
        self.error_frame = ctk.CTkFrame(self, fg_color="#fff8f5", border_width=1, border_color=COLORS["warn_border"], corner_radius=16)
        body = ctk.CTkFrame(self.error_frame, fg_color="transparent")
        body.pack(fill="x", padx=24, pady=24)

        self.e_title = ctk.CTkLabel(body, text="Extraction encountered an issue", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["warn"], anchor="w")
        self.e_title.pack(fill="x", pady=(0, 6))

        self.e_msg = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=13), text_color=COLORS["ink_soft"], anchor="w", justify="left", wraplength=800)
        self.e_msg.pack(fill="x", pady=(0, 14))

        retry = ctk.CTkButton(body, text="Try again", height=34, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                              font=ctk.CTkFont(size=12, weight="bold"), command=lambda: self._show_state("drop"))
        retry.pack(anchor="w")

    # ---------- state ----------

    def _show_state(self, state):
        for frame in (self.drop_frame, self.progress_frame, self.results_frame, self.error_frame):
            frame.pack_forget()

        mapping = {
            "drop": self.drop_frame,
            "progress": self.progress_frame,
            "results": self.results_frame,
            "error": self.error_frame,
        }
        if state == "results":
            mapping[state].pack(fill="both", expand=True, padx=30, pady=28)
        else:
            mapping[state].pack(fill="x", padx=30, pady=28)

    # ---------- actions ----------

    def _choose_pdf(self):
        path = filedialog.askopenfilename(title="Choose a catalogue PDF", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            self._show_state("error")
            self.e_msg.configure(text="Please choose a PDF file.")
            return
        self._start(path)

    def _start(self, pdf):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.out_dir = os.path.join(get_data_dir(), f"run-{stamp}")
        os.makedirs(self.out_dir, exist_ok=True)

        self.p_file.configure(text=f"Processing: {os.path.basename(pdf)}")
        self.p_bar.set(0)
        self.p_msg.configure(text="Starting…")
        self._show_state("progress")

        self._worker_thread = threading.Thread(target=self._worker, args=(pdf,), daemon=True)
        self._worker_thread.start()

    def _worker(self, pdf):
        def cb(cur, total, message):
            self.q.put(("progress", cur, total, message))
        try:
            result = process_catalogue(pdf, self.out_dir, progress_cb=cb)
            self.q.put(("done", result))
        except Exception as e:
            self.q.put(("error", str(e)))

    def _poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, cur, tot, text = msg
                    self.p_bar.set(cur / tot if tot else 0)
                    self.p_msg.configure(text=text)
                elif kind == "done":
                    self._on_done(msg[1])
                    break
                elif kind == "error":
                    self._show_state("error")
                    self.e_msg.configure(text=msg[1])
                    break
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # ---------- results UI ----------

    def _on_done(self, result):
        # clear old
        for child in self.results_frame.winfo_children():
            child.destroy()

        s = result["summary"]

        # back row at the top
        back_row = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        back_row.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(back_row, text="← Back", width=90, height=32, fg_color=COLORS["btn"],
                      hover_color=COLORS["btn_hover"], font=ctk.CTkFont(size=12, weight="bold"),
                      command=lambda: self._show_state("drop")).pack(side="left")

        # header cards row – use pack for CTkScrollableFrame compatibility
        cards_row = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 8))
        StatCard(cards_row, s["total_products"], "Products found", "ink").pack(side="left", padx=(0, 6))
        StatCard(cards_row, s["total_variants"], "Size variants", "ink").pack(side="left", padx=(6, 6))
        StatCard(cards_row, s["products_with_photo"], "Photos extracted", "good").pack(side="left", padx=(6, 0))
        warn_tone = "warn" if s["products_missing_photo"] else "ink"
        StatCard(cards_row, s["products_missing_photo"], "Missing photo", warn_tone).pack(side="left", padx=(6, 0))

        # missing-photo flag
        if s["products_missing_photo"] > 0:
            flag = ctk.CTkFrame(self.results_frame, fg_color=COLORS["warn_bg"], border_width=1,
                                border_color=COLORS["warn_border"], corner_radius=10)
            flag.pack(fill="x", pady=(0, 12))
            fi = ctk.CTkFrame(flag, fg_color="transparent")
            fi.pack(fill="x", padx=12, pady=8)
            skus = s["missing_photo_skus"]
            shown = ", ".join(skus[:20]) + (", …" if len(skus) > 20 else "")
            ctk.CTkLabel(flag, text=f"{s['products_missing_photo']} products need a photo:", font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=COLORS["warn"], anchor="w").pack(fill="x", pady=(0, 2))
            ctk.CTkLabel(flag, text=shown, font=ctk.CTkFont(size=10), text_color=COLORS["warn"], anchor="w", justify="left", wraplength=800).pack(fill="x")

        # generated files list
        files = [
            ("products.csv", "products.csv", "Product table with status & photo indicators"),
            ("variants.csv", "variants.csv", "Size variants in centimetres"),
            ("products.json", "products.json", "Structured JSON with nested variants"),
            ("import.sql", "import.sql", "PostgreSQL / Supabase ready SQL seed script"),
            ("photos.zip", "photos.zip", "All extracted product photos named by SKU"),
        ]

        ctk.CTkLabel(self.results_frame, text="GENERATED FILES", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLORS["ink_soft"], anchor="w").pack(fill="x", pady=(10, 4))

        for idx, (name, label, desc) in enumerate(files):
            card = ctk.CTkFrame(self.results_frame, fg_color=COLORS["surface"], border_width=1,
                                border_color=COLORS["line"], corner_radius=7)
            card.pack(fill="x", pady=2)
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=10, pady=4)
            ctk.CTkLabel(info, text=label, font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["ink"], anchor="w").pack(fill="x")
            ctk.CTkLabel(info, text=desc, font=ctk.CTkFont(size=9), text_color=COLORS["ink_soft"], anchor="w").pack(fill="x")
            save_path = os.path.join(self.out_dir, name)
            ctk.CTkButton(card, text="Save As…", width=90, height=28, fg_color=COLORS["btn"],
                          hover_color=COLORS["btn_hover"], font=ctk.CTkFont(size=11, weight="bold"),
                          command=lambda p=save_path: self._save_as(p)).pack(side="right", padx=10)

        # action buttons at the bottom
        ctk.CTkButton(self.results_frame, text="Open output folder", height=34, fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"], font=ctk.CTkFont(size=12, weight="bold"),
                      command=lambda: _open_in_explorer(self.out_dir)).pack(fill="x", pady=(10, 0))
        ctk.CTkButton(self.results_frame, text="Import another catalogue", height=34, width=180,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                      font=ctk.CTkFont(size=12, weight="bold"), command=self._show_state("drop")).pack(fill="x", pady=(6, 0))

    # ---------- helpers ----------

    def _save_as(self, path):
        if not os.path.exists(path):
            return
        default = os.path.basename(path)
        dest = filedialog.asksaveasfilename(title="Save file as", initialdir=os.path.expanduser("~"),
                                            initialfile=default,
                                            defaultextension=os.path.splitext(default)[1] or "")
        if not dest:
            return
        try:
            import shutil
            shutil.copyfile(path, dest)
            try:
                _open_in_explorer(dest)
            except Exception:
                pass
        except Exception as e:
            self.e_msg.configure(text=str(e))
            self._show_state("error")


# ---------- entry point ----------

def main():
    app = CatalogueApp()
    app.mainloop()


if __name__ == "__main__":
    main()