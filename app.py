
from flask import Flask, request, jsonify
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import tempfile
import os
from extractor import extract_fields

app = Flask(__name__)

def extract_text_from_pdf(filepath):
    """Try digital extraction first, fall back to OCR"""
    text = ""
    
    # Try pdfplumber first (digital PDFs)
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except:
        pass

    # If little text extracted, use OCR (scanned PDFs)
    if len(text.strip()) < 100:
        try:
            images = convert_from_path(filepath, dpi=300)
            for image in images:
                text += pytesseract.image_to_string(image) + "\n"
        except Exception as e:
            return None, str(e)

    return text, None

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "PDF Extractor API is running"})

@app.route("/extract", methods=["POST"])
def extract():
    # Check file was sent
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files accepted"}), 400

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Extract text
        text, error = extract_text_from_pdf(tmp_path)
        if error:
            return jsonify({"error": f"Extraction failed: {error}"}), 500

        # Extract fields
        filename = file.filename.replace(".pdf", "")
        result = extract_fields(text, filename)

        # Add confidence score
        fields = ["provider","account_number","bill_date",
                  "due_date","usage_kwh","amount_due"]
        found = sum(1 for f in fields if result.get(f))
        result["confidence"] = f"{round(found/len(fields)*100)}%"
        result["status"] = "success"

        return jsonify(result)

    finally:
        os.unlink(tmp_path)  # Clean up temp file

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
