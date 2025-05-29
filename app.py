from flask import Flask, request, jsonify, send_file, render_template_string
import tempfile, os
import tabula
import pandas as pd
import numpy as np

app = Flask(_name_)

def parse_produto_servico(pdf_path, arquivo_nome):
    tables = tabula.read_pdf(
        pdf_path,
        pages="1",
        multiple_tables=True,
        stream=True
    )

    target = None
    for tbl in tables:
        if tbl.astype(str).apply(lambda col: col.str.contains("CÓDIGO", na=False)).any().any():
            target = tbl
            break
    if target is None:
        return []

    df = target.copy()

    hdr = df.iloc[0]
    second = df.iloc[1]
    orig_cols = df.columns
    new_cols = [
        (hdr[i] if pd.notna(hdr[i]) else f"{orig_cols[i]}{second[i]}")
        for i in range(len(orig_cols))
    ]
    df.columns = new_cols
    df = df.drop(df.index[0]).reset_index(drop=True)

    df.columns = df.columns.str.replace(r"\.1", "", regex=True)
    df = df.dropna(subset=["DESCRIÇÃO DO PRODUTO/SERVIÇO"])

    df["CÓDIGO"] = df["CÓDIGO"].replace(r"^\s*$", np.nan, regex=True)
    for idx in range(1, len(df)):
        if pd.isna(df.at[idx, "CÓDIGO"]):
            for col in df.columns:
                if col == "CÓDIGO":
                    continue
                prev = str(df.at[idx - 1, col]).strip()
                this = str(df.at[idx, col]).strip()
                if this and this.lower() != "nan":
                    df.at[idx - 1, col] = f"{prev} {this}".strip()
    df = df[df["CÓDIGO"].notna()].reset_index(drop=True)

    num_cols = [
        "QTD.", "VLR. UNIT.", "V.DESC.", "VLR. TOTAL",
        "BC. ICMS", "VLR. ICMS", "VLR. IPI", "ALÍQ.ICMS", "ALÍQ.IPI"
    ]
    for c in num_cols:
        if c in df:
            df[c] = (
                df[c]
                  .astype(str)
                  .str.replace(r"\.", "", regex=True)
                  .str.replace(",", ".", regex=False)
                  .astype(float)
            )

    df["arquivo"] = arquivo_nome

    return df.to_dict(orient="records")

@app.route("/", methods=["GET"])
def home():
    return render_template_string("""
    <!doctype html>
    <html lang="pt-BR">
      <head><meta charset="utf-8"><title>Upload NFe</title></head>
      <body>
        <h1>Envie seus PDFs de NFe</h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
          <input type="file" name="arquivos" multiple>
          <button type="submit">Upload</button>
        </form>
      </body>
    </html>
    """)

@app.route("/upload", methods=["POST"])
def upload():
    arquivos = request.files.getlist("arquivos")
    all_dados = []

    for arquivo in arquivos:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        arquivo.save(tmp.name)
        tmp.close()

        all_dados.extend(parse_produto_servico(tmp.name, arquivo.filename))
        os.remove(tmp.name)

    df = pd.DataFrame(all_dados)

    cols = ['CÓDIGO', 'DESCRIÇÃO DO PRODUTO/SERVIÇO', 'NCM/SH', 'CST', 'CFOP',
       'UNID.', 'QTD.', 'VLR. UNIT.', 'V.DESC.', 'VLR. TOTAL', 'BC. ICMS',
       'VLR. ICMS', 'VLR. IPI', 'ALÍQ.ICMS', 'ALÍQ.IPI', 'arquivo']

    df = df[[c for c in cols if c in df.columns]]

    df = df.rename(columns = {'arquivo': 'ARQUIVO'})

    tmp_xlsx = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df.to_excel(tmp_xlsx.name, index=False)
    app.config["ULTIMO_ARQUIVO"] = tmp_xlsx.name

    table_html = df.to_html(classes="data", index=False, border=0)

    return render_template_string("""
    <!doctype html>
    <html lang="pt-BR">
      <head>
        <meta charset="utf-8">
        <title>Resultados NFe</title>
        <style>
          table.data { border-collapse: collapse; width: 100%; }
          table.data th, table.data td { border: 1px solid #ccc; padding: 4px; text-align: left; }
        </style>
      </head>
      <body>
        <h1>Dados extraídos</h1>
        {{ table|safe }}
        <p><a href="/baixar">⬇ Download resultados.xlsx</a></p>
        <p><a href="/">↩️ Voltar</a></p>
      </body>
    </html>
    """, table=table_html)

@app.route("/baixar")
def baixar_excel():
    arquivo = app.config.get("ULTIMO_ARQUIVO")
    if arquivo and os.path.exists(arquivo):
        return send_file(arquivo, as_attachment=True, download_name="resultado.xlsx")
    return "Nenhum arquivo gerado ainda.", 404

if _name_ == "_main_":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
