import os
import uuid
import shutil
import subprocess
import tempfile
from io import BytesIO
from flask import Flask, request, jsonify, send_file
from docx import Document
from pypdf import PdfWriter, PdfReader

app = Flask(__name__)

# Security: Simple API key (change this to your own secret)
API_KEY = "ayra_secret_key_2026"


def check_auth():
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return False
    return True


def fill_docx(docx_path, replacements, output_path):
    """Fill a DOCX template with replacement values preserving all formatting"""
    doc = Document(docx_path)

    # Sort replacements by key length (longest first) to prevent partial matches
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)

    # Fill paragraphs
    for para in doc.paragraphs:
        for key in sorted_keys:
            if key in para.text:
                value = replacements[key] or ""
                for run in para.runs:
                    if key in run.text:
                        run.text = run.text.replace(key, value)

    # Fill tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for key in sorted_keys:
                        if key in para.text:
                            value = replacements[key] or ""
                            for run in para.runs:
                                if key in run.text:
                                    run.text = run.text.replace(key, value)

    doc.save(output_path)


def convert_docx_to_pdf(docx_path, pdf_path):
    """Convert DOCX to PDF using LibreOffice headless"""
    output_dir = os.path.dirname(pdf_path)
    cmd = [
        "libreoffice",
        "--headless",
        "--norestore",
        "--nofirststartwizard",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path
    ]
    subprocess.run(cmd, timeout=60, check=True, capture_output=True)


def merge_pdfs(pdf_bytes_list):
    """Merge multiple PDF byte strings into one"""
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


@app.route("/api/convert", methods=["POST"])
def convert():
    """
    Main endpoint: Receives DOCX files + replacements, returns merged PDF.
    
    POST multipart/form-data:
      - files: multiple DOCX files
      - replacements: JSON string of {KEY: value}
      - witness_name: filename stem to duplicate (default: "WITNESS")
      - exclude_name: filename stem to skip (default: "CD")
    """
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        replacements_raw = request.form.get("replacements", "{}")
        import json
        replacements = json.loads(replacements_raw)

        witness_stem = request.form.get("witness_name", "WITNESS").upper()
        exclude_stem = request.form.get("exclude_name", "CD").upper()

        files = request.files.getlist("files")
        if not files:
            return jsonify({"success": False, "message": "No files uploaded"}), 400

        # Create temp workspace
        work_dir = tempfile.mkdtemp(prefix="ayra_pdf_")

        try:
            pdf_bytes_list = []

            for f in files:
                stem = os.path.splitext(f.filename)[0].upper()

                # Skip excluded documents (like CD)
                if stem == exclude_stem:
                    continue

                # Save uploaded DOCX
                docx_path = os.path.join(work_dir, f.filename)
                f.save(docx_path)

                # Fill template
                filled_path = os.path.join(work_dir, f"filled_{f.filename}")
                fill_docx(docx_path, replacements, filled_path)

                # Convert to PDF
                pdf_filename = f"filled_{os.path.splitext(f.filename)[0]}.pdf"
                pdf_path = os.path.join(work_dir, pdf_filename)
                convert_docx_to_pdf(filled_path, pdf_path)

                # Read PDF bytes
                with open(pdf_path, "rb") as pf:
                    pdf_data = pf.read()

                pdf_bytes_list.append(pdf_data)

                # Duplicate Witness document
                if stem == witness_stem:
                    pdf_bytes_list.append(pdf_data)

            if not pdf_bytes_list:
                return jsonify({"success": False, "message": "No PDFs generated"}), 500

            # Merge all PDFs
            merged = merge_pdfs(pdf_bytes_list)

            return send_file(
                BytesIO(merged),
                mimetype="application/pdf",
                as_attachment=False,
                download_name="print_output.pdf"
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)