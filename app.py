from flask import Flask, request, send_file, jsonify
import os
import pandas as pd
import tempfile
import camelot
from datetime import datetime

app = Flask(__name__)

@app.route("/upload", methods=["POST"])
def upload_pdf():
    if 'files' not in request.files:
        return jsonify({"error": "No files part in the request"}), 400

    files = request.files.getlist("files")
    all_rows = []

    for file in files:
        if file.filename == '':
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            file.save(tmp.name)
            try:
                # Tenta com lattice
                tables = camelot.read_pdf(tmp.name, pages='all', flavor='lattice', strip_text='\n')
                if tables.n == 0:
                    raise ValueError("Nenhuma tabela encontrada com lattice, tentando stream...")
            except Exception as e:
                print(f"[fallback] {e}")
                try:
                    tables = camelot.read_pdf(tmp.name, pages='all', flavor='stream', strip_text='\n')
                except Exception as fallback_error:
                    print(f"[erro ao tentar stream] {fallback_error}")
                    continue  # pula esse arquivo

            for table in tables:
                df = table.df
                for i, row in df.iterrows():
                    all_rows.append([file.filename] + row.tolist())

            os.unlink(tmp.name)

    if not all_rows:
        return jsonify({"error": "Nenhum dado extraído dos PDFs."}), 400

    output_df = pd.DataFrame(all_rows)
    output_path = os.path.join(tempfile.gettempdir(), f"saida_{datetime.now().timestamp()}.xlsx")
    output_df.to_excel(output_path, index=False)

    return send_file(output_path, as_attachment=True, download_name="notas_extraidas.xlsx")

@app.route("/")
def index():
    return "<h2>API de Upload de PDFs DANFE</h2><p>Use o endpoint /upload via POST com arquivos PDFs.</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
