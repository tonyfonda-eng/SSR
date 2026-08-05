import re

with open("src/html_generator.py", "r") as f:
    content = f.read()

# 1. Remove generate_archive_html and generate_ontology_debug_html
content = re.sub(r'def generate_archive_html\(.*?\)(.*?)(?=def generate_)', '', content, flags=re.DOTALL)

with open("src/html_generator.py", "w") as f:
    f.write(content)
