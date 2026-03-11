import os
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_use_mkldnn"] = "0"

import uuid
import base64
from flask import Flask, request, jsonify, render_template
from config import (
    UPLOAD_FOLDER, DRUG_NAMES_PATH, INVENTORY_PATH,
    ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH,
    MATCH_SCORE_THRESHOLD, MATCH_LIMIT,
)
from ocr_engine import extract_text, extract_medicine_candidates
from medicine_matcher import load_drug_names, load_inventory, match_medicines

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load data at startup
drug_names = load_drug_names(DRUG_NAMES_PATH)
inventory = load_inventory(INVENTORY_PATH)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan", methods=["POST"])
def scan_prescription():
    """Accept file upload or base64 image, run OCR + matching pipeline."""
    image_path = None

    try:
        if "file" in request.files:
            file = request.files["file"]
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400
            if not allowed_file(file.filename):
                return jsonify({"error": "File type not allowed. Use PNG, JPG, JPEG, WEBP, or BMP."}), 400

            ext = file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(image_path)

        elif request.is_json and "image_base64" in request.json:
            b64_data = request.json["image_base64"]
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            image_bytes = base64.b64decode(b64_data)
            filename = f"{uuid.uuid4().hex}.jpg"
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            with open(image_path, "wb") as f:
                f.write(image_bytes)

        else:
            return jsonify({"error": "No image provided"}), 400

        # Pipeline
        text_lines = extract_text(image_path)
        candidates = extract_medicine_candidates(text_lines)
        results = match_medicines(
            candidates, drug_names, inventory,
            score_threshold=MATCH_SCORE_THRESHOLD,
            limit=MATCH_LIMIT,
        )

        return jsonify({
            "success": True,
            "raw_text_lines": text_lines,
            "medicines": results,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)


@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    """Return the full inventory."""
    return jsonify(inventory)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
