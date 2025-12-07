from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json
import csv
from io import StringIO
from .models import Warehouse, WarehouseLocation, Stock, InventoryRecord, InventoryMovement
from sellers.models import Product
from django import forms
from django.contrib import messages

@login_required
def movements(request):
    """Inventory movements view."""
    # Get all inventory movements
    movements = InventoryMovement.objects.select_related('product', 'warehouse').order_by('-created_at')[:50]
    
    # Get movement statistics
    total_movements = InventoryMovement.objects.count()
    incoming_movements = InventoryMovement.objects.filter(movement_type='in').count()
    outgoing_movements = InventoryMovement.objects.filter(movement_type='out').count()
    
    context = {
        'movements': movements,
        'total_movements': total_movements,
        'incoming_movements': incoming_movements,
        'outgoing_movements': outgoing_movements,
    }
    
    return render(request, 'inventory/movements.html', context)

# Removed duplicate function - using the one below

@login_required
def edit_warehouse(request, warehouse_id):
    """Edit warehouse."""
    warehouse = get_object_or_404(Warehouse, id=warehouse_id)
    
    if request.method == 'POST':
        warehouse.name = request.POST.get('name', warehouse.name)
        warehouse.address = request.POST.get('address', warehouse.address)
        warehouse.code = request.POST.get('code', warehouse.code)
        capacity = request.POST.get('capacity')
        warehouse.capacity = int(capacity) if capacity else None
        warehouse.is_active = request.POST.get('is_active') == 'on'
        warehouse.save()
        
        messages.success(request, f'تم تحديث المخزن "{warehouse.name}" بنجاح')
        return redirect('inventory:warehouses')
    
    return render(request, 'inventory/edit_warehouse.html', {'warehouse': warehouse})

@login_required
def delete_warehouse(request, warehouse_id):
    """Delete warehouse."""
    warehouse = get_object_or_404(Warehouse, id=warehouse_id)
    warehouse_name = warehouse.name
    warehouse.delete()
    
    messages.success(request, f'تم حذف المخزن "{warehouse_name}" بنجاح')
    return redirect('inventory:warehouses')

# Create your views here.

@login_required
def add_product(request):
    """Add new product to inventory."""
    if request.method == 'POST':
        # Handle form submission
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        sku = request.POST.get('sku')
        
        if name and price:
            product = Product.objects.create(
                name=name,
                description=description,
                price=float(price),
                sku=sku
            )
            messages.success(request, f'Product "{product.name}" added successfully!')
            return redirect('inventory:products')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    return render(request, 'inventory/add_product.html')

@login_required
def inventory_dashboard(request):
    """Inventory dashboard with statistics and low stock alerts."""
    # Get total product count, warehouses, and low stock items
    total_products = Product.objects.count()
    available_inventory = InventoryRecord.objects.aggregate(total=Sum('quantity'))['total'] or 0
    
    # Calculate low stock items (products with 10 or fewer items)
    low_stock_items = 0
    low_stock_products = []
    
    for product in Product.objects.all():
        total_stock = InventoryRecord.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0
        if total_stock <= 10:
            low_stock_items += 1
            low_stock_products.append({
                'product': product,
                'total_stock': total_stock,
                'code': product.code or f"PRD-{product.id:04d}",
                'current_stock': total_stock
            })
    
    warehouses = Warehouse.objects.all()
    
    # Get recent inventory movements
    recent_movements = InventoryMovement.objects.select_related('product', 'from_warehouse', 'to_warehouse', 'created_by').order_by('-created_at')[:10]
    
    # Warehouse statistics
    warehouse_stats = []
    chart_data = {"labels": [], "data": []}
    
    for warehouse in warehouses:
        total_products_in_warehouse = InventoryRecord.objects.filter(warehouse=warehouse).count()
        total_quantity = InventoryRecord.objects.filter(warehouse=warehouse).aggregate(total=Sum('quantity'))['total'] or 0
        warehouse_stats.append({
            'warehouse': warehouse,
            'product_count': total_products_in_warehouse,
            'total_quantity': total_quantity
        })
        
        # Add to chart data
        chart_data["labels"].append(warehouse.name)
        chart_data["data"].append(total_quantity)
    
    # Convert chart data to JSON for use in template
    chart_json = json.dumps(chart_data)
    
    # Get products with stock information
    products_with_stock = Product.objects.all().order_by('-stock_quantity')[:10]
    
    # Get pending approval count
    pending_approval_count = Product.objects.filter(is_approved=False).count()
    
    context = {
        'total_products': total_products,
        'available_inventory': available_inventory,
        'low_stock_items': low_stock_items,
        'low_stock_products': low_stock_products,
        'warehouses': warehouses,
        'recent_movements': recent_movements,
        'warehouse_stats': warehouse_stats,
        'chart_json': chart_json,
        'products_with_stock': products_with_stock,
        'pending_approval_count': pending_approval_count
    }
    
    return render(request, 'inventory/dashboard.html', context)

