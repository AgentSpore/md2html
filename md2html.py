#!/usr/bin/env python3
"""MD2HTML - Zero-dependency Markdown to HTML converter.

Usage:
    python md2html.py input.md > output.html
    cat input.md | python md2html.py > output.html
"""

import sys
import re
import html as html_mod


def parse(markdown_text):
    """Convert markdown text to HTML."""
    lines = markdown_text.split('\n')
    html_lines = []
    in_code_block = False
    code_content = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code blocks (```)
        if line.strip().startswith('```'):
            if in_code_block:
                html_lines.append(f'<pre><code>{html_mod.escape(chr(10).join(code_content))}\n</code></pre>')
                code_content = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_content.append(line)
            i += 1
            continue

        # Headers
        if line.startswith('###### '):
            html_lines.append(f'<h6>{line[7:]}</h6>')
        elif line.startswith('##### '):
            html_lines.append(f'<h5>{line[6:]}</h5>')
        elif line.startswith('#### '):
            html_lines.append(f'<h4>{line[5:]}</h4>')
        elif line.startswith('### '):
            html_lines.append(f'<h3>{line[4:]}</h3>')
        elif line.startswith('## '):
            html_lines.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('# '):
            html_lines.append(f'<h1>{line[2:]}</h1>')
        # Horizontal rule
        elif re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', line.strip()):
            html_lines.append('<hr>')
        # Empty line
        elif line.strip() == '':
            html_lines.append('')
        # Unordered list
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            html_lines.append(f'<li>{line.strip()[2:]}</li>')
        # Blockquote
        elif line.strip().startswith('> '):
            html_lines.append(f'<blockquote>{line.strip()[2:]}</blockquote>')
        # Paragraph (default)
        else:
            # Inline formatting
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
            line = re.sub(r'`(.+?)`', r'<code>\1</code>', line)
            # Links
            line = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', line)
            # Images
            line = re.sub(r'!\[(.*?)\]\((.+?)\)', r'<img src="\2" alt="\1">', line)
            html_lines.append(f'<p>{line}</p>')

        i += 1

    # Close unclosed code block
    if in_code_block:
        html_lines.append(f'<pre><code>{html_mod.escape(chr(10).join(code_content))}\n</code></pre>')

    return '\n'.join(html_lines)


STYLE_CSS = '''body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }
pre { background: #f4f4f4; padding: 16px; border-radius: 4px; overflow-x: auto; }
code { background: #f4f4f4; padding: 2px 4px; border-radius: 2px; }
blockquote { border-left: 4px solid #ddd; margin: 0; padding-left: 16px; color: #666; }
img { max-width: 100%; }
h1, h2, h3 { margin-top: 24px; }'''


def generate_html(body_html, title="MD2HTML Output"):
    """Wrap body HTML in a complete HTML document."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(title)}</title>
<style>
{STYLE_CSS}
</style>
</head>
<body>
{body_html}
</body>
</html>'''


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            md_text = f.read()
    else:
        md_text = sys.stdin.read()

    body = parse(md_text)
    html_output = generate_html(body)
    sys.stdout.write(html_output)


if __name__ == '__main__':
    main()
