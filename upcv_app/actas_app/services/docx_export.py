from io import BytesIO


def build_acta_docx(acta, institucion_nombre="Sistema de Actas Consistoriales"):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    contenido = (acta.contenido_final or "").strip() or (acta.contenido_borrador or "").strip()

    document = Document()

    titulo_sistema = document.add_paragraph(institucion_nombre)
    titulo_sistema.alignment = WD_ALIGN_PARAGRAPH.CENTER
    titulo_sistema.runs[0].font.size = Pt(11)

    titulo = document.add_paragraph(f"ACTA NÚMERO {acta.numero_acta}-{acta.anio}")
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    titulo_run = titulo.runs[0]
    titulo_run.bold = True
    titulo_run.font.size = Pt(14)

    document.add_paragraph("")

    if contenido:
        for bloque in contenido.replace("\r\n", "\n").split("\n"):
            texto = bloque.strip()
            if texto:
                p = document.add_paragraph(texto)
                p.paragraph_format.space_after = Pt(8)
            else:
                document.add_paragraph("")

    lower = contenido.lower()
    if "moderador" not in lower and "secretario" not in lower:
        document.add_paragraph("")
        document.add_paragraph("__________________________")
        document.add_paragraph("Moderador")
        document.add_paragraph("")
        document.add_paragraph("__________________________")
        document.add_paragraph("Secretario")

    stream = BytesIO()
    document.save(stream)
    stream.seek(0)
    return stream
