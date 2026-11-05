"""PDF adjunto al correo: generado en memoria, nunca descargado por el kiosco."""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape


def make_pdf(document, invoice=False):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.barcode.qr import QrCodeWidget

    output = BytesIO()
    navy, red, muted = colors.HexColor('#153252'), colors.HexColor('#ad102b'), colors.HexColor('#68798c')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('TitleJS', fontName='Helvetica-Bold', fontSize=22, leading=27, textColor=navy, spaceAfter=10))
    styles.add(ParagraphStyle('BodyJS', fontName='Helvetica', fontSize=9, leading=14, textColor=navy))
    styles.add(ParagraphStyle('SmallJS', parent=styles['BodyJS'], fontSize=8, leading=12, textColor=muted))
    styles.add(ParagraphStyle('NoticeJS', parent=styles['BodyJS'], fontName='Helvetica-Bold', textColor=red, alignment=TA_CENTER))
    p = lambda text, style='BodyJS': Paragraph(escape(str(text)), styles[style])
    title = 'Factura de prueba' if invoice else 'Comprobante de pago demo'
    pdf = SimpleDocTemplate(output, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=23*mm, bottomMargin=22*mm,
                            title=title+' - SIN VALIDEZ FISCAL', author='Kiosco Justo Sierra - Demo')
    story = [p('UNIVERSIDAD JUSTO SIERRA', 'SmallJS'), Spacer(1, 5*mm), p(title, 'TitleJS')]
    notice = Table([[p('DEMO / SIN VALIDEZ FISCAL / SIN COBRO REAL', 'NoticeJS')]], colWidths=[170*mm])
    notice.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fff1ef')),('BOX',(0,0),(-1,-1),.5,colors.HexColor('#e6b8bf')),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    story += [notice, Spacer(1, 7*mm), p('Fecha: '+datetime.fromisoformat(document['issued_at']).strftime('%d/%m/%Y %H:%M UTC'))]
    story += [p('Folio: '+document.get('folio', document['qr_payload']))]
    if invoice:
        story += [p('CFDI 4.0 ilustrativo. Sin timbrado, certificado ni sello SAT.', 'SmallJS'), Spacer(1,4*mm),
                  p('Emisor: '+document['emisor']), p('RFC emisor: '+document['rfc_emisor']),
                  p('Receptor: '+document['receptor']), p('RFC receptor: '+document['rfc_receptor'])]
    else:
        story += [p('Matrícula demo: '+document['estudiante']['matricula'])]
    story.append(Spacer(1,7*mm))
    rows = [[p('CONCEPTO'), p('VENCIMIENTO'), p('IMPORTE MXN')]]
    for item in document['conceptos']:
        rows.append([p(item['nombre']), p(item['fechaVencimiento']), p(f"$ {item['restante']:,.2f}")])
    table = Table(rows, colWidths=[106*mm,32*mm,32*mm], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf2f8')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#fafbfd')]),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dce3ec')),
        ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    story += [table, Spacer(1,6*mm)]
    qr = QrCodeWidget(document['qr_payload'], barLevel='M')
    x1,y1,x2,y2 = qr.getBounds()
    size=38*mm
    drawing=Drawing(size,size,transform=[size/(x2-x1),0,0,size/(y2-y1),0,0]); drawing.add(qr)
    total = Paragraph(f"<b>TOTAL DEMO: $ {document['total']:,.2f} MXN</b>",styles['BodyJS'])
    summary=Table([[drawing,[total,Spacer(1,4*mm),p('Conserva este QR. Puedes escanearlo en el mismo kiosco para consultar tu comprobante o factura.', 'SmallJS'),Spacer(1,3*mm),p(document['qr_payload'],'SmallJS')]]],colWidths=[45*mm,125*mm])
    summary.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(KeepTogether([summary,Spacer(1,4*mm),p('Documento ficticio. No acredita pagos reales ni puede utilizarse como comprobante fiscal.','SmallJS')]))
    def page_frame(canvas, doc):
        canvas.setStrokeColor(red); canvas.setLineWidth(2); canvas.line(20*mm, A4[1]-16*mm, A4[0]-20*mm,A4[1]-16*mm)
        canvas.setFillColor(muted);canvas.setFont('Helvetica',8)
        canvas.drawString(20*mm,13*mm,'JUSTO SIERRA / DOCKBUY / DOCUMENTO DE PRUEBA')
        canvas.drawRightString(A4[0]-20*mm,13*mm,f'Página {doc.page}')
    pdf.build(story,onFirstPage=page_frame,onLaterPages=page_frame)
    return output.getvalue()