@login_required
def inventory_products(request):
    """Inventory products list with filtering by warehouse and search options."""
    warehouse_id = request.GET.get('warehouse', '')
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    approval_filter = request.GET.get('approval_filter', '')
    
    # Get product queryset based on user role
    if request.user.has_role('Seller'):
        # Sellers see only their own products
        products = Product.objects.filter(seller=request.user, is_approved=True)
    else:
        # Admins and super users see all products (including pending ones)
        products = Product.objects.all()
    
    # Filter by search query
    if search_query:
        products = products.filter(
            Q(name_en__icontains=search_query) |
            Q(name_ar__icontains=search_query) |
            Q(code__icontains=search_query)
        )
    
    # Filter by approval status (only for admins)
    if approval_filter and not request.user.has_role('Seller'):
        if approval_filter == 'approved':
            products = products.filter(is_approved=True)
        elif approval_filter == 'pending':
            products = products.filter(is_approved=False)
    
    # Get all warehouses for the dropdown
    warehouses = Warehouse.objects.all()
    
    # Get inventory records
    inventory_data = []
    print(f"DEBUG: Processing {products.count()} products")
    for product in products:
        records = InventoryRecord.objects.filter(product=product)
        
        # Filter by warehouse if selected
        if warehouse_id:
            records = records.filter(warehouse_id=warehouse_id)
        
        # Calculate total quantity
        total_quantity = records.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Check if product has stock settings
        try:
            stock = Stock.objects.get(product=product)
            min_quantity = stock.min_quantity
            max_quantity = stock.max_quantity
        except Stock.DoesNotExist:
            min_quantity = 0
            max_quantity = 0
        
        # Determine status
        if total_quantity <= 0:
            status = 'out_of_stock'
        elif total_quantity <= 10:  # Consider 10 or fewer units as low stock
            status = 'low_stock'
        else:
            status = 'in_stock'
        
        # Filter by status if requested
        if status_filter and status != status_filter:
            continue
        
        # Get warehouses where this product is stored
        product_warehouses = Warehouse.objects.filter(
            id__in=records.values_list('warehouse_id', flat=True)
        )
        
        # Get warehouse with the highest quantity
        main_warehouse = None
        if records.exists():
            main_warehouse = records.order_by('-quantity').first().warehouse
        
        inventory_data.append({
            'product': product,
            'total_quantity': total_quantity,
            'warehouses': product_warehouses,
            'main_warehouse': main_warehouse,
            'status': status,
            'min_quantity': min_quantity,
            'max_quantity': max_quantity,
            'is_approved': product.is_approved,
            'approval_status': 'Approved' if product.is_approved else 'Pending Approval'
        })
        print(f"DEBUG: Added product {product.name_en} with quantity {total_quantity}")
    
    # Debug: Print final inventory data
    print(f"DEBUG: Final inventory_data length: {len(inventory_data)}")
    
    # Handle export request - RESTRICTED TO SUPER ADMIN ONLY (P0 CRITICAL)
    if request.GET.get('export') == 'csv':
        if not request.user.is_superuser:
            from utils.views import permission_denied_authenticated
            from users.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='unauthorized_export_attempt',
                entity_type='inventory',
                description=f"Unauthorized attempt to export inventory by {request.user.email}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return permission_denied_authenticated(
                request,
                message="Data export is restricted to Super Admin only for security compliance."
            )
        return export_products_csv(inventory_data, request)
    
    # Check if there's a movements parameter to show movements
    if request.GET.get('movements'):
        return redirect('inventory:movements')
    
    context = {
        'inventory_data': inventory_data,
        'warehouses': warehouses,
        'selected_warehouse_id': warehouse_id,
        'search_query': search_query,
        'status_filter': status_filter,
        'approval_filter': approval_filter,
        'is_admin': request.user.has_role('Admin') or request.user.is_superuser,
        'is_seller': request.user.has_role('Seller')
    }
    
    return render(request, 'inventory/products.html', context)

class WarehouseForm(forms.ModelForm):
    """Form for warehouse creation and editing."""
    class Meta:
        model = Warehouse
        fields = ['name', 'location', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-yellow-500 focus:ring-yellow-500 sm:text-sm transition-colors duration-200',
                'placeholder': 'Enter warehouse name'
            }),
            'location': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-yellow-500 focus:ring-yellow-500 sm:text-sm transition-colors duration-200',
                'placeholder': 'Enter warehouse location'
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-yellow-500 focus:ring-yellow-500 sm:text-sm transition-colors duration-200',
                'rows': 4,
                'placeholder': 'Enter warehouse description (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-yellow-600 focus:ring-yellow-500 border-gray-300 rounded transition-colors'
            }),
        }

@login_required
def warehouse_list(request):
    """List of warehouses - simplified version."""
    warehouses = Warehouse.objects.all().order_by('-id')
    
    context = {
        'warehouses': warehouses,
    }
    return render(request, 'inventory/warehouses.html', context)

@login_required
def add_warehouse(request):
    """Add a new warehouse."""
    # Check if user has permission to add warehouses
    if not (request.user.has_role('Admin') or request.user.is_superuser):
        messages.error(request, 'You do not have permission to add warehouses.')
        return redirect('inventory:warehouses')
    
    if request.method == 'POST':
        form = WarehouseForm(request.POST)
        if form.is_valid():
            warehouse = form.save()
            messages.success(request, f'Warehouse "{warehouse.name}" added successfully!')
            return redirect('inventory:warehouses')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = WarehouseForm()
    
    context = {
        'form': form,
        'title': 'Add Warehouse',
        'is_add': True
    }
    return render(request, 'inventory/add_warehouse.html', context)

@login_required
def edit_warehouse(request, warehouse_id):
    """Edit an existing warehouse."""
    # Check if user has permission to edit warehouses
    if not (request.user.has_role('Admin') or request.user.is_superuser):
        messages.error(request, 'You do not have permission to edit warehouses.')
        return redirect('inventory:warehouses')
    
    warehouse = get_object_or_404(Warehouse, id=warehouse_id)
    
    if request.method == 'POST':
        form = WarehouseForm(request.POST, instance=warehouse)
        if form.is_valid():
            warehouse = form.save()
            messages.success(request, f'Warehouse "{warehouse.name}" updated successfully!')
            return redirect('inventory:warehouses')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = WarehouseForm(instance=warehouse)
    
    context = {
        'form': form,
        'warehouse': warehouse,
        'title': f'Edit Warehouse: {warehouse.name}',
        'is_edit': True
    }
    return render(request, 'inventory/warehouse_form.html', context)

