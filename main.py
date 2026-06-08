from flask import Flask, request, jsonify
import pdfplumber
import io
import csv
from PIL import Image
import img2pdf

app = Flask(__name__)

ALLOWED_TYPES = (
    "application/pdf",
    "application/octet-stream",  # some clients send PDF with this type
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
)

def load_mapping(filepath):
    rows = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "match": normalize(row["match_text"]),
                "name": row["name"].strip()
            })
    return rows

def normalize(s):
    return s.upper().replace(" ", "").replace("-", "").replace(".", "")

def find_match(norm_text, mapping):
    for row in mapping:
        if row["match"] and row["match"] in norm_text:
            return row["name"]
    return None

SUPPLIERS = load_mapping("suppliers.csv")
CLIENTS   = load_mapping("clients.csv")

def extract_text_from_pdf(pdf_bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def image_to_pdf_bytes(image_bytes):
    # open with Pillow, convert to RGB (strips alpha channel if PNG)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    pdf_bytes = img2pdf.convert(img_byte_arr.getvalue())
    return pdf_bytes

@app.route("/parse-invoice", methods=["POST"])
def parse_invoice():
    if "file" not in request.files:
        return jsonify({"error": "no file sent"}), 400

    f = request.files["file"]
    content_type = f.content_type
    file_bytes = f.read()

    if content_type not in ALLOWED_TYPES:
        return jsonify({"error": f"unsupported type: {content_type}"}), 400

    # convert image to PDF first if needed
    if content_type.startswith("image/"):
        try:
            file_bytes = image_to_pdf_bytes(file_bytes)
        except Exception as e:
            return jsonify({"error": f"image conversion failed: {str(e)}"}), 500

    # now everything is PDF
    try:
        text = extract_text_from_pdf(file_bytes)
    except Exception as e:
        return jsonify({"error": f"text extraction failed: {str(e)}"}), 500

    if not text.strip():
        return jsonify({
            "matched": False,
            "reason": "no text extracted — may be a scanned image inside PDF"
        }), 200

    norm = normalize(text)
    supplier = find_match(norm, SUPPLIERS)
    client   = find_match(norm, CLIENTS)

    if supplier and client:
        return jsonify({
            "matched": True,
            "supplier": supplier,
            "client": client
        }), 200
    else:
        return jsonify({
            "matched": False,
            "supplier": supplier,
            "client": client,
            "reason": f"missing {'supplier' if not supplier else 'client'}"
        }), 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# from flask import Flask, request, jsonify
# import pdfplumber
# import io
# import csv

# app = Flask(__name__)

# # ---- load your mapping from a CSV (same logic as Sheet) ----
# def load_mapping(filepath):
#     rows = []
#     with open(filepath, newline='', encoding='utf-8') as f:
#         reader = csv.DictReader(f)  # expects headers: match_text, name
#         for row in reader:
#             rows.append({
#                 "match": normalize(row["match_text"]),
#                 "name": row["name"].strip()
#             })
#     return rows

# def normalize(s):
#     return s.upper().replace(" ", "").replace("-", "").replace(".", "")

# def find_match(norm_text, mapping):
#     for row in mapping:
#         if row["match"] and row["match"] in norm_text:
#             return row["name"]
#     return None

# # load once at startup, not on every request
# SUPPLIERS = load_mapping("suppliers.csv")
# CLIENTS   = load_mapping("clients.csv")

# # ---- the one endpoint ----
# @app.route("/parse-invoice", methods=["POST"])
# def parse_invoice():
#     if "file" not in request.files:
#         return jsonify({"error": "no file"}), 400

#     pdf_bytes = request.files["file"].read()

#     # extract text with pdfplumber
#     text = ""
#     with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
#         for page in pdf.pages:
#             text += page.extract_text() or ""

#     norm = normalize(text)
#     supplier = find_match(norm, SUPPLIERS)
#     client   = find_match(norm, CLIENTS)

#     if not supplier or not client:
#         return jsonify({
#             "matched": False,
#             "supplier": supplier,
#             "client": client,
#             "reason": f"missing {'supplier' if not supplier else 'client'}"
#         }), 200  # 200 not 400 — n8n can handle the logic, it's not a server error

#     return jsonify({
#         "matched": True,
#         "supplier": supplier,
#         "client": client,
#     }), 200

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000)
