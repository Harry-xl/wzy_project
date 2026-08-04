# docx_reader.py
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

def extract_raw_text(docx_path: str) -> str:
    """按文档顺序提取所有段落和表格文字，包含段落和表格交叉的情况"""
    doc = Document(docx_path)
    lines = []

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]

        if tag == "p":
            para = Paragraph(block, doc)
            text = para.text.strip()
            if text:
                lines.append(text)

        elif tag == "tbl":
            table = Table(block, doc)
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        text = para.text.strip()
                        if text:
                            lines.append(text)

    return "\n".join(lines)