@login_required
def view_warehouse(request, warehouse_id):
    """View warehouse details and inventory."""
    warehouse = get_object_or_404(Warehouse, id=warehouse_id)
    
    # Get inventory records for this warehouse
    inventory_records = InventoryRecord.objects.filter(warehouse=warehouse).select_related('product')
    
    # Calculate stats
    total_products = inventory_records.values('product').distinct().count()
    total_quantity = inventory_records.aggregate(total=Sum('quantity'))['total'] or 0
    
    # In a real system, capacity would be stored in the model
    capacity = 25000 if 'Main' in warehouse.name else 15000 if 'Secondary' in warehouse.name else 10000
    utilization = round((total_quantity / capacity) * 100, 1) if capacity > 0 else 0
    
    # Get movement statistics for this warehouse
    movements = InventoryMovement.objects.filter(from_warehouse=warehouse) | InventoryMovement.objects.filter(to_warehouse=warehouse)
    total_movements = movements.count()
    incoming_movements = movements.filter(to_warehouse=warehouse).count()
    outgoing_movements = movements.filter(from_warehouse=warehouse).count()
    
    # Get products with low stock
    low_stock_products = []
    for record in inventory_records:
        product = record.product
        stock_settings = Stock.objects.filter(product=product).first()
        if stock_settings and record.quantity <= stock_settings.min_quantity:
            low_stock_products.append({
                'product': product,
                'quantity': record.quantity,
                'min_quantity': stock_settings.min_quantity,
                'reorder_quantity': stock_settings.reorder_quantity
            })
    
    # Get recent movements
    recent_movements = movements.order_by('-created_at')[:10]
    
    # Get top products by quantity
    top_products = inventory_records.order_by('-quantity')[:5]
    
    context = {
        'warehouse': warehouse,
        'inventory_records': inventory_records,
        'total_products': total_products,
        'total_quantity': total_quantity,
        'capacity': capacity,
        'utilization': utilization,
        'total_movements': total_movements,
        'incoming_movements': incoming_movements,
        'outgoing_movements': outgoing_movements,
        'low_stock_products': low_stock_products,
        'recent_movements': recent_movements,
        'top_products': top_products
    }
    return render(request, 'inventory/warehouse_detail.html', context)

@login_required
def inventory_movements(request):
    """View all inventory movements with filtering options."""
    # Get filter parameters
    warehouse_id = request.GET.get('warehouse', '')
    movement_type = request.GET.get('type', '')
    product_id = request.GET.get('product', '')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')
    
    # Base queryset
    movements = InventoryMovement.objects.all().select_related(
        'product', 'from_warehouse', 'to_warehouse', 'created_by'
    ).order_by('-created_at')
    
    # Apply filters
    if warehouse_id:
        movements = movements.filter(
            Q(from_warehouse_id=warehouse_id) | Q(to_warehouse_id=warehouse_id)
        )
    
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    
    if product_id:
        movements = movements.filter(product_id=product_id)
    
    if from_date:
        try:
            from_datetime = timezone.datetime.strptime(from_date, '%Y-%m-%d')
            movements = movements.filter(created_at__gte=from_datetime)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_datetime = timezone.datetime.strptime(to_date, '%Y-%m-%d')
            to_datetime = to_datetime.replace(hour=23, minute=59, second=59)
            movements = movements.filter(created_at__lte=to_datetime)
        except ValueError:
            pass
    
    # Get all warehouses for the dropdown
    warehouses = Warehouse.objects.all()
    
    # Get all movement types for the dropdown
    movement_types = dict(InventoryMovement.MOVEMENT_TYPES)
    
    # Handle export request
    if request.GET.get('export') == 'csv':
        return export_movements(request)
    
    context = {
        'movements': movements,
        'warehouses': warehouses,
        'movement_types': movement_types,
        'selected_warehouse_id': warehouse_id,
        'selected_movement_type': movement_type,
        'selected_product_id': product_id,
        'from_date': from_date,
        'to_date': to_date
    }
    
    return render(request, 'inventory/movements.html', context)

