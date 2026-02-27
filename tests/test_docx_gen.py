from skills.document_writer import DocumentWriter
import os

content = '''# Test Document
This is a bold test: **BOLD**. This is italic: *ITALIC*.
## Subheading
- Bullet 1
- Bullet 2
'''
output_path = 'test_output.docx'
if os.path.exists(output_path):
    os.remove(output_path)

print('Generating test DOCX...')
try:
    DocumentWriter.write_docx(output_path, content)
    print(f'Success! Saved to {output_path}')
except Exception as e:
    print(f'Failed: {e}')
