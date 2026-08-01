import os
import markdown
import glob
import base64
import requests

DOCS_DIR = "docs"
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - SSR Living Documentation</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --text-color: #f1f5f9;
            --border-color: #334155;
            --accent: #3b82f6;
            --sidebar-width: 250px;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            display: flex;
            min-height: 100vh;
        }}
        .sidebar {{
            width: var(--sidebar-width);
            background-color: var(--panel-bg);
            border-right: 1px solid var(--border-color);
            padding: 20px;
            position: fixed;
            height: 100%;
            overflow-y: auto;
        }}
        .sidebar h2 {{
            color: var(--accent);
            font-size: 1.2rem;
            margin-top: 0;
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .sidebar ul {{
            list-style-type: none;
            padding: 0;
            margin: 0;
        }}
        .sidebar li {{
            margin-bottom: 10px;
        }}
        .sidebar a {{
            color: var(--text-color);
            text-decoration: none;
            display: block;
            padding: 8px 12px;
            border-radius: 4px;
            transition: background-color 0.2s;
        }}
        .sidebar a:hover, .sidebar a.active {{
            background-color: rgba(59, 130, 246, 0.1);
            color: var(--accent);
        }}
        .content {{
            margin-left: var(--sidebar-width);
            padding: 40px;
            max-width: 900px;
            width: 100%;
            line-height: 1.6;
        }}
        h1, h2, h3, h4 {{
            color: #ffffff;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}
        h1 {{ font-size: 2.2rem; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; }}
        a {{ color: var(--accent); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        code {{
            background-color: rgba(0,0,0,0.3);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.9em;
        }}
        pre code {{
            display: block;
            padding: 15px;
            overflow-x: auto;
            background-color: #000;
            border: 1px solid var(--border-color);
        }}
        blockquote {{
            border-left: 4px solid var(--accent);
            margin: 0;
            padding-left: 15px;
            color: #cbd5e1;
            background-color: rgba(59, 130, 246, 0.05);
            padding: 10px 15px;
            border-radius: 0 4px 4px 0;
        }}
        ul, ol {{ margin-top: 0.5em; margin-bottom: 1.5em; padding-left: 25px; }}
        li {{ margin-bottom: 0.5em; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background-color: rgba(0,0,0,0.2);
            font-weight: 600;
        }}
        img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin: 20px 0;
            background: white; /* For SVG contrast if needed */
        }}
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>SSR Manual</h2>
        <ul>
            <li><a href="PROJECT_STATE.html" id="link-PROJECT_STATE">Project State</a></li>
            <li><a href="ARCHITECTURE.html" id="link-ARCHITECTURE">Architecture</a></li>
            <li><a href="PIPELINE.html" id="link-PIPELINE">The Pipeline</a></li>
            <li><a href="WORKBOOK.html" id="link-WORKBOOK">Workbook Schema</a></li>
            <li><a href="OPERATIONS.html" id="link-OPERATIONS">Operations</a></li>
            <li><a href="CHANGELOG.html" id="link-CHANGELOG">Changelog</a></li>
            <li style="margin-top: 20px; border-top: 1px solid var(--border-color); padding-top: 20px;">
                <a href="index.html">Live Dashboard</a>
            </li>
        </ul>
    </div>
    <div class="content">
        {content}
    </div>
    <script>
        // Simple script to highlight the active sidebar link
        const currentPage = window.location.pathname.split('/').pop().replace('.html', '');
        const activeLink = document.getElementById('link-' + currentPage);
        if (activeLink) {{
            activeLink.classList.add('active');
        }}
    </script>
</body>
</html>
"""

def generate_architecture_svg():
    print("[DOCS] Generating ARCHITECTURE.svg via Mermaid API...")
    graph = '''graph TD
A[News Sources & RSS] --> B[SQLite Deduplication]
B --> C[Global Exclusions]
C --> D[Ontology Extraction]
D --> E[Rules Engine]
E --> F[AI Target Extraction]
F --> G[AI Event Classification]
G --> H[AI Research & Playbooks]
H --> I[Daily Memory Deduplication]
I --> J[Email Alerts & Archiving]
J --> K[Operations Dashboard]

classDef default fill:#1e293b,stroke:#334155,stroke-width:2px,color:#f1f5f9;
classDef ai fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:#ffffff;
classDef drop fill:#ef4444,stroke:#dc2626,stroke-width:2px,color:#ffffff;

class F,G,H ai;
class C,I drop;
'''
    try:
        # Encode graph for mermaid.ink
        b64_str = base64.urlsafe_b64encode(graph.encode('utf-8')).decode('utf-8')
        url = f'https://mermaid.ink/svg/{b64_str}'
        
        response = requests.get(url)
        if response.status_code == 200:
            svg_path = os.path.join(DOCS_DIR, 'ARCHITECTURE.svg')
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("[DOCS] Successfully generated ARCHITECTURE.svg")
            return True
        else:
            print(f"[ERROR] Failed to fetch SVG. Status: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Exception during SVG generation: {e}")
    return False

def build_docs():
    print("[DOCS] Building Living Documentation...")
    
    # 1. Generate the SVG diagram
    generate_architecture_svg()
    
    # 2. Process all Markdown files
    md_files = glob.glob(os.path.join(DOCS_DIR, "*.md"))
    
    for md_file in md_files:
        basename = os.path.basename(md_file)
        name_no_ext = os.path.splitext(basename)[0]
        html_file = os.path.join(DOCS_DIR, f"{name_no_ext}.html")
        
        with open(md_file, "r", encoding="utf-8") as f:
            md_content = f.read()
            
        # Add the SVG image into the Architecture page dynamically if it exists
        if name_no_ext == "ARCHITECTURE":
            md_content += "\\n## Pipeline Diagram\\n\\n![Architecture Diagram](ARCHITECTURE.svg)\\n"
            
        html_content = markdown.markdown(
            md_content, 
            extensions=['fenced_code', 'tables']
        )
        
        # Inject into template
        final_html = TEMPLATE.format(
            title=name_no_ext.replace("_", " ").title(),
            content=html_content
        )
        
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(final_html)
            
        print(f"[DOCS] Built {html_file}")

if __name__ == "__main__":
    build_docs()
    print("[DOCS] Documentation build complete.")