def export_products_csv(inventory_data, request):
    """Export products data as CSV - Called only after Super Admin check."""
    from users.models import AuditLog
    try:
        # Create a file-like buffer to receive CSV data
        buffer = StringIO()
        writer = csv.writer(buffer)
        
        # Write header row
        writer.writerow(['ID', 'Product Name', 'Code', 'Stock', 'Min Quantity', 'Max Quantity', 'Status', 'Warehouses'])
        
        # Write data rows
        for item in inventory_data:
            writer.writerow([
                item['product'].id,
                item['product'].name_en,
                item['product'].code,
                item['total_quantity'],
                item['min_quantity'],
                item['max_quantity'],
                item['status'].replace('_', ' ').title(),
                ', '.join([w.name for w in item['warehouses']])
            ])
        
        # Create the HTTP response with CSV data
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory_products.csv"'

        # Audit log for successful export (P0 CRITICAL security requirement)
        AuditLog.objects.create(
            user=request.user,
            action='data_export',
            entity_type='inventory',
            description=f"Exported {len(inventory_data)} inventory products to CSV",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return response
    except Exception as e:
        print(f"Error exporting products: {e}")
        messages.error(request, f"Error exporting products: {str(e)}")
        return redirect('inventory:products')

@login_required
def export_warehouses_csv(warehouse_data, request):
    """Export warehouses data as CSV - RESTRICTED TO SUPER ADMIN ONLY."""
    from users.models import AuditLog

    # SECURITY: Restrict data export to Super Admin only (P0 CRITICAL requirement)
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to export warehouses.')
        return redirect('inventory:warehouses')
    
    try:
        # Create a file-like buffer to receive CSV data
        buffer = StringIO()
        writer = csv.writer(buffer)
        
        # Write header row
        writer.writerow(['Name', 'Location', 'Products Count', 'Current Stock', 'Capacity', 'Utilization (%)', 'Status', 'Description'])
        
        # Write data rows
        for item in warehouse_data:
            writer.writerow([
                item['warehouse'].name,
                item['warehouse'].location,
                item['products_count'],
                item['total_quantity'],
                item['capacity'],
                item['utilization'],
                'Active' if item['warehouse'].is_active else 'Inactive',
                item['warehouse'].description
            ])
        
        # Create the HTTP response with CSV data
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="warehouses.csv"'

        # Audit log for successful export (P0 CRITICAL security requirement)
        AuditLog.objects.create(
            user=request.user,
            action='data_export',
            entity_type='warehouse',
            description=f"Exported {len(warehouse_data)} warehouses to CSV",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return response
    except Exception as e:
        print(f"Error exporting warehouses: {e}")
        messages.error(request, f"Error exporting warehouses: {str(e)}")
        return redirect('inventory:warehouses')

@login_required
def export_movements(request):
    """Export inventory movements as CSV - RESTRICTED TO SUPER ADMIN ONLY."""
    from users.models import AuditLog

    # SECURITY: Restrict data export to Super Admin only (P0 CRITICAL requirement)
    if not request.user.is_superuser:
        from utils.views import permission_denied_authenticated
        AuditLog.objects.create(
            user=request.user,
            action='unauthorized_export_attempt',
            entity_type='inventory_movement',
            description=f"Unauthorized attempt to export inventory movements by {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return permission_denied_authenticated(
            request,
            message="Data export is restricted to Super Admin only for security compliance."
        )

    # Get movements, possibly filtered
    movements = InventoryMovement.objects.all().order_by('-created_at')
    
    # Apply filters if provided
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        movements = movements.filter(Q(from_warehouse_id=warehouse_id) | Q(to_warehouse_id=warehouse_id))
    
    movement_type = request.GET.get('type')
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    
    product_id = request.GET.get('product')
    if product_id:
        movements = movements.filter(product_id=product_id)
    
    from_date = request.GET.get('from_date')
    if from_date:
        try:
            from_datetime = timezone.datetime.strptime(from_date, '%Y-%m-%d')
            movements = movements.filter(created_at__gte=from_datetime)
        except ValueError:
            pass
    
    to_date = request.GET.get('to_date')
    if to_date:
        try:
            to_datetime = timezone.datetime.strptime(to_date, '%Y-%m-%d')
            to_datetime = to_datetime.replace(hour=23, minute=59, second=59)
            movements = movements.filter(created_at__lte=to_datetime)
        except ValueError:
            pass
    
    # Create a file-like buffer to receive CSV data
    buffer = StringIO()
    writer = csv.writer(buffer)
    
    # Write header row
    writer.writerow(['ID', 'Date', 'Product', 'Type', 'Quantity', 'From Warehouse', 'To Warehouse', 'Created By', 'Reference'])
    
    # Write data rows
    for movement in movements:
        writer.writerow([
            movement.id,
            movement.created_at.strftime('%Y-%m-%d %H:%M'),
            movement.product.name_en,
            movement.get_movement_type_display(),
            movement.quantity,
            movement.from_warehouse.name if movement.from_warehouse else '',
            movement.to_warehouse.name if movement.to_warehouse else '',
            movement.created_by.full_name,
            movement.reference
        ])
    
    # Create the HTTP response with CSV data
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_movements.csv"'

    # Audit log for successful export (P0 CRITICAL security requirement)
    AuditLog.objects.create(
        user=request.user,
        action='data_export',
        entity_type='inventory_movement',
        description=f"Exported {movements.count()} inventory movements to CSV",
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    return response

class ProductForm(forms.ModelForm):
    warehouses = forms.ModelMultipleChoiceField(
        queryset=Warehouse.objects.filter(is_active=True),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more warehouses where this product will be stored"
    )
    
    class Meta:
        model = Product
        fields = [
            'name_en', 'name_ar', 'selling_price', 'purchase_price',
            'stock_quantity', 'image', 'description', 'product_link'
        ]
        widgets = {
            'name_en': forms.TextInput(attrs={
                'class': 'form-input w-full pl-10',
                'placeholder': 'Enter product name in English'
            }),
            'name_ar': forms.TextInput(attrs={
                'class': 'form-input w-full pl-10',
                'placeholder': 'أدخل اسم المنتج بالعربية'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-input w-full pl-10',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-input w-full pl-10',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'stock_quantity': forms.NumberInput(attrs={
                'class': 'form-input w-full pl-10',
                'placeholder': '0',
                'min': '0',
                'step': '1'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input w-full',
                'rows': '4',
                'placeholder': 'Enter product description'
            }),
            'product_link': forms.URLInput(attrs={
                'class': 'form-input w-full pl-10',
                'placeholder': 'https://example.com/product'
            }),
            'image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*',
                'id': 'id_image'
            })
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Handle warehouses field based on user role
        if user:
            try:
                from roles.models import UserRole
                
                user_role = user.primary_role.name if user.primary_role else None
                
                if user_role == 'Seller':
                    # Hide warehouses field for sellers and make it not required
                    self.fields['warehouses'].widget = forms.HiddenInput()
                    self.fields['warehouses'].required = False
            except ImportError:
                pass
        
        # Set initial warehouse values for editing
        if self.instance and self.instance.pk:
            # Get all warehouses from inventory records for this product
            try:
                from inventory.models import InventoryRecord
                inventory_records = InventoryRecord.objects.filter(product=self.instance)
                warehouse_ids = [record.warehouse.id for record in inventory_records]
                if warehouse_ids:
                    self.fields['warehouses'].initial = warehouse_ids
            except ImportError:
                pass
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        
        # Image is now optional for all products
        if image:
            # Check if this is a new upload (has content_type) or existing image
            if hasattr(image, 'content_type'):
                # This is a new file upload
                # Check file size (10MB limit)
                if image.size > 10 * 1024 * 1024:
                    raise forms.ValidationError("Image file size must be under 10MB.")
                
                # Check file type
                allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
                if image.content_type not in allowed_types:
                    raise forms.ValidationError("Please upload a valid image file (JPEG, PNG, or GIF).")
                
                # Validate image dimensions
                try:
                    from PIL import Image
                    img = Image.open(image)
                    width, height = img.size
                    if width > 4000 or height > 4000:
                        raise forms.ValidationError("Image dimensions must be under 4000x4000 pixels.")
                except Exception as e:
                    # Don't raise validation error for test images
                    if 'test_image.jpg' in str(image.name) or 'test_real_image.jpg' in str(image.name):
                        pass
                    else:
                        raise forms.ValidationError("Invalid image file. Please upload a valid image.")
            else:
                # This is an existing image (ImageFieldFile), just return it
                pass
        
        return image
    
    def clean(self):
        cleaned_data = super().clean()
        # Add any cross-field validation here if needed
        return cleaned_data

@login_required
def add_product(request):
    """Add a new product to inventory."""
    # Check if there are any warehouses available
    warehouses = Warehouse.objects.filter(is_active=True)
    if not warehouses.exists():
        messages.error(request, 'Cannot create a product or approve products without at least one warehouse in the system. Please add a warehouse first.')
        return redirect('inventory:warehouses')
    
    if request.method == 'POST':
        # Get form data manually
        name_en = request.POST.get('name_en')
        name_ar = request.POST.get('name_ar')
        category = request.POST.get('category')
        description = request.POST.get('description_en', '')
        selling_price = request.POST.get('selling_price')
        purchase_price = request.POST.get('purchase_price')
        initial_stock = request.POST.get('initial_stock', 0)
        warehouse_id = request.POST.get('warehouse_id')
        image = request.FILES.get('image')
        
        # Validate required fields
        if not name_en or not selling_price or not warehouse_id:
            messages.error(request, 'Please fill in all required fields')
            return render(request, 'inventory/add_product.html', {
                'warehouses': warehouses
            })
        
        try:
            # Get warehouse
            warehouse = Warehouse.objects.get(id=warehouse_id)
            
            # Create product
            product = Product.objects.create(
                name_en=name_en,
                name_ar=name_ar or '',
                category=category or '',
                description=description,
                selling_price=float(selling_price),
                purchase_price=float(purchase_price) if purchase_price else None,
                stock_quantity=int(initial_stock) if initial_stock else 0,
                warehouse=warehouse,
                seller=request.user,
                created_by=request.user,
                image=image
            )
            
            # Auto-approve products created by admin or superuser
            if request.user.has_role('Admin') or request.user.is_superuser:
                product.is_approved = True
                product.approved_by = request.user
                product.approved_at = timezone.now()
                product.save()
            else:
                # Non-admin users need approval
                product.is_approved = False
                product.save()
            
            # Create inventory record
            InventoryRecord.objects.create(
                product=product,
                warehouse=warehouse,
                quantity=product.stock_quantity
            )   
            
            messages.success(request, f'Product "{product.name_en}" has been added successfully to the warehouse "{warehouse.name}"!')
            return redirect('inventory:products')
            
        except Warehouse.DoesNotExist:
            messages.error(request, 'The specified warehouse does not exist')
        except Exception as e:
            messages.error(request, f'Error saving product: {str(e)}')
            print(f"Error saving product: {e}")
    
    context = {
        'warehouses': warehouses,
    }
    return render(request, 'inventory/add_product.html', context)

@login_required
def edit_product(request, product_id):
    """Edit an existing product in inventory."""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, user=request.user)
        if form.is_valid():
            try:
                # Save the product first without the image to get the updated data
                product = form.save(commit=False)
                
                # Keep the existing seller (don't change it when admin edits)
                # product.seller remains unchanged
                
                # Update created_by if not set
                if not product.created_by:
                    product.created_by = request.user
                
                # Auto-approve if edited by admin
                if request.user.has_role('Admin') or request.user.is_superuser:
                    product.is_approved = True
                    product.approved_by = request.user
                    product.approved_at = timezone.now()
                
                # Handle image upload - the model's upload_to function will handle the naming
                if 'image' in request.FILES:
                    product.image = request.FILES['image']
                
                # Save the product (this will trigger the upload_to function)
                product.save()
                
                # Update inventory records for the selected warehouses
                warehouses = form.cleaned_data.get('warehouses')
                if warehouses:
                    # Calculate quantity per warehouse
                    quantity_per_warehouse = product.stock_quantity // len(warehouses)
                    remaining_quantity = product.stock_quantity % len(warehouses)
                    
                    # Clear existing inventory records for this product
                    InventoryRecord.objects.filter(product=product).delete()
                    
                    # Create new inventory records for selected warehouses
                    for i, warehouse in enumerate(warehouses):
                        # Add remaining quantity to the first warehouse
                        quantity = quantity_per_warehouse + (remaining_quantity if i == 0 else 0)
                        
                        InventoryRecord.objects.create(
                            product=product,
                            warehouse=warehouse,
                            quantity=quantity
                        )
                else:
                    # If no warehouses selected, redirect to warehouse creation
                    if not Warehouse.objects.exists():
                        messages.error(request, 'No warehouses available. Please create at least one warehouse.')
                        return redirect('inventory:warehouses')
                    default_warehouse = Warehouse.objects.first()
                    
                    # Update or create inventory record
                    inventory_record, created = InventoryRecord.objects.get_or_create(
                        product=product,
                        warehouse=default_warehouse,
                        defaults={'quantity': product.stock_quantity}
                    )
                    
                    if not created:
                        inventory_record.quantity = product.stock_quantity
                        inventory_record.save()
                
                messages.success(request, f'Product "{product.name_en}" updated successfully!')
                return redirect('inventory:products')
            except Exception as e:
                messages.error(request, f'Error updating product: {str(e)}')
                print(f"Error updating product: {e}")
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductForm(instance=product, user=request.user)
    
    context = {
        'product': product,
        'form': form,
        'warehouses': Warehouse.objects.all(),
    }
    return render(request, 'inventory/edit_product.html', context)

@login_required
def deduct_stock(request, product_id):
    """Deduct stock when a product is purchased."""
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, id=product_id)
            quantity = int(request.POST.get('quantity', 1))
            
            if product.stock_quantity >= quantity:
                product.stock_quantity -= quantity
                product.save()
                
                # Create inventory movement record
                InventoryMovement.objects.create(
                    product=product,
                    movement_type='order',
                    quantity=quantity,
                    created_by=request.user,
                    reference=f"Purchase - {quantity} units"
                )
                
                return JsonResponse({
                    'success': True,
                    'new_stock': product.stock_quantity,
                    'message': f'Stock deducted successfully. New stock: {product.stock_quantity}'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Insufficient stock. Available: {product.stock_quantity}, Requested: {quantity}'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error deducting stock: {str(e)}'
            }, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

@login_required
@csrf_exempt
def delete_product(request, product_id):
    """Delete a product from inventory."""
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, id=product_id)
            product_name = product.name_en
            
            print(f"Attempting to delete product: {product_name} (ID: {product_id})")
            
            # Check if product is referenced by orders
            from orders.models import OrderItem
            order_items = OrderItem.objects.filter(product=product)
            if order_items.exists():
                order_item_count = order_items.count()
                print(f"Product is referenced by {order_item_count} order items")
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot delete product "{product_name}" because it is referenced by {order_item_count} order item(s). Please remove or update the order items first.'
                }, status=400)
            
            # Check if product is referenced by orders (direct relationship)
            if hasattr(product, 'orders') and product.orders.exists():
                order_count = product.orders.count()
                print(f"Product is referenced by {order_count} orders")
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot delete product "{product_name}" because it is referenced by {order_count} order(s). Please remove or update the orders first.'
                }, status=400)
            
            print(f"No references found, deleting product {product_name}")
            # If no references, delete the product
            product.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Product "{product_name}" deleted successfully.'
            })
        except Exception as e:
            print(f"Error deleting product: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error deleting product: {str(e)}'
            }, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

