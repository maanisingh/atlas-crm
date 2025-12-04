#!/usr/bin/env python3
"""
Atlas CRM & Fulfillment System - Comprehensive Roadmap PDF Generator
Generates a detailed gap analysis and implementation roadmap
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime
import os

# Output path
OUTPUT_PATH = '/root/new-python-code/staticfiles/atlas_crm_roadmap.pdf'

def create_styles():
    """Create custom paragraph styles"""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1a365d')
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#2c5282'),
        borderWidth=1,
        borderColor=colors.HexColor('#2c5282'),
        borderPadding=5
    ))

    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Heading3'],
        fontSize=13,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#2d3748')
    ))

    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=6,
        spaceAfter=6,
        alignment=TA_JUSTIFY
    ))

    styles.add(ParagraphStyle(
        name='StatusComplete',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#22543d'),
        backColor=colors.HexColor('#c6f6d5')
    ))

    styles.add(ParagraphStyle(
        name='StatusPartial',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#744210'),
        backColor=colors.HexColor('#fefcbf')
    ))

    styles.add(ParagraphStyle(
        name='StatusPending',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#742a2a'),
        backColor=colors.HexColor('#fed7d7')
    ))

    return styles

def create_header_footer(canvas, doc):
    """Add header and footer to each page"""
    canvas.saveState()

    # Header
    canvas.setFillColor(colors.HexColor('#1a365d'))
    canvas.setFont('Helvetica-Bold', 10)
    canvas.drawString(50, A4[1] - 30, "Atlas CRM & Fulfillment System")
    canvas.drawRightString(A4[0] - 50, A4[1] - 30, "Implementation Roadmap")
    canvas.setStrokeColor(colors.HexColor('#2c5282'))
    canvas.line(50, A4[1] - 35, A4[0] - 50, A4[1] - 35)

    # Footer
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.gray)
    canvas.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    canvas.drawCentredString(A4[0]/2, 30, f"Page {doc.page}")
    canvas.drawRightString(A4[0] - 50, 30, "Confidential")

    canvas.restoreState()

def create_status_table(items, styles):
    """Create a status table for requirements"""
    data = [['Requirement', 'Current Status', 'Priority', 'Effort']]

    for item in items:
        status_color = {
            'Complete': colors.HexColor('#c6f6d5'),
            'Partial': colors.HexColor('#fefcbf'),
            'Pending': colors.HexColor('#fed7d7')
        }.get(item['status'], colors.white)

        data.append([
            Paragraph(item['requirement'], styles['CustomBody']),
            item['status'],
            item['priority'],
            item['effort']
        ])

    table = Table(data, colWidths=[3.5*inch, 1.2*inch, 0.8*inch, 0.8*inch])

    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]

    # Add row colors based on status
    for i, item in enumerate(items, 1):
        status_color = {
            'Complete': colors.HexColor('#c6f6d5'),
            'Partial': colors.HexColor('#fefcbf'),
            'Pending': colors.HexColor('#fed7d7')
        }.get(item['status'], colors.white)
        style_commands.append(('BACKGROUND', (1, i), (1, i), status_color))

    table.setStyle(TableStyle(style_commands))
    return table

def generate_roadmap():
    """Generate the complete roadmap PDF"""

    # Ensure staticfiles directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=60,
        bottomMargin=50
    )

    styles = create_styles()
    story = []

    # ==================== TITLE PAGE ====================
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("ATLAS CRM & FULFILLMENT SYSTEM", styles['CustomTitle']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Complete Implementation Roadmap", styles['SectionHeader']))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['CustomBody']))
    story.append(Paragraph("Version: 1.0", styles['CustomBody']))
    story.append(Spacer(1, 1*inch))

    # Executive Summary Box
    summary_text = """
    This document provides a comprehensive gap analysis and implementation roadmap for the
    Atlas CRM & Fulfillment System. It compares the current system state against client
    requirements across 6 major phases, identifying completed features, partial implementations,
    and pending work items.
    """
    story.append(Paragraph("<b>Executive Summary</b>", styles['SubHeader']))
    story.append(Paragraph(summary_text, styles['CustomBody']))

    story.append(PageBreak())

    # ==================== TABLE OF CONTENTS ====================
    story.append(Paragraph("TABLE OF CONTENTS", styles['SectionHeader']))
    story.append(Spacer(1, 0.2*inch))

    toc_items = [
        "1. Executive Summary & Current State Overview",
        "2. Phase 1: Foundational & System-Wide Requirements",
        "3. Phase 2: Authentication & User Management",
        "4. Phase 3: Sourcing & Inventory (WMS)",
        "5. Phase 4: Order & Fulfillment (CRM & Pick/Pack)",
        "6. Phase 5: Delivery & Finance (DMS & Accounting)",
        "7. Phase 6: Security & Data Integrity",
        "8. Implementation Timeline & Priority Matrix",
        "9. Resource Requirements",
        "10. Risk Assessment & Mitigation"
    ]

    for item in toc_items:
        story.append(Paragraph(item, styles['CustomBody']))

    story.append(PageBreak())

    # ==================== EXECUTIVE SUMMARY ====================
    story.append(Paragraph("1. EXECUTIVE SUMMARY & CURRENT STATE", styles['SectionHeader']))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("<b>System Overview</b>", styles['SubHeader']))
    overview_text = """
    The Atlas CRM & Fulfillment System is a comprehensive e-commerce fulfillment platform
    built on Django 5.2 with PostgreSQL. The current deployment is live at
    <b>https://atlas-crm.alexandratechlab.com</b> with SSL/TLS encryption via Let's Encrypt.
    """
    story.append(Paragraph(overview_text, styles['CustomBody']))

    # Current State Summary Table
    story.append(Paragraph("<b>Current Implementation Status by Module</b>", styles['SubHeader']))

    module_status = [
        ['Module', 'Status', 'Completion %', 'Notes'],
        ['User Management', 'Partial', '70%', 'Core RBAC done, UI needs work'],
        ['Role-Based Access Control', 'Complete', '90%', 'Full RBAC with audit logs'],
        ['Order Management', 'Partial', '75%', 'Workflow complete, UI partial'],
        ['Call Center Module', 'Partial', '60%', 'Views exist, needs dashboard'],
        ['Packaging System', 'Partial', '65%', 'Models complete, QC partial'],
        ['Delivery Management', 'Complete', '85%', 'Full DMS with GPS tracking'],
        ['Finance Module', 'Partial', '55%', 'Payments done, reports pending'],
        ['Inventory/WMS', 'Partial', '60%', 'Stock tracking done, alerts pending'],
        ['Sourcing Module', 'Partial', '50%', 'Supplier management done'],
        ['Reporting & Analytics', 'Pending', '20%', 'Basic exports only'],
    ]

    module_table = Table(module_status, colWidths=[1.8*inch, 0.9*inch, 1*inch, 2.5*inch])
    module_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (2, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    story.append(module_table)

    story.append(PageBreak())

    # ==================== PHASE 1 ====================
    story.append(Paragraph("2. PHASE 1: FOUNDATIONAL & SYSTEM-WIDE REQUIREMENTS", styles['SectionHeader']))

    # 1.1 UI/UX
    story.append(Paragraph("1.1 UI/UX Standards", styles['SubHeader']))
    phase1_uiux = [
        {'requirement': 'Responsive design (desktop + mobile)', 'status': 'Partial', 'priority': 'High', 'effort': '3 days'},
        {'requirement': 'Consistent navigation sidebar', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Dashboard with KPIs and charts', 'status': 'Partial', 'priority': 'High', 'effort': '5 days'},
        {'requirement': 'Color-coded status badges', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Toast notifications', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Loading indicators', 'status': 'Partial', 'priority': 'Med', 'effort': '1 day'},
        {'requirement': 'Data tables with sort/filter/search', 'status': 'Partial', 'priority': 'High', 'effort': '3 days'},
        {'requirement': 'Inline editing capability', 'status': 'Pending', 'priority': 'Med', 'effort': '4 days'},
        {'requirement': 'Bulk action support', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Print-friendly views', 'status': 'Pending', 'priority': 'Low', 'effort': '2 days'},
    ]
    story.append(create_status_table(phase1_uiux, styles))

    # 1.2 Backend Architecture
    story.append(Paragraph("1.2 Backend Architecture", styles['SubHeader']))
    phase1_backend = [
        {'requirement': 'Django 5.2+ with PostgreSQL', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'RESTful API endpoints', 'status': 'Partial', 'priority': 'High', 'effort': '5 days'},
        {'requirement': 'Celery task queue integration', 'status': 'Pending', 'priority': 'High', 'effort': '3 days'},
        {'requirement': 'Redis caching layer', 'status': 'Pending', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Soft delete implementation', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Full audit trail logging', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Environment-based configuration', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Database migrations management', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
    ]
    story.append(create_status_table(phase1_backend, styles))

    # 1.3 Roles & Permissions
    story.append(Paragraph("1.3 Role-Based Access Control", styles['SubHeader']))
    phase1_roles = [
        {'requirement': 'Admin role - full system access', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Seller role - product/order management', 'status': 'Partial', 'priority': 'High', 'effort': '2 days'},
        {'requirement': 'CallCenter role - order verification', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Warehouse role - stock operations', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Packaging role - pack operations', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Finance role - payments/invoices', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Delivery role - courier management', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'StockKeeper role - inventory ops', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Sourcing role - supplier management', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Dynamic permission assignment', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Role hierarchy inheritance', 'status': 'Pending', 'priority': 'Med', 'effort': '3 days'},
    ]
    story.append(create_status_table(phase1_roles, styles))

    story.append(PageBreak())

    # ==================== PHASE 2 ====================
    story.append(Paragraph("3. PHASE 2: AUTHENTICATION & USER MANAGEMENT", styles['SectionHeader']))

    story.append(Paragraph("2.1 Authentication System", styles['SubHeader']))
    phase2_auth = [
        {'requirement': 'Email-based login (no username)', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Secure password with Django validators', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Remember me functionality', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Forgot password via email', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Session timeout (configurable)', 'status': 'Partial', 'priority': 'Med', 'effort': '1 day'},
        {'requirement': 'Two-Factor Authentication (2FA)', 'status': 'Partial', 'priority': 'High', 'effort': '3 days'},
        {'requirement': 'Login attempt rate limiting', 'status': 'Pending', 'priority': 'High', 'effort': '2 days'},
        {'requirement': 'Account lockout after failed attempts', 'status': 'Pending', 'priority': 'High', 'effort': '1 day'},
    ]
    story.append(create_status_table(phase2_auth, styles))

    story.append(Paragraph("2.2 User Registration & Approval", styles['SubHeader']))
    phase2_reg = [
        {'requirement': 'Self-registration with email verification', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Admin approval workflow', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Registration rejection with reason', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Email notifications for status changes', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'User profile management', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Profile photo upload', 'status': 'Complete', 'priority': 'Low', 'effort': 'Done'},
        {'requirement': 'Activity log per user', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
    ]
    story.append(create_status_table(phase2_reg, styles))

    story.append(Paragraph("2.3 Admin User Management", styles['SubHeader']))
    phase2_admin = [
        {'requirement': 'User CRUD operations', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Role assignment interface', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Permission override per user', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'User status toggle (active/inactive)', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'User search and filtering', 'status': 'Partial', 'priority': 'Med', 'effort': '1 day'},
        {'requirement': 'Bulk user operations', 'status': 'Pending', 'priority': 'Low', 'effort': '2 days'},
        {'requirement': 'User export functionality', 'status': 'Pending', 'priority': 'Low', 'effort': '1 day'},
    ]
    story.append(create_status_table(phase2_admin, styles))

    story.append(PageBreak())

    # ==================== PHASE 3 ====================
    story.append(Paragraph("4. PHASE 3: SOURCING & INVENTORY (WMS)", styles['SectionHeader']))

    story.append(Paragraph("3.1 Supplier Management", styles['SubHeader']))
    phase3_supplier = [
        {'requirement': 'Supplier CRUD with contact info', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Supplier quality scoring', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Supplier delivery performance tracking', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Supplier price scoring', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Supplier document uploads', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Supplier status management', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Supplier product catalog linking', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
    ]
    story.append(create_status_table(phase3_supplier, styles))

    story.append(Paragraph("3.2 Sourcing Requests", styles['SubHeader']))
    phase3_sourcing = [
        {'requirement': 'Sourcing request creation workflow', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Request approval process', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Request document attachments', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Multi-status workflow (draft/submitted/approved)', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Request timeline tracking', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Email notifications for status changes', 'status': 'Pending', 'priority': 'Med', 'effort': '2 days'},
    ]
    story.append(create_status_table(phase3_sourcing, styles))

    story.append(Paragraph("3.3 Warehouse & Inventory", styles['SubHeader']))
    phase3_inventory = [
        {'requirement': 'Multi-warehouse support', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Warehouse location/zone management', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Stock level tracking per product/location', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Min/Max stock level alerts', 'status': 'Partial', 'priority': 'High', 'effort': '2 days'},
        {'requirement': 'Inventory movement tracking', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Stock adjustment workflow', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Barcode/QR code scanning', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Cycle counting support', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Stock reservation for orders', 'status': 'Partial', 'priority': 'High', 'effort': '3 days'},
        {'requirement': 'Inventory valuation reports', 'status': 'Pending', 'priority': 'Med', 'effort': '3 days'},
    ]
    story.append(create_status_table(phase3_inventory, styles))

    story.append(PageBreak())

    # ==================== PHASE 4 ====================
    story.append(Paragraph("5. PHASE 4: ORDER & FULFILLMENT (CRM & PICK/PACK)", styles['SectionHeader']))

    story.append(Paragraph("4.1 Seller Portal", styles['SubHeader']))
    phase4_seller = [
        {'requirement': 'Product CRUD with images', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Auto-generated SKU codes', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Product approval workflow', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Order submission interface', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Order status tracking', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Seller dashboard with stats', 'status': 'Partial', 'priority': 'Med', 'effort': '3 days'},
        {'requirement': 'Product deletion request workflow', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Sales channel management', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Bulk product import (CSV)', 'status': 'Pending', 'priority': 'Med', 'effort': '4 days'},
    ]
    story.append(create_status_table(phase4_seller, styles))

    story.append(Paragraph("4.2 Call Center Module", styles['SubHeader']))
    phase4_callcenter = [
        {'requirement': 'Order queue with filters', 'status': 'Partial', 'priority': 'High', 'effort': '2 days'},
        {'requirement': 'Customer contact information display', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Order confirmation workflow', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Order cancellation with reason', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Order modification capability', 'status': 'Partial', 'priority': 'Med', 'effort': '3 days'},
        {'requirement': 'Call notes/comments on orders', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Callback scheduling', 'status': 'Pending', 'priority': 'Med', 'effort': '3 days'},
        {'requirement': 'Call center dashboard/stats', 'status': 'Pending', 'priority': 'Med', 'effort': '4 days'},
        {'requirement': 'Agent performance metrics', 'status': 'Pending', 'priority': 'Low', 'effort': '3 days'},
    ]
    story.append(create_status_table(phase4_callcenter, styles))

    story.append(Paragraph("4.3 Packaging & Pick/Pack", styles['SubHeader']))
    phase4_packaging = [
        {'requirement': 'Packaging task assignment', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Packaging record creation', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Barcode generation for packages', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Packaging materials tracking', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Quality check workflow', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Package weight/dimensions capture', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Multi-item order packaging', 'status': 'Partial', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Packing slip generation', 'status': 'Pending', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Package photo capture', 'status': 'Pending', 'priority': 'Low', 'effort': '2 days'},
    ]
    story.append(create_status_table(phase4_packaging, styles))

    story.append(PageBreak())

    # ==================== PHASE 5 ====================
    story.append(Paragraph("6. PHASE 5: DELIVERY & FINANCE (DMS & ACCOUNTING)", styles['SectionHeader']))

    story.append(Paragraph("5.1 Delivery Management System", styles['SubHeader']))
    phase5_delivery = [
        {'requirement': 'Delivery company management', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Courier CRUD with credentials', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Delivery record creation', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Delivery status tracking', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Delivery status history log', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Delivery attempt tracking', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'GPS location tracking for couriers', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Delivery proof (photo/signature/OTP)', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Delivery route optimization', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Courier session management', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Delivery performance metrics', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'Manager confirmation workflow', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Courier mobile app API', 'status': 'Pending', 'priority': 'High', 'effort': '10 days'},
    ]
    story.append(create_status_table(phase5_delivery, styles))

    story.append(Paragraph("5.2 Finance & Payments", styles['SubHeader']))
    phase5_finance = [
        {'requirement': 'Payment recording', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Multiple payment methods', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Truvo payment integration', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Invoice generation', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Order fee breakdown', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Platform sync logging', 'status': 'Complete', 'priority': 'Med', 'effort': 'Done'},
        {'requirement': 'COD collection tracking', 'status': 'Partial', 'priority': 'High', 'effort': '2 days'},
        {'requirement': 'Payment reconciliation', 'status': 'Pending', 'priority': 'High', 'effort': '5 days'},
        {'requirement': 'Financial reports', 'status': 'Pending', 'priority': 'High', 'effort': '5 days'},
        {'requirement': 'Seller payout management', 'status': 'Pending', 'priority': 'High', 'effort': '5 days'},
        {'requirement': 'Refund processing', 'status': 'Pending', 'priority': 'Med', 'effort': '3 days'},
        {'requirement': 'Commission calculation', 'status': 'Partial', 'priority': 'Med', 'effort': '3 days'},
    ]
    story.append(create_status_table(phase5_finance, styles))

    story.append(PageBreak())

    # ==================== PHASE 6 ====================
    story.append(Paragraph("7. PHASE 6: SECURITY & DATA INTEGRITY", styles['SectionHeader']))

    story.append(Paragraph("6.1 Security Measures", styles['SubHeader']))
    phase6_security = [
        {'requirement': 'HTTPS/SSL enforcement', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'CSRF protection', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'XSS prevention', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'SQL injection prevention', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Password hashing (bcrypt/argon2)', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Session security', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Rate limiting', 'status': 'Pending', 'priority': 'High', 'effort': '2 days'},
        {'requirement': 'IP-based access control', 'status': 'Pending', 'priority': 'Med', 'effort': '2 days'},
        {'requirement': 'Security audit logging', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'File upload validation', 'status': 'Partial', 'priority': 'High', 'effort': '1 day'},
        {'requirement': 'API authentication (JWT/Token)', 'status': 'Partial', 'priority': 'High', 'effort': '3 days'},
    ]
    story.append(create_status_table(phase6_security, styles))

    story.append(Paragraph("6.2 Data Integrity & Backup", styles['SubHeader']))
    phase6_data = [
        {'requirement': 'Database referential integrity', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Data validation on models', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Audit trail for critical actions', 'status': 'Complete', 'priority': 'High', 'effort': 'Done'},
        {'requirement': 'Automated database backups', 'status': 'Pending', 'priority': 'High', 'effort': '2 days'},
        {'requirement': 'Backup restoration testing', 'status': 'Pending', 'priority': 'High', 'effort': '1 day'},
        {'requirement': 'Data export functionality', 'status': 'Partial', 'priority': 'Med', 'effort': '3 days'},
        {'requirement': 'GDPR compliance features', 'status': 'Pending', 'priority': 'Med', 'effort': '5 days'},
        {'requirement': 'Data retention policies', 'status': 'Pending', 'priority': 'Med', 'effort': '2 days'},
    ]
    story.append(create_status_table(phase6_data, styles))

    story.append(PageBreak())

    # ==================== IMPLEMENTATION TIMELINE ====================
    story.append(Paragraph("8. IMPLEMENTATION TIMELINE & PRIORITY MATRIX", styles['SectionHeader']))

    story.append(Paragraph("<b>Priority Classification</b>", styles['SubHeader']))
    priority_text = """
    <b>Critical (Week 1-2):</b> Security fixes, core workflow completion<br/>
    <b>High (Week 2-4):</b> Dashboard improvements, reporting, API completion<br/>
    <b>Medium (Week 4-6):</b> UI enhancements, bulk operations, notifications<br/>
    <b>Low (Week 6-8):</b> Nice-to-have features, optimizations
    """
    story.append(Paragraph(priority_text, styles['CustomBody']))

    # Timeline table
    story.append(Paragraph("<b>Recommended Implementation Schedule</b>", styles['SubHeader']))
    timeline_data = [
        ['Week', 'Focus Area', 'Key Deliverables', 'Effort'],
        ['1-2', 'Security & Critical Fixes', 'Rate limiting, 2FA completion, login protection', '8-10 days'],
        ['2-3', 'Dashboard & Analytics', 'KPI dashboards, charts, real-time updates', '8 days'],
        ['3-4', 'API & Integration', 'REST API completion, Celery tasks, Redis caching', '10 days'],
        ['4-5', 'Finance Module', 'Reconciliation, reports, seller payouts', '10 days'],
        ['5-6', 'UI/UX Improvements', 'Responsive design, data tables, bulk actions', '8 days'],
        ['6-7', 'Notifications & Automation', 'Email system, alerts, automated workflows', '6 days'],
        ['7-8', 'Testing & Documentation', 'Integration tests, user guides, API docs', '6 days'],
    ]

    timeline_table = Table(timeline_data, colWidths=[0.6*inch, 1.5*inch, 3*inch, 1*inch])
    timeline_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    story.append(timeline_table)

    story.append(PageBreak())

    # ==================== RESOURCE REQUIREMENTS ====================
    story.append(Paragraph("9. RESOURCE REQUIREMENTS", styles['SectionHeader']))

    story.append(Paragraph("<b>Development Team</b>", styles['SubHeader']))
    resources_text = """
    <b>Recommended Team Composition:</b><br/>
    - 1 Senior Django Developer (Full-time, 8 weeks)<br/>
    - 1 Frontend Developer (Part-time, 4 weeks)<br/>
    - 1 QA/Testing Engineer (Part-time, 3 weeks)<br/>
    - 1 DevOps Engineer (Part-time, 1 week)<br/><br/>

    <b>Infrastructure Requirements:</b><br/>
    - Redis server for caching and Celery<br/>
    - Celery worker processes<br/>
    - Enhanced monitoring (Sentry/NewRelic)<br/>
    - Automated backup system<br/><br/>

    <b>Estimated Total Effort:</b> 55-65 developer days
    """
    story.append(Paragraph(resources_text, styles['CustomBody']))

    # ==================== RISK ASSESSMENT ====================
    story.append(Paragraph("10. RISK ASSESSMENT & MITIGATION", styles['SectionHeader']))

    risk_data = [
        ['Risk', 'Impact', 'Probability', 'Mitigation'],
        ['Security vulnerabilities', 'High', 'Medium', 'Priority security audit and fixes'],
        ['Data loss', 'High', 'Low', 'Implement automated backups immediately'],
        ['Performance issues', 'Medium', 'Medium', 'Add caching, optimize queries'],
        ['Scope creep', 'Medium', 'High', 'Strict change management process'],
        ['Integration failures', 'Medium', 'Low', 'Comprehensive API testing'],
    ]

    risk_table = Table(risk_data, colWidths=[1.8*inch, 0.8*inch, 1*inch, 2.5*inch])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#742a2a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fff5f5')]),
    ]))
    story.append(risk_table)

    story.append(Spacer(1, 0.5*inch))

    # Final summary
    story.append(Paragraph("<b>Conclusion</b>", styles['SubHeader']))
    conclusion_text = """
    The Atlas CRM & Fulfillment System has a solid foundation with approximately 65% of core
    functionality already implemented. The remaining work focuses primarily on security hardening,
    dashboard/reporting improvements, and completing the finance module. With a dedicated team
    following this roadmap, full completion is achievable within 8 weeks.
    """
    story.append(Paragraph(conclusion_text, styles['CustomBody']))

    # Build PDF
    doc.build(story, onFirstPage=create_header_footer, onLaterPages=create_header_footer)
    print(f"PDF generated successfully: {OUTPUT_PATH}")
    return OUTPUT_PATH

if __name__ == "__main__":
    generate_roadmap()
