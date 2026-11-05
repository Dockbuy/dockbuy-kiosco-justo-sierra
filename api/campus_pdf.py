"""Constancias ficticias; adjuntos en memoria, nunca descargas del kiosco."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def make_constancia(document):
    stream=BytesIO()
    styles=getSampleStyleSheet()
    content=[Paragraph('JUSTO SIERRA · KIOSCO DEMO',styles['Title']),Spacer(1,20),
             Paragraph(escape(document['title']),styles['Heading1']),
             Paragraph('DOCUMENTO DE DEMOSTRACIÓN · SIN VALIDEZ ACADÉMICA, OFICIAL O FISCAL',styles['Heading2']),Spacer(1,20)]
    student=document['student']
    for line in [document['folio'],'Alumno ficticio: '+student['nombre'],'Matrícula demo: '+student['matricula'],
                 'Nivel: '+student['nivel'],'Ciclo de prueba: '+student['ciclo']]:
        content.extend([Paragraph(escape(line),styles['Normal']),Spacer(1,10)])
    if document.get('kind')=='calificaciones':
        table=Table([['Asignatura ficticia','Calificación demo'],['Matemáticas','9.0'],['Comunicación','9.5'],['Ciencias','8.5']],colWidths=[300,160])
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf1f7')),('GRID',(0,0),(-1,-1),.5,colors.lightgrey),('PADDING',(0,0),(-1,-1),10)]))
        content.append(table)
    else:
        content.append(Paragraph('Ejemplo de constancia para validar el flujo de solicitud, autorización y entrega por correo. No acredita inscripción ni estudios reales.',styles['Normal']))
    content.extend([Spacer(1,30),Paragraph('No contiene firmas, sellos ni certificaciones oficiales. Los datos y resultados son ficticios.',styles['Normal'])])
    SimpleDocTemplate(stream,title='Constancia DEMO',author='Kiosco demo').build(content)
    return stream.getvalue()