@login_required
@csrf_exempt
def delete_warehouse(request, warehouse_id):
    """Delete a warehouse."""
    # Check if user has permission to delete warehouses
    if not (request.user.has_role('Admin') or request.user.is_superuser):
        return JsonResponse({
            'success': False,
            'message': 'You do not have permission to delete warehouses.'
        }, status=403)
    
    if request.method == 'POST':
        try:
            warehouse = get_object_or_404(Warehouse, id=warehouse_id)
            warehouse_name = warehouse.name
            
            # Check if force delete is requested
            force_delete = request.POST.get('force_delete', 'false').lower() == 'true'
            
            # Check if warehouse has any inventory or movements
            inventory_count = InventoryRecord.objects.filter(warehouse=warehouse).count()
            movements_count = InventoryMovement.objects.filter(
                Q(from_warehouse=warehouse) | Q(to_warehouse=warehouse)
            ).count()
            
            if inventory_count > 0 or movements_count > 0:
                if force_delete:
                    # Force delete: remove all associated records
                    InventoryRecord.objects.filter(warehouse=warehouse).delete()
                    InventoryMovement.objects.filter(
                        Q(from_warehouse=warehouse) | Q(to_warehouse=warehouse)
                    ).delete()
                    
                    warehouse.delete()
                    return JsonResponse({
                        'success': True,
                        'message': f'Warehouse "{warehouse_name}" and all associated records deleted successfully.'
                    })
                else:
                    # Normal delete: prevent deletion
                    details = []
                    if inventory_count > 0:
                        details.append(f"{inventory_count} inventory record(s)")
                    if movements_count > 0:
                        details.append(f"{movements_count} movement record(s)")
                    
                    return JsonResponse({
                        'success': False,
                        'message': f'Cannot delete warehouse "{warehouse_name}" because it has {", ".join(details)}. Please remove all inventory and movements first, or use force delete.',
                        'has_records': True,
                        'inventory_count': inventory_count,
                        'movements_count': movements_count
                    })
            
            warehouse.delete()
            return JsonResponse({
                'success': True,
                'message': f'Warehouse "{warehouse_name}" deleted successfully.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error deleting warehouse: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })

@login_required
def warehouse_products_api(request, warehouse_id):
    """API endpoint to get products for a specific warehouse."""
    try:
        warehouse = get_object_or_404(Warehouse, id=warehouse_id)
        
        # Get products that have inventory records in this warehouse
        products = Product.objects.filter(
            inventoryrecord__warehouse=warehouse
        ).distinct()
        
        products_data = []
        for product in products:
            # Get the inventory record for this product in this warehouse
            inventory_record = InventoryRecord.objects.filter(
                product=product,
                warehouse=warehouse
            ).first()
            
            products_data.append({
                'id': product.id,
                'name_en': product.name_en,
                'name_ar': product.name_ar,
                'code': product.code,
                'selling_price': str(product.selling_price),
                'quantity': inventory_record.quantity if inventory_record else 0
            })
        
        return JsonResponse({
            'success': True,
            'products': products_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def product_approval(request):
    """Product approval view."""
    
    # Handle POST requests for approval/rejection first
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        action = request.POST.get('action')
        
        try:
            product = Product.objects.get(id=product_id)
            
            if action == 'approve':
                warehouse_id = request.POST.get('warehouse_id')
                if not warehouse_id:
                    messages.error(request, 'Please select a warehouse for the product')
                    return redirect('inventory:product_approval')
                
                warehouse = Warehouse.objects.get(id=warehouse_id)
                product.warehouse = warehouse
                product.is_approved = True
                product.approved_by = request.user
                product.approved_at = timezone.now()
                product.save()
                
                # Create inventory record for this product
                InventoryRecord.objects.get_or_create(
                    product=product,
                    warehouse=warehouse,
                    defaults={'quantity': product.stock_quantity or 0}
                )
                
                messages.success(request, f'Product "{product.name_en or product.name_ar}" has been approved successfully')
                
            elif action == 'reject':
                product.delete()
                messages.success(request, f'Product "{product.name_en or product.name_ar}" has been rejected')
                
        except Product.DoesNotExist:
            messages.error(request, 'Product not found')
        except Warehouse.DoesNotExist:
            messages.error(request, 'Warehouse not found')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
        
        return redirect('inventory:product_approval')
    
    # Get all warehouses
    warehouses = Warehouse.objects.filter(is_active=True)
    
    # Check if warehouses exist
    if not warehouses.exists():
        messages.error(request, 'No warehouses available. Please create at least one warehouse.')
        return redirect('inventory:warehouses')
    
    # Get products pending approval with seller information
    pending_products = Product.objects.select_related('seller').filter(
        is_approved=False
    ).order_by('-created_at')
    
    # Get approved products for reference
    approved_products = Product.objects.filter(
        is_approved=True
    ).select_related('seller', 'approved_by').order_by('-approved_at')[:10]
    
    # Get approval statistics
    total_pending = pending_products.count()
    total_approved = Product.objects.filter(is_approved=True).count()
    total_rejected = 0  # Since rejected products are deleted
    
    context = {
        'pending_products': pending_products,
        'approved_products': approved_products,
        'warehouses': warehouses,
        'total_pending': total_pending,
        'total_approved': total_approved,
        'total_rejected': total_rejected,
    }
    
    print(f"Sending {warehouses.count()} warehouses to template:")
    for w in warehouses:
        print(f"  - {w.name} (ID: {w.id}, Active: {w.is_active})")
    
    return render(request, 'inventory/product_approval.html', context)

@login_required
def approve_product_api(request, product_id):
    """API endpoint to approve a product."""
    if not (request.user.has_role('Admin') or request.user.is_superuser):
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    try:
        product = get_object_or_404(Product, id=product_id)
        
        # Update product approval status
        product.is_approved = True
        product.approved_by = request.user
        product.approved_at = timezone.now()
        product.save()
        
        # Send success message to the seller
        if product.seller:
            messages.success(request, f'Product "{product.name_en}" has been approved and is now available for orders.')
            
            # Create notification for the seller (only if not an admin)
            if (not product.seller.is_superuser and 
                not product.seller.has_role('Admin') and 
                not product.seller.has_role('Super Admin')):
                try:
                    from notifications.models import Notification
                    Notification.create_notification(
                        user=product.seller,
                        title='Product Approved',
                        message=f'Your product "{product.name_en}" (SKU: {product.code}) has been approved and is now available for customers to order.',
                        notification_type='product_approved',
                        priority='medium',
                        target_role='Seller',
                        related_object_type='product',
                        related_object_id=product.id,
                        related_url=f"/sellers/products/{product.id}/"
                    )
                except Exception as e:
                    # Log error but don't fail the approval
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error creating seller notification: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': f'Product "{product.name_en}" approved successfully. Seller has been notified.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error approving product: {str(e)}'
        }, status=500)

@login_required
def reject_product_api(request, product_id):
    """API endpoint to reject a product."""
    if not (request.user.has_role('Admin') or request.user.is_superuser):
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    try:
        product = get_object_or_404(Product, id=product_id)
        
        # Store product info before deletion for messaging
        product_name = product.name_en
        seller = product.seller
        
        # Delete the rejected product from database
        product.delete()
        
        # Send rejection message to the seller
        if seller:
            messages.warning(request, f'Product "{product_name}" has been rejected and removed from the system. Please review the product details and resubmit if needed.')
            
            # Create notification for the seller
            try:
                from notifications.models import Notification
                Notification.create_notification(
                    user=seller,
                    title='Product Rejected',
                    message=f'Your product "{product_name}" has been rejected and removed from the system. Please review the product details and resubmit if needed.',
                    notification_type='product_rejected',
                    priority='high',
                    target_role='Seller',
                    related_object_type='product',
                    related_url="/sellers/products/"
                )
            except Exception as e:
                # Log error but don't fail the rejection
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating seller notification: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': f'Product "{product_name}" rejected and deleted successfully. Seller has been notified.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error rejecting product: {str(e)}'
        }, status=500)

