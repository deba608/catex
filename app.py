import os
import sys
import uuid
import threading
import shutil
import subprocess
import traceback
from flask import Flask, request, jsonify, send_from_directory, render_template

from catalogue_extractor import process_catalogue

# Base directory for bundled assets (templates, static)
if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data directory for uploads & outputs
def get_data_dir():
    app_data = os.environ.get("APPDATA")
    if app_data:
        base = os.path.join(app_data, "CatalogueImporter")
    else:
        base = os.path.join(os.path.expanduser("~"), ".catalogue_importer")
    return base

DATA_DIR = os.environ.get("CATALOGUE_DATA_DIR") or get_data_dir()
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
OUTPUT_DIR = os.path.join(DATA_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(BUNDLE_DIR, "templates"),
    static_folder=os.path.join(BUNDLE_DIR, "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB

# in-memory job tracking (fine for a single-user local tool)
jobs = {}


def configure_paths(data_dir):
    global DATA_DIR, UPLOAD_DIR, OUTPUT_DIR
    DATA_DIR = data_dir
    UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
    OUTPUT_DIR = os.path.join(DATA_DIR, "outputs")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_job(job_id, pdf_path, job_output_dir):
    def progress_cb(current, total, message):
        if job_id in jobs:
            jobs[job_id]["progress"] = {
                "current": current,
                "total": total,
                "message": message
            }

    try:
        jobs[job_id]["status"] = "processing"
        result = process_catalogue(pdf_path, job_output_dir, progress_cb=progress_cb)
        jobs[job_id]["summary"] = result.get("summary", {})
        jobs[job_id]["progress"] = {"current": 1, "total": 1, "message": "Complete"}
        jobs[job_id]["status"] = "done"
    except Exception as e:
        traceback.print_exc()
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a valid PDF file"}), 400

    job_id = str(uuid.uuid4())[:8]
    pdf_path = os.path.join(UPLOAD_DIR, f"{job_id}.pdf")
    file.save(pdf_path)

    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_output_dir, exist_ok=True)

    jobs[job_id] = {
        "status": "queued",
        "progress": {"current": 0, "total": 1, "message": "Starting…"},
        "summary": None,
    }

    thread = threading.Thread(target=run_job, args=(job_id, pdf_path, job_output_dir), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    return jsonify(job)


@app.route("/api/download/<job_id>/<filename>")
def download(job_id, filename):
    allowed = {"products.csv", "variants.csv", "products.json", "import.sql", "photos.zip", "summary.json"}
    if filename not in allowed:
        return jsonify({"error": "File type not allowed"}), 400
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    file_path = os.path.join(job_output_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": f"File {filename} not found"}), 404
    return send_from_directory(job_output_dir, filename, as_attachment=True)


@app.route("/api/open-folder/<job_id>", methods=["POST"])
def open_folder(job_id):
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    if not os.path.exists(job_output_dir):
        return jsonify({"error": "Output folder not found"}), 404
    try:
        if sys.platform == "win32":
            os.startfile(job_output_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", job_output_dir])
        else:
            subprocess.Popen(["xdg-open", job_output_dir])
        return jsonify({"success": True, "path": job_output_dir})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
