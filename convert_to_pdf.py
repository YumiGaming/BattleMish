import os
import subprocess
import markdown

MD_PATH = r"c:\Users\benja\Desktop\Codes\Taller Redes\INFORME_TALLER_REDES.md"
HTML_TEMP_PATH = r"c:\Users\benja\Desktop\Codes\Taller Redes\INFORME_TALLER_REDES.html"
PDF_PATH = r"c:\Users\benja\Desktop\Codes\Taller Redes\INFORME_TALLER_REDES.pdf"

# Leer markdown
with open(MD_PATH, "r", encoding="utf-8") as f:
    md_content = f.read()

# Convertir Markdown a HTML con extensiones de tablas, código cercado y metadatos
html_body = markdown.markdown(
    md_content,
    extensions=["tables", "fenced_code", "codehilite", "toc", "attr_list", "def_list"]
)

# Plantilla HTML con estilo académico formal para impresión en PDF
html_document = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe Técnico - BattleMish Sockets TCP</title>
    <style>
        @page {{
            size: letter portrait;
            margin: 20mm 18mm 22mm 18mm;
            @bottom-right {{
                content: "Página " counter(page);
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                color: #64748b;
            }}
            @bottom-left {{
                content: "Taller de Redes — BattleMish Sockets TCP";
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                color: #64748b;
            }}
        }}

        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
            font-size: 10.5pt;
            line-height: 1.6;
            color: #1e293b;
            background: #ffffff;
            margin: 0;
            padding: 0;
        }}

        h1 {{
            font-size: 20pt;
            font-weight: 800;
            color: #0f172a;
            border-bottom: 3px solid #2563eb;
            padding-bottom: 8px;
            margin-top: 0;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        h2 {{
            font-size: 14pt;
            font-weight: 700;
            color: #1e40af;
            border-bottom: 1.5px solid #cbd5e1;
            padding-bottom: 4px;
            margin-top: 22pt;
            margin-bottom: 10pt;
            page-break-after: avoid;
        }}

        h3 {{
            font-size: 11.5pt;
            font-weight: 600;
            color: #0f172a;
            margin-top: 14pt;
            margin-bottom: 6pt;
            page-break-after: avoid;
        }}

        p {{
            margin-top: 0;
            margin-bottom: 9pt;
            text-align: justify;
        }}

        ul, ol {{
            margin-top: 0;
            margin-bottom: 9pt;
            padding-left: 22px;
        }}

        li {{
            margin-bottom: 4pt;
        }}

        hr {{
            border: 0;
            height: 1px;
            background: #e2e8f0;
            margin: 18pt 0;
        }}

        /* Tablas Académicas */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12pt 0;
            font-size: 9.5pt;
            page-break-inside: avoid;
        }}

        th, td {{
            padding: 7pt 10pt;
            text-align: left;
            vertical-align: top;
            border: 1px solid #cbd5e1;
        }}

        th {{
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
            border-bottom: 2px solid #94a3b8;
        }}

        tr:nth-child(even) td {{
            background-color: #f8fafc;
        }}

        /* Bloques de Código */
        pre {{
            background-color: #0f172a;
            color: #f8fafc;
            padding: 10pt 12pt;
            border-radius: 5px;
            font-family: 'Consolas', 'Courier New', Courier, monospace;
            font-size: 8.8pt;
            line-height: 1.45;
            overflow-x: auto;
            margin: 10pt 0;
            page-break-inside: avoid;
            border: 1px solid #1e293b;
        }}

        code {{
            font-family: 'Consolas', 'Courier New', Courier, monospace;
            font-size: 9pt;
            background-color: #f1f5f9;
            color: #0f172a;
            padding: 1.5pt 4pt;
            border-radius: 3px;
            border: 1px solid #e2e8f0;
        }}

        pre code {{
            background-color: transparent;
            color: inherit;
            padding: 0;
            border: none;
            font-size: 8.8pt;
        }}

        /* Citas y Destacados */
        blockquote {{
            border-left: 4px solid #2563eb;
            background-color: #eff6ff;
            color: #1e3a8a;
            padding: 8pt 12pt;
            margin: 10pt 0;
            border-radius: 0 4px 4px 0;
            font-size: 9.8pt;
        }}

        strong {{
            color: #0f172a;
            font-weight: 700;
        }}

        .page-break {{
            page-break-before: always;
        }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>
"""

with open(HTML_TEMP_PATH, "w", encoding="utf-8") as f:
    f.write(html_document)

print(f"HTML generado en: {HTML_TEMP_PATH}")

# Ejecutar Microsoft Edge o Chrome en modo headless para generar el PDF
edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

browser_exe = edge_path if os.path.exists(edge_path) else chrome_path

cmd = [
    browser_exe,
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-extensions",
    f"--print-to-pdf={PDF_PATH}",
    "--print-to-pdf-no-header",
    f"file:///{HTML_TEMP_PATH.replace(os.sep, '/')}"
]

print("Generando PDF con:", browser_exe)
res = subprocess.run(cmd, capture_output=True, text=True)
print("Salida:", res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)

if os.path.exists(PDF_PATH):
    size_kb = os.path.getsize(PDF_PATH) / 1024
    print(f"PDF generado con éxito: {PDF_PATH} ({size_kb:.1f} KB)")
else:
    print("Error: No se pudo generar el archivo PDF.")