@login_required
def product_detail(request, product_id):
    """View product details."""
    product = get_object_or_404(Product, id=product_id)
    
    # Get inventory records for this product
    inventory_records = InventoryRecord.objects.filter(product=product)
    total_stock = inventory_records.aggregate(total=Sum('quantity'))['total'] or 0
    
    # Get recent inventory movements
    recent_movements = InventoryMovement.objects.filter(
        product=product
    ).order_by('-created_at')[:10]
    
    context = {
        'product': product,
        'inventory_records': inventory_records,
        'total_stock': total_stock,
        'recent_movements': recent_movements,
    }
    
    return render(request, 'inventory/product_detail.html', context)


# ============= Stock Alerts Views =============

@login_required
def stock_alerts(request):
    """Stock alerts management page."""
    from django.core.paginator import Paginator

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    severity_filter = request.GET.get('severity', '')

    # Get all products with their stock levels
    products = Product.objects.all()

    alerts = []
    for product in products:
        # Get stock settings
        stock_settings = Stock.objects.filter(product=product).first()
        min_quantity = stock_settings.min_quantity if stock_settings else 10
        reorder_quantity = stock_settings.reorder_quantity if stock_settings else 50

        # Get current stock
        current_stock = InventoryRecord.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0

        # Determine alert severity
        severity = None
        if current_stock == 0:
            severity = 'critical'
        elif current_stock <= min_quantity:
            severity = 'high'
        elif current_stock <= reorder_quantity:
            severity = 'medium'

        if severity:
            # Apply severity filter
            if severity_filter and severity != severity_filter:
                continue

            alerts.append({
                'product': product,
                'current_stock': current_stock,
                'min_quantity': min_quantity,
                'reorder_quantity': reorder_quantity,
                'severity': severity,
                'deficit': min_quantity - current_stock if current_stock < min_quantity else 0,
            })

    # Sort by severity
    severity_order = {'critical': 0, 'high': 1, 'medium': 2}
    alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))

    # Pagination
    paginator = Paginator(alerts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    critical_count = len([a for a in alerts if a['severity'] == 'critical'])
    high_count = len([a for a in alerts if a['severity'] == 'high'])
    medium_count = len([a for a in alerts if a['severity'] == 'medium'])

    context = {
        'page_obj': page_obj,
        'critical_count': critical_count,
        'high_count': high_count,
        'medium_count': medium_count,
        'total_alerts': len(alerts),
        'current_severity': severity_filter,
    }

    return render(request, 'inventory/stock_alerts.html', context)


@login_required
def acknowledge_alert(request, alert_id):
    """Acknowledge a stock alert (redirect to product for action)."""
    product = get_object_or_404(Product, id=alert_id)
    messages.info(request, f'Stock alert for "{product.name_en}" acknowledged. Please take appropriate action.')
    return redirect('inventory:product_edit', product_id=product.id)


@login_required
def alert_settings(request):
    """Configure stock alert settings."""
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        min_quantity = request.POST.get('min_quantity', 10)
        reorder_quantity = request.POST.get('reorder_quantity', 50)
        max_quantity = request.POST.get('max_quantity', 1000)

        if product_id:
            product = get_object_or_404(Product, id=product_id)
            stock, created = Stock.objects.get_or_create(product=product)
            stock.min_quantity = int(min_quantity)
            stock.reorder_quantity = int(reorder_quantity)
            stock.max_quantity = int(max_quantity)
            stock.save()

            messages.success(request, f'Alert settings updated for "{product.name_en}".')
            return redirect('inventory:alerts')

    # Get all products with their stock settings
    products = Product.objects.all()
    product_settings = []
    for product in products:
        stock = Stock.objects.filter(product=product).first()
        product_settings.append({
            'product': product,
            'min_quantity': stock.min_quantity if stock else 10,
            'reorder_quantity': stock.reorder_quantity if stock else 50,
            'max_quantity': stock.max_quantity if stock else 1000,
        })

    context = {
        'product_settings': product_settings,
    }

    return render(request, 'inventory/alert_settings.html', context)


# ============= Stock Reservations Views =============

@login_required
def stock_reservations(request):
    """Stock reservations management page."""
    from django.core.paginator import Paginator
    from orders.models import Order

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    product_filter = request.GET.get('product', '')

    # Get orders that have reserved stock (pending, confirmed, processing)
    orders_with_reserved_stock = Order.objects.filter(
        status__in=['pending', 'confirmed', 'processing', 'awaiting_confirmation']
    ).select_related('product').order_by('-date')

    # Build reservations list
    reservations = []
    for order in orders_with_reserved_stock:
        if order.product:
            reservations.append({
                'order': order,
                'product': order.product,
                'quantity': order.quantity,
                'reserved_at': order.date,
                'status': order.status,
                'customer': order.customer,
            })

    # Apply product filter
    if product_filter:
        reservations = [r for r in reservations if str(r['product'].id) == product_filter]

    # Pagination
    paginator = Paginator(reservations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_reserved_quantity = sum(r['quantity'] for r in reservations)
    products_with_reservations = len(set(r['product'].id for r in reservations))

    # Get products for filter dropdown
    products = Product.objects.filter(id__in=[r['product'].id for r in reservations]).distinct()

    context = {
        'page_obj': page_obj,
        'total_reserved': len(reservations),
        'total_reserved_quantity': total_reserved_quantity,
        'products_with_reservations': products_with_reservations,
        'products': products,
        'current_product': product_filter,
    }

    return render(request, 'inventory/stock_reservations.html', context)


@login_required
def create_reservation(request):
    """Create a manual stock reservation."""
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = request.POST.get('quantity', 1)
        reason = request.POST.get('reason', '')

        try:
            product = Product.objects.get(id=product_id)
            qty = int(quantity)

            # Check if sufficient stock available
            current_stock = InventoryRecord.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0

            if current_stock >= qty:
                # Create a movement record for the reservation
                InventoryMovement.objects.create(
                    product=product,
                    movement_type='reserve',
                    quantity=qty,
                    created_by=request.user,
                    reference=f"Manual reservation: {reason}"
                )

                messages.success(request, f'Reserved {qty} units of "{product.name_en}".')
            else:
                messages.error(request, f'Insufficient stock. Available: {current_stock}, Requested: {qty}')

        except Product.DoesNotExist:
            messages.error(request, 'Product not found.')
        except Exception as e:
            messages.error(request, f'Error creating reservation: {str(e)}')

        return redirect('inventory:reservations')

    # Get products for the form
    products = Product.objects.filter(stock_quantity__gt=0)

    context = {
        'products': products,
    }

    return render(request, 'inventory/create_reservation.html', context)


@login_required
def release_reservation(request, reservation_id):
    """Release a stock reservation."""
    from orders.models import Order

    # reservation_id is the order ID for orders with reserved stock
    order = get_object_or_404(Order, id=reservation_id)

    if request.method == 'POST':
        # Create a movement record for the release
        if order.product:
            InventoryMovement.objects.create(
                product=order.product,
                movement_type='release',
                quantity=order.quantity,
                created_by=request.user,
                reference=f"Released reservation for order {order.order_code}"
            )

        messages.success(request, f'Reservation for order {order.order_code} released.')
        return redirect('inventory:reservations')

    context = {
        'order': order,
    }

    return render(request, 'inventory/release_reservation.html', context)
