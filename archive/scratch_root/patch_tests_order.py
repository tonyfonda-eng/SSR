import re

with open('tests/test_ingestion_contract.py', 'r') as f:
    content = f.read()

# Remove the if __name__ block from the middle
content = re.sub(r'if __name__ == \'__main__\':\n    unittest\.main\(verbosity=2\)\n', '', content)

# Append it to the very end
content += """\nif __name__ == '__main__':\n    unittest.main(verbosity=2)\n"""

with open('tests/test_ingestion_contract.py', 'w') as f:
    f.write(content)
