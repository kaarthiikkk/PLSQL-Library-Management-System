#!/usr/bin/env python3
"""
Converts BCSE302P_Project_Report_Final.docx to PDF using Mammoth HTML conversion
and Google Chrome headless print-to-pdf engine for publication-quality output.
"""

import os
import subprocess
import mammoth

def convert_docx_to_pdf(input_docx, output_pdf):
    print(f"[*] Reading {input_docx}...")
    with open(input_docx, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)
        html_body = result.value
        messages = result.messages
        if messages:
            print(f"[*] Mammoth notes: {len(messages)} notices")

    # Add academic print styling
    styled_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>BCSE302P Project Report - Library Management System</title>
    <style>
        @page {{
            size: A4;
            margin: 20mm 18mm 20mm 18mm;
            @bottom-right {{
                content: counter(page);
            }}
        }}

        body {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 11pt;
            line-height: 1.35;
            color: #111827;
            margin: 0 auto;
            max-width: 800px;
        }}

        h1 {{
            font-family: 'Arial', sans-serif;
            font-size: 15pt;
            font-weight: bold;
            color: #0f172a;
            margin-top: 24pt;
            margin-bottom: 8pt;
            border-bottom: 1.5px solid #cbd5e1;
            padding-bottom: 4pt;
            page-break-after: avoid;
        }}

        h2 {{
            font-family: 'Arial', sans-serif;
            font-size: 12.5pt;
            font-weight: bold;
            color: #1e293b;
            margin-top: 16pt;
            margin-bottom: 6pt;
            page-break-after: avoid;
        }}

        h3 {{
            font-family: 'Arial', sans-serif;
            font-size: 11pt;
            font-weight: bold;
            color: #334155;
            margin-top: 12pt;
            margin-bottom: 4pt;
            page-break-after: avoid;
        }}

        p {{
            margin-top: 0;
            margin-bottom: 8pt;
            text-align: justify;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10pt;
            margin-bottom: 14pt;
            font-size: 9.5pt;
            page-break-inside: avoid;
        }}

        th, td {{
            border: 1px solid #cbd5e1;
            padding: 6pt 8pt;
            text-align: left;
            vertical-align: top;
        }}

        th {{
            background-color: #f1f5f9;
            font-weight: bold;
            color: #0f172a;
        }}

        pre, code {{
            font-family: 'Courier New', Courier, monospace;
            font-size: 8.5pt;
            background-color: #f8fafc;
        }}

        pre {{
            border: 1px solid #e2e8f0;
            border-left: 3px solid #4f46e5;
            padding: 8pt 10pt;
            border-radius: 4px;
            white-space: pre-wrap;
            word-break: break-all;
            margin: 8pt 0 12pt 0;
            background-color: #f8fafc;
            color: #1e293b;
            page-break-inside: avoid;
        }}

        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 10pt auto;
            border-radius: 4px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.1);
        }}

        ul, ol {{
            margin-top: 0;
            margin-bottom: 8pt;
            padding-left: 20pt;
        }}

        li {{
            margin-bottom: 3pt;
        }}

        .cover-page {{
            text-align: center;
            page-break-after: always;
            padding-top: 40pt;
        }}

        .certificate-page {{
            page-break-after: always;
            padding-top: 30pt;
        }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>
"""

    temp_html = "report_render.html"
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(styled_html)
    print(f"[+] Rendered intermediate HTML: {temp_html}")

    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome_path):
        print(f"[*] Invoking Google Chrome Headless Print-to-PDF engine...")
        cmd = [
            chrome_path,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_pdf}",
            temp_html
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(output_pdf):
            print(f"[OK] Successfully created PDF: {output_pdf} (Size: {os.path.getsize(output_pdf)} bytes)")
        else:
            print(f"[!] Chrome PDF creation error: {res.stderr.decode('utf-8', errors='ignore')}")
    else:
        print("[!] Google Chrome not found at default location.")

if __name__ == "__main__":
    convert_docx_to_pdf("BCSE302P_Project_Report_Final.docx", "BCSE302P_Project_KarthikReddy.pdf")
    # Also create standard named PDF
    if os.path.exists("BCSE302P_Project_KarthikReddy.pdf"):
        import shutil
        shutil.copyfile("BCSE302P_Project_KarthikReddy.pdf", "BCSE302P_Project_Report.pdf")
        print("[OK] Created BCSE302P_Project_Report.pdf as duplicate copy.")
