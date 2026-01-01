# core/services/receipt_generator.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfgen import canvas
from io import BytesIO
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
import qrcode
from core.utils.financial import FinancialCalculator

class ProfessionalReceiptGenerator:
    """Generate professional PDF receipts for payments"""
    
    def __init__(self, school_name, school_address, school_logo_path=None):
        self.school_name = school_name
        self.school_address = school_address
        self.school_logo_path = school_logo_path
        self.calculator = FinancialCalculator()
    
    def generate_payment_receipt(self, payment_data, student_data):
        """
        Generate a professional receipt PDF
        payment_data: dict with payment details
        student_data: dict with student details
        """
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center aligned
        )
        
        # Add school header
        if self.school_logo_path:
            try:
                logo = Image(self.school_logo_path, width=1.5*inch, height=1.5*inch)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 0.1*inch))
            except:
                pass
        
        story.append(Paragraph(self.school_name, title_style))
        story.append(Paragraph(self.school_address, styles['Normal']))
        story.append(Paragraph("OFFICIAL PAYMENT RECEIPT", styles['Heading2']))
        story.append(Spacer(1, 0.3*inch))
        
        # Receipt details table
        receipt_details = [
            ['Receipt Number:', payment_data.get('receipt_number', 'N/A')],
            ['Receipt Date:', timezone.now().strftime('%d/%m/%Y %I:%M %p')],
            ['Student ID:', student_data.get('student_id', 'N/A')],
            ['Student Name:', student_data.get('full_name', 'N/A')],
            ['Class:', student_data.get('class_level', 'N/A')],
        ]
        
        receipt_table = Table(receipt_details, colWidths=[2*inch, 4*inch])
        receipt_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(receipt_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Payment details table
        payment_items = [
            ['Description', 'Amount (GH₵)']
        ]
        
        # Add fee items
        for item in payment_data.get('items', []):
            payment_items.append([
                item.get('description', ''),
                f"{item.get('amount', 0):,.2f}"
            ])
        
        # Add totals
        subtotal = self.calculator.safe_decimal(payment_data.get('subtotal', 0))
        payment_items.append(['Subtotal:', f"{subtotal:,.2f}"])
        
        if payment_data.get('discount', 0) > 0:
            discount = self.calculator.safe_decimal(payment_data.get('discount', 0))
            payment_items.append(['Discount:', f"-{discount:,.2f}"])
        
        if payment_data.get('tax', 0) > 0:
            tax = self.calculator.safe_decimal(payment_data.get('tax', 0))
            payment_items.append(['Tax:', f"{tax:,.2f}"])
        
        total = self.calculator.safe_decimal(payment_data.get('total', 0))
        payment_items.append(['<b>TOTAL PAID</b>', f"<b>GH₵{total:,.2f}</b>"])
        
        payment_table = Table(payment_items, colWidths=[4*inch, 2*inch])
        payment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(payment_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Payment method and reference
        payment_info = [
            ['Payment Method:', payment_data.get('payment_method', 'N/A')],
            ['Reference:', payment_data.get('reference', 'N/A')],
            ['Received By:', payment_data.get('received_by', 'N/A')],
        ]
        
        if payment_data.get('bank_reference'):
            payment_info.append(['Bank Reference:', payment_data.get('bank_reference')])
        
        info_table = Table(payment_info, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Generate QR code with receipt data
        qr_data = f"""
        Receipt: {payment_data.get('receipt_number')}
        Date: {timezone.now().strftime('%Y-%m-%d')}
        Student: {student_data.get('full_name')}
        Amount: GH₵{total:,.2f}
        School: {self.school_name}
        """
        
        qr = qrcode.QRCode(version=1, box_size=4, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code to buffer
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        # Add QR code to PDF
        qr_image = Image(qr_buffer, width=1.5*inch, height=1.5*inch)
        qr_image.hAlign = 'CENTER'
        story.append(qr_image)
        
        # Footer note
        footer = Paragraph(
            "This is an official receipt. Please retain for your records.<br/>"
            "For any queries, contact the school accounts office.",
            styles['Italic']
        )
        story.append(Spacer(1, 0.2*inch))
        story.append(footer)
        
        # Build PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer
    
    def generate_receipt_response(self, payment_data, student_data, filename=None):
        """Generate HTTP response with PDF receipt"""
        if not filename:
            filename = f"receipt_{payment_data.get('receipt_number', 'unknown')}.pdf"
        
        pdf_buffer = self.generate_payment_receipt(payment_data, student_data)
        
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_buffer.getvalue())
        
        return response