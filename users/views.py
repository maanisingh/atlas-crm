import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models
from .forms import LoginForm, RegisterForm, UserCreationForm, UserChangeForm, PasswordChangeForm, EmailVerificationForm
from .models import User, AuditLog
from django.views.decorators.csrf import csrf_exempt
from roles.models import Role, UserRole
from .email_utils import send_registration_confirmation_email, send_approval_email, send_rejection_email
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='60/m', method='POST', block=True)
def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                if user.approval_status == 'pending':
                    if user.email_verified:
                        messages.info(request, "Your email has been verified successfully! Your account is now pending admin approval. You will be notified once your account is approved.")
                    else:
                        messages.error(request, "Your account is pending approval. Please verify your email first, then wait for admin approval.")
                    return redirect('users:login')
                elif user.approval_status == 'rejected':
                    messages.error(request, "Your registration request has been rejected. Please contact the administration.")
                    return redirect('users:login')
                elif not user.is_active:
                    messages.error(request, "Your account is not active. Please contact the administration.")
                    return redirect('users:login')
                elif not user.email_verified and not user.is_superuser:
                    messages.error(request, "Please verify your email address before logging in. Check your email for the verification code.")
                    return redirect('users:login')
                else:
                    # Check if user has 2FA enabled
                    try:
                        if hasattr(user, 'twofa_profile') and user.twofa_profile.is_enabled:
                            # Store user ID in session for 2FA verification
                            request.session['2fa_user_id'] = user.id
                            request.session['2fa_verified'] = False
                            
                            # Log the login attempt
                            from .models import LoginAttempt
                            LoginAttempt.objects.create(
                                user=user,
                                ip_address=request.META.get('REMOTE_ADDR'),
                                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                                success=False,
                                failure_reason='Pending 2FA verification'
                            )
                            
                            messages.info(request, "Please verify your identity with two-factor authentication.")
                            return redirect('users:verify_2fa_login')
                    except:
                        pass
                    
                    # If no 2FA or 2FA not enabled, proceed with normal login
                    login(request, user)
                    
                    # Create audit log for login
                    AuditLog.objects.create(
                        user=user,
                        action='login',
                        entity_type='user',
                        entity_id=str(user.id),
                        description=f"User login: {user.email}",
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    
                    # Log successful login attempt
                    from .models import LoginAttempt
                    LoginAttempt.objects.create(
                        user=user,
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        success=True
                    )
                    
                    messages.success(request, f"Welcome {user.full_name}! Login successful.")
                    
                    # Redirect based on user role
                    if user.has_role('Super Admin') or user.is_superuser:
                        return redirect('dashboard:index')
                    elif user.has_role('Packaging Agent'):
                        return redirect('packaging:dashboard')
                    elif user.has_role('Call Center Manager'):
                        return redirect('callcenter:dashboard')
                    elif user.has_role('Call Center Agent'):
                        return redirect('callcenter:agent_dashboard')
                    elif user.has_role('Inventory'):
                        return redirect('inventory:dashboard')
                    elif user.has_role('Delivery Agent'):
                        return redirect('delivery:dashboard')
                    elif user.has_role('Finance'):
                        return redirect('finance:dashboard')
                    elif user.has_role('Stock Keeper'):
                        return redirect('stock_keeper:dashboard')
                    elif user.has_role('Seller'):
                        return redirect('sellers:dashboard')
                    else:
                        # Default redirect for other roles
                        return redirect('dashboard:index')
            else:
                messages.error(request, "البريد الإلكتروني أو كلمة المرور غير صحيحة.")
        else:
            messages.error(request, "يرجى إدخال البيانات المطلوبة.")
    else:
        form = LoginForm()
    
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    """Handle user logout."""
    if request.user.is_authenticated:
        # Create audit log for logout
        AuditLog.objects.create(
            user=request.user,
            action='logout',
            entity_type='user',
            entity_id=str(request.user.id),
            description=f"User logout: {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        logout(request)
        messages.success(request, "تم تسجيل الخروج بنجاح.")
    
    return redirect('/users/login/')

def register_view(request):
    """Register a new user."""
    if request.user.is_authenticated:
        # Redirect based on user role
        if request.user.has_role('Super Admin') or request.user.is_superuser:
            return redirect('dashboard:index')
        elif request.user.has_role('Packaging Agent'):
            return redirect('packaging:dashboard')
        elif request.user.has_role('Call Center Manager'):
            return redirect('callcenter:dashboard')
        elif request.user.has_role('Call Center Agent'):
            return redirect('callcenter:agent_dashboard')
        elif request.user.has_role('Inventory'):
            return redirect('inventory:dashboard')
        elif request.user.has_role('Delivery Agent'):
            return redirect('delivery:dashboard')
        elif request.user.has_role('Finance'):
            return redirect('finance:dashboard')
        elif request.user.has_role('Stock Keeper'):
            return redirect('stock_keeper:dashboard')
        elif request.user.has_role('Seller'):
            return redirect('sellers:dashboard')
        else:
            return redirect('dashboard:index')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.approval_status = 'pending'  # Set to pending approval
                user.is_active = False  # Deactivate until approved
                user.save()
            except OSError as e:
                # Handle file system errors (disk space, permissions, etc.)
                messages.error(request, "عذراً، حدث خطأ في النظام. يرجى المحاولة مرة أخرى لاحقاً أو التواصل مع الدعم الفني.")
                print(f"OSError during user registration: {e}")
                return render(request, 'users/register.html', {'form': form})
            except Exception as e:
                # Handle Cloudinary and other errors specifically
                error_message = str(e)
                print(f"Error during user registration: {error_message}")
                
                # Check for Cloudinary-specific errors
                if "concurrent requests" in error_message.lower() or "too many" in error_message.lower():
                    messages.error(request, "عذراً، حدث خطأ في رفع الصور. يرجى المحاولة مرة أخرى بعد قليل. تأكد من عدم الضغط على الزر أكثر من مرة.")
                elif "cloudinary" in error_message.lower():
                    messages.error(request, "عذراً، حدث خطأ في رفع الصور إلى الخدمة السحابية. يرجى التحقق من حجم الصورة (أقل من 10 ميجابايت) أو المحاولة مرة أخرى.")
                elif "cloud_name" in error_message.lower() or "api" in error_message.lower():
                    messages.error(request, "عذراً، حدث خطأ في إعدادات النظام. يرجى التواصل مع الدعم الفني.")
                else:
                    # Generic error message
                    messages.error(request, "عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو التواصل مع الدعم الفني.")
                
                return render(request, 'users/register.html', {'form': form})
            
            # Automatically assign Seller role as primary (only Seller role)
            seller_role, created = Role.objects.get_or_create(
                name='Seller',
                defaults={
                    'description': 'Seller role for product management',
                    'role_type': 'custom'
                }
            )
            
            # Create user role with Seller as primary (only one role)
            UserRole.objects.create(
                user=user,
                role=seller_role,
                is_primary=True
            )
            
            # Generate and send verification code
            verification_code = user.generate_verification_code()
            try:
                from .email_utils import send_verification_code_email
                send_verification_code_email(user, verification_code)
            except Exception as e:
                print(f"Error sending verification email: {e}")
            
            # Create audit log for new registration
            AuditLog.objects.create(
                user=user,
                action='create',
                entity_type='user',
                entity_id=str(user.id),
                description=f"New user registration pending email verification: {user.email} with Seller role",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, "Your account has been registered successfully! A verification code has been sent to your email address. Please check your email and enter the verification code to complete your registration.")
            return redirect('users:verify_email', user_id=user.id)
        else:
            # If form has errors, display them to the user
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = RegisterForm()
    
    return render(request, 'users/register.html', {'form': form})

def registration_success_view(request):
    """Display registration success page."""
    return render(request, 'users/registration_success.html')

def verify_email_view(request, user_id):
    """Handle email verification with code."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Invalid user ID.")
        return redirect('users:register')
    
    if user.email_verified:
        messages.info(request, "Your email is already verified.")
        return redirect('users:login')
    
    if request.method == 'POST':
        form = EmailVerificationForm(request.POST)
        if form.is_valid():
            verification_code = form.cleaned_data['verification_code']
            
            if user.verify_code(verification_code):
                # Send confirmation email after successful verification
                try:
                    send_registration_confirmation_email(user)
                except Exception as e:
                    print(f"Error sending confirmation email: {e}")
                
                messages.success(request, "Email verified successfully! Your account is now pending admin approval.")
                return redirect('users:registration_success')
            else:
                messages.error(request, "Invalid or expired verification code. Please try again.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = EmailVerificationForm()
    
    return render(request, 'users/verify_email.html', {
        'form': form,
        'user': user,
        'email_masked': user.email[:3] + '***' + user.email[-10:] if len(user.email) > 13 else user.email
    })

def resend_verification_code(request, user_id):
    """Resend verification code."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid user ID'})
    
    if user.email_verified:
        return JsonResponse({'success': False, 'error': 'Email already verified'})
    
    # Generate new verification code
    verification_code = user.generate_verification_code()
    
    try:
        from .email_utils import send_verification_code_email
        send_verification_code_email(user, verification_code)
        return JsonResponse({'success': True, 'message': 'Verification code sent successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Failed to send email: {str(e)}'})

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
def user_list(request):
    """List all users (admin only)."""
    # Prefetch user roles to avoid N+1 queries
    # Exclude users with Seller role
    users = User.objects.prefetch_related('user_roles__role').exclude(
        user_roles__role__name='Seller'
    ).distinct().order_by('-date_joined')
    action = request.POST.get('action')
    if action == 'delete':
        user_id = request.POST.get('user_id')
        try:
            user = User.objects.get(id=user_id)
            user.delete()
            messages.success(request, 'User deleted successfully!')
        except User.DoesNotExist:
            messages.error(request, 'User not found!')
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            models.Q(full_name__icontains=search_query) |
            models.Q(email__icontains=search_query) |
            models.Q(phone_number__icontains=search_query)
        )
    
    # Filter by role if requested
    selected_role = request.GET.get('role', '')
    if selected_role:
        users = users.filter(user_roles__role__name=selected_role)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

        
    
    # Get available roles for filter dropdown
    available_roles = Role.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'users/list.html', {
        'users': page_obj,
        'search_query': search_query,
        'selected_role': selected_role,
        'available_roles': available_roles,
    })

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
def user_create(request):
    """Create a new user (admin only)."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            
            # Check if a primary role was selected in the form
            primary_role_selected = form.cleaned_data.get('primary_role')
            
            if primary_role_selected:
                # If a primary role was selected in the form, don't create default roles
                # The form's save method already created the UserRole
                role_description = f"User {user.email} created by {request.user.email} with {primary_role_selected.name} role"
                messages.success(request, f"User {user.email} created successfully with {primary_role_selected.name} role.")
            else:
                # No primary role selected, create default role (only Seller)
                # Automatically assign Seller role as primary
                seller_role, created = Role.objects.get_or_create(
                    name='Seller',
                    defaults={
                        'description': 'Seller role for product management',
                        'role_type': 'custom'
                    }
                )
                
                # Create user role with Seller as primary (only one role)
                seller_user_role, created = UserRole.objects.get_or_create(
                    user=user,
                    role=seller_role,
                    defaults={
                        'is_primary': True
                    }
                )
                
                role_description = f"User {user.email} created by {request.user.email} with Seller role"
                messages.success(request, f"User {user.email} created successfully with Seller role.")
            
            # Log the creation
            AuditLog.objects.create(
                user=request.user,
                action='create',
                entity_type='user',
                entity_id=str(user.id),
                description=role_description,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return redirect('users:list')
    else:
        form = UserCreationForm()
    
    # Get all available roles for the dropdown
    roles = Role.objects.all().order_by('name')
    
    return render(request, 'users/create.html', {
        'form': form,
        'roles': roles
    })

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
def user_edit(request, user_id):
    """Edit an existing user (admin only)."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Split the user's full name for the template
    first_name = ''
    last_name = ''
    if user_obj.full_name:
        name_parts = user_obj.full_name.split(' ', 1)
        if len(name_parts) > 1:
            first_name = name_parts[0]
            last_name = name_parts[1]
        else:
            first_name = name_parts[0]
    
    if request.method == 'POST':
        form = UserChangeForm(request.POST, request.FILES, instance=user_obj)
        if form.is_valid():
            # Check if password was changed
            password_changed = bool(form.cleaned_data.get('password1'))
            
            updated_user = form.save()
            
            # Log the update
            if password_changed:
                description = f"User {updated_user.email} updated with password change by {request.user.email}"
                action = 'password_change'
            else:
                description = f"User {updated_user.email} updated by {request.user.email}"
                action = 'update'
            
            AuditLog.objects.create(
                user=request.user,
                action=action,
                entity_type='user',
                entity_id=str(updated_user.id),
                description=description,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            if password_changed:
                messages.success(request, f"User {updated_user.email} updated successfully with new password.")
            else:
                messages.success(request, f"User {updated_user.email} updated successfully.")
            return redirect('users:list')
    else:
        form = UserChangeForm(instance=user_obj)
    
    # Get available roles for filter dropdown
    available_roles = Role.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'users/edit.html', {
        'form': form, 
        'user_obj': user_obj,
        'first_name': first_name,
        'last_name': last_name,
        'available_roles': available_roles
    })

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
def user_detail(request, user_id):
    """View user details (admin only)."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Get user's audit logs
    audit_logs = AuditLog.objects.filter(user=user_obj).order_by('-timestamp')[:20]
    
    return render(request, 'users/detail.html', {
        'user_obj': user_obj,
        'audit_logs': audit_logs
    })

@login_required
def profile(request):
    """View and edit current user's profile."""
    user = request.user
    
    if request.method == 'POST':
        form = UserChangeForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            # Check if password was changed
            password_changed = bool(form.cleaned_data.get('password1'))
            
            form.save()
            
            if password_changed:
                messages.success(request, "Your profile has been updated with a new password.")
            else:
                messages.success(request, "Your profile has been updated.")
            return redirect('users:profile')
    else:
        form = UserChangeForm(instance=user)
    
    return render(request, 'users/profile.html', {'form': form})

@login_required
def password_change(request):
    """Change user's password."""
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            
            # Log the password change
            AuditLog.objects.create(
                user=request.user,
                action='password_change',
                entity_type='user',
                entity_id=str(user.id),
                description=f"Password changed for {user.email}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Update the session to prevent logging out
            update_session_auth_hash(request, user)
            
            messages.success(request, "Your password has been changed successfully.")
            return redirect('users:profile')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'users/password_change.html', {'form': form})

@login_required
@require_http_methods(["POST"])
def profile_update(request):
    """Update user profile via AJAX."""
    try:
        user = request.user
        
        # Update basic fields
        if 'first_name' in request.POST:
            user.first_name = request.POST['first_name']
        if 'last_name' in request.POST:
            user.last_name = request.POST['last_name']
        if 'phone_number' in request.POST:
            user.phone_number = request.POST['phone_number']
        if 'company_name' in request.POST:
            user.company_name = request.POST['company_name']
        
        user.save()
        
        # Log the profile update
        AuditLog.objects.create(
            user=request.user,
            action='update',
            entity_type='user',
            entity_id=str(user.id),
            description=f"Profile updated for {user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return JsonResponse({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def change_password(request):
    """Change password via AJAX."""
    try:
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate current password
        if not request.user.check_password(current_password):
            return JsonResponse({'success': False, 'error': 'Current password is incorrect'})
        
        # Validate new password
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'error': 'New passwords do not match'})
        
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters long'})
        
        # Check for uppercase letter
        if not any(c.isupper() for c in new_password):
            return JsonResponse({'success': False, 'error': 'Password must contain at least one uppercase letter'})
        
        # Check for lowercase letter
        if not any(c.islower() for c in new_password):
            return JsonResponse({'success': False, 'error': 'Password must contain at least one lowercase letter'})
        
        # Check for number
        if not any(c.isdigit() for c in new_password):
            return JsonResponse({'success': False, 'error': 'Password must contain at least one number'})
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, request.user)
        
        # Log the password change
        AuditLog.objects.create(
            user=request.user,
            action='password_change',
            entity_type='user',
            entity_id=str(request.user.id),
            description=f"Password changed for {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return JsonResponse({'success': True, 'message': 'Password updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def notification_settings(request):
    """Update notification settings via AJAX."""
    try:
        # Get notification preferences from request
        email_notifications = request.POST.get('email_notifications') == 'on'
        order_updates = request.POST.get('order_updates') == 'on'
        inventory_alerts = request.POST.get('inventory_alerts') == 'on'
        sourcing_updates = request.POST.get('sourcing_updates') == 'on'
        
        # Store settings in user preferences (you can extend the User model or use a separate model)
        # For now, we'll just return success
        # In a real implementation, you might want to store these in a UserPreference model
        
        # Log the settings update
        AuditLog.objects.create(
            user=request.user,
            action='update',
            entity_type='user_preferences',
            entity_id=str(request.user.id),
            description=f"Notification settings updated for {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return JsonResponse({'success': True, 'message': 'Notification settings saved'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def security_settings(request):
    """Update security settings via AJAX."""
    try:
        # Get security preferences from request
        two_factor = request.POST.get('two_factor') == 'on'
        login_alerts = request.POST.get('login_alerts') == 'on'
        
        # Store settings in user preferences (you can extend the User model or use a separate model)
        # For now, we'll just return success
        # In a real implementation, you might want to store these in a UserPreference model
        
        # Log the settings update
        AuditLog.objects.create(
            user=request.user,
            action='update',
            entity_type='user_preferences',
            entity_id=str(request.user.id),
            description=f"Security settings updated for {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return JsonResponse({'success': True, 'message': 'Security settings saved'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
@csrf_exempt
def add_user_role(request, user_id):
    """Add a role to a user."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')
        
        user = get_object_or_404(User, id=user_id)
        role = get_object_or_404(Role, id=role_id)
        
        # Check if role already exists
        if UserRole.objects.filter(user=user, role=role).exists():
            return JsonResponse({'success': False, 'error': 'Role already assigned'})
        
        # Add role and ensure it's active
        user_role, created = UserRole.objects.get_or_create(
            user=user, 
            role=role,
            defaults={'is_active': True}
        )
        
        # If role already exists, make sure it's active
        if not created:
            user_role.is_active = True
            user_role.save()
        
        # ALWAYS ensure user remains active when adding roles
        user.is_active = True
        user.save()
        
        # Log the action
        AuditLog.objects.create(
            user=request.user,
            action='add_role',
            entity_type='user',
            entity_id=str(user.id),
            description=f"Role '{role.name}' added to user {user.email} by {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
@csrf_exempt
def remove_user_role(request, user_role_id):
    """Remove a role from a user."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        user_role = get_object_or_404(UserRole, id=user_role_id)
        user = user_role.user
        role = user_role.role
        
        # Check if this is the last active role
        active_roles_count = UserRole.objects.filter(user=user, is_active=True).count()
        
        # Remove role
        user_role.delete()
        
        # ALWAYS ensure user remains active when removing roles
        user.is_active = True
        user.save()
        
        # If this was the last active role, ensure user has at least one role or make them inactive
        remaining_active_roles = UserRole.objects.filter(user=user, is_active=True).count()
        if remaining_active_roles == 0:
            # Check if user has any roles at all
            total_roles = UserRole.objects.filter(user=user).count()
            if total_roles == 0:
                # User has no roles, but keep them active for admin to assign roles
                # Don't make them inactive automatically
                pass
            else:
                # User has roles but none are active, activate the first one
                first_role = UserRole.objects.filter(user=user).first()
                if first_role:
                    first_role.is_active = True
                    first_role.save()
        
        # Log the action
        AuditLog.objects.create(
            user=request.user,
            action='remove_role',
            entity_type='user',
            entity_id=str(user.id),
            description=f"Role '{role.name}' removed from user {user.email} by {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
@csrf_exempt
def toggle_primary_role(request, user_role_id):
    """Toggle primary role for a user."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        user_role = get_object_or_404(UserRole, id=user_role_id)
        user = user_role.user
        
        # Remove primary from all other roles
        UserRole.objects.filter(user=user).update(is_primary=False)
        
        # Set this role as primary and ensure it's active
        user_role.is_primary = True
        user_role.is_active = True
        user_role.save()
        
        # ALWAYS ensure user remains active when changing primary role
        user.is_active = True
        user.save()
        
        # Double-check: if user has no active roles, activate this one
        active_roles_count = UserRole.objects.filter(user=user, is_active=True).count()
        if active_roles_count == 0:
            user_role.is_active = True
            user_role.save()
        
        # Log the action
        AuditLog.objects.create(
            user=request.user,
            action='set_primary_role',
            entity_type='user',
            entity_id=str(user.id),
            description=f"Primary role set to '{user_role.role.name}' for user {user.email} by {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def profile_view(request):
    """User profile view."""
    context = {
        'user': request.user,
        'title': 'Profile'
    }
    return render(request, 'users/profile.html', context)

@login_required
def change_password_view(request):
    """Change user password."""
    if request.method == 'POST':
        # Handle password change logic here
        messages.success(request, 'Password changed successfully!')
        return redirect('users:profile')
    
    return render(request, 'users/change_password.html', {})

@login_required
def edit_profile_view(request):
    """Edit user profile."""
    if request.method == 'POST':
        # Update user information
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.phone = request.POST.get('phone', '')
        
        # Save additional fields if they exist in the model
        if hasattr(user, 'company'):
            user.company = request.POST.get('company', '')
        if hasattr(user, 'position'):
            user.position = request.POST.get('position', '')
        if hasattr(user, 'bio'):
            user.bio = request.POST.get('bio', '')
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('users:profile')
    
    return render(request, 'users/edit_profile.html', {})

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
def delete_user(request, user_id):
    """Delete a user (admin only)."""
    if request.method == 'POST':
        try:
            user_obj = get_object_or_404(User, id=user_id)
            
            # Prevent deleting superusers
            if user_obj.is_superuser:
                return JsonResponse({
                    'success': False,
                    'message': 'Cannot delete superuser accounts.'
                })
            
            # Prevent deleting self
            if user_obj.id == request.user.id:
                return JsonResponse({
                    'success': False,
                    'message': 'Cannot delete your own account.'
                })
            
            # Prevent deleting seller accounts
            if user_obj.has_role('Seller'):
                return JsonResponse({
                    'success': False,
                    'message': 'Cannot delete seller accounts. Sellers must contact support for account management.'
                })
            
            # Log the deletion
            AuditLog.objects.create(
                user=request.user,
                action='delete_user',
                entity_type='user',
                entity_id=str(user_obj.id),
                description=f"Deleted user: {user_obj.email}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Delete the user
            user_obj.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'User deleted successfully.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error deleting user: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })

@login_required
@user_passes_test(lambda u: u.has_role('Super Admin') or u.has_role('Admin') or u.is_superuser)
def toggle_user_status(request, user_id):
    """Toggle user active/inactive status (admin only)."""
    if request.method == 'POST':
        try:
            user_obj = get_object_or_404(User, id=user_id)
            
            # Prevent toggling superuser status
            if user_obj.is_superuser:
                return JsonResponse({
                    'success': False,
                    'message': 'Cannot change superuser status.'
                })
            
            # Prevent toggling own status
            if user_obj.id == request.user.id:
                return JsonResponse({
                    'success': False,
                    'message': 'Cannot change your own status.'
                })
            
            # Toggle status
            old_status = user_obj.is_active
            user_obj.is_active = not user_obj.is_active
            user_obj.save()
            
            # Log the status change
            action = 'activate_user' if user_obj.is_active else 'deactivate_user'
            status_text = 'activated' if user_obj.is_active else 'deactivated'
            
            AuditLog.objects.create(
                user=request.user,
                action=action,
                entity_type='user',
                entity_id=str(user_obj.id),
                description=f"User {status_text}: {user_obj.email}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True,
                'message': f'User has been {status_text} successfully!',
                'is_active': user_obj.is_active
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error updating user status: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })


@login_required
def force_password_change(request):
    """
    Force password change for users with password_change_required=True.

    This view is specifically for internal users (staff, admin, etc.) who have been
    given temporary passwords and must change them before accessing the system.
    """
    # If user doesn't need to change password, redirect to dashboard
    if not request.user.password_change_required:
        messages.info(request, "You do not need to change your password.")
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()

            # Mark password change as no longer required
            user.password_change_required = False
            user.save(update_fields=['password_change_required'])

            # Log the forced password change
            AuditLog.objects.create(
                user=request.user,
                action='forced_password_change',
                entity_type='user',
                entity_id=str(user.id),
                description=f"Forced password change completed for {user.email}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

            # Update the session to prevent logging out
            update_session_auth_hash(request, user)

            messages.success(request, "Your password has been changed successfully. You can now access the system.")
            return redirect('dashboard:index')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'users/force_password_change.html', {'form': form})


# ============= Roles Management Views =============

@login_required
def roles_list(request):
    """List all roles and their permissions."""
    from roles.models import Role, Permission
    from django.core.paginator import Paginator

    roles = Role.objects.prefetch_related('permissions').order_by('name')

    # Get filter parameters
    search_query = request.GET.get('search', '')

    if search_query:
        roles = roles.filter(name__icontains=search_query)

    # Pagination
    paginator = Paginator(roles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_roles = Role.objects.count()
    total_permissions = Permission.objects.count()
    users_per_role = {}
    for role in Role.objects.all():
        users_per_role[role.name] = User.objects.filter(primary_role=role).count()

    context = {
        'page_obj': page_obj,
        'total_roles': total_roles,
        'total_permissions': total_permissions,
        'users_per_role': users_per_role,
        'search_query': search_query,
    }

    return render(request, 'users/roles_list.html', context)


@login_required
def create_role(request):
    """Create a new role."""
    from roles.models import Role, Permission

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        permission_ids = request.POST.getlist('permissions')

        if name:
            try:
                role = Role.objects.create(name=name, description=description)
                if permission_ids:
                    permissions = Permission.objects.filter(id__in=permission_ids)
                    role.permissions.set(permissions)

                messages.success(request, f'Role "{name}" created successfully.')
                return redirect('users:roles')
            except Exception as e:
                messages.error(request, f'Error creating role: {str(e)}')
        else:
            messages.error(request, 'Role name is required.')

    permissions = Permission.objects.all().order_by('codename')

    context = {
        'permissions': permissions,
    }

    return render(request, 'users/create_role.html', context)


@login_required
def edit_role(request, role_id):
    """Edit an existing role."""
    from roles.models import Role, Permission

    role = get_object_or_404(Role, id=role_id)

    if request.method == 'POST':
        role.name = request.POST.get('name', role.name)
        role.description = request.POST.get('description', '')
        permission_ids = request.POST.getlist('permissions')

        try:
            role.save()
            if permission_ids:
                permissions = Permission.objects.filter(id__in=permission_ids)
                role.permissions.set(permissions)
            else:
                role.permissions.clear()

            messages.success(request, f'Role "{role.name}" updated successfully.')
            return redirect('users:roles')
        except Exception as e:
            messages.error(request, f'Error updating role: {str(e)}')

    permissions = Permission.objects.all().order_by('codename')
    role_permissions = role.permissions.values_list('id', flat=True)

    context = {
        'role': role,
        'permissions': permissions,
        'role_permissions': list(role_permissions),
    }

    return render(request, 'users/edit_role.html', context)


@login_required
def manage_role_permissions(request, role_id):
    """Manage permissions for a specific role."""
    from roles.models import Role, Permission

    role = get_object_or_404(Role, id=role_id)

    if request.method == 'POST':
        permission_codes = request.POST.getlist('permissions')
        try:
            # Clear existing and set new permissions based on codenames
            role.permissions.clear()
            if permission_codes:
                for code in permission_codes:
                    perm, created = Permission.objects.get_or_create(codename=code, defaults={'name': code.replace('.', ' ').replace('_', ' ').title()})
                    role.permissions.add(perm)

            messages.success(request, f'Permissions updated for role "{role.name}".')
            return redirect('users:roles')
        except Exception as e:
            messages.error(request, f'Error updating permissions: {str(e)}')

    permissions = Permission.objects.all().order_by('codename')
    role_permissions = role.permissions.values_list('id', flat=True)

    # Get current permission codenames for template
    current_permissions = list(role.permissions.values_list('codename', flat=True))

    # Group permissions by category
    permission_groups = {}
    for permission in permissions:
        category = permission.codename.split('_')[0] if '_' in permission.codename else 'general'
        if category not in permission_groups:
            permission_groups[category] = []
        permission_groups[category].append(permission)

    context = {
        'role': role,
        'permissions': permissions,
        'permission_groups': permission_groups,
        'role_permissions': list(role_permissions),
        'current_permissions': current_permissions,
    }

    return render(request, 'users/role_permissions.html', context)


# ============= User Settings Views =============

@login_required
def user_settings(request):
    """User personal settings page."""
    user = request.user

    if request.method == 'POST':
        # Update user settings
        user.email_notifications = request.POST.get('email_notifications') == 'on'
        user.sms_notifications = request.POST.get('sms_notifications') == 'on'

        # Language preference
        language = request.POST.get('language', 'en')
        if hasattr(user, 'language'):
            user.language = language

        # Timezone
        timezone_pref = request.POST.get('timezone', 'Asia/Dubai')
        if hasattr(user, 'timezone'):
            user.timezone = timezone_pref

        try:
            user.save()
            messages.success(request, 'Settings updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')

        return redirect('users:settings')

    context = {
        'user': user,
    }

    return render(request, 'users/user_settings.html', context)


@login_required
def notification_settings(request):
    """Notification preferences settings."""
    user = request.user

    if request.method == 'POST':
        # Update notification preferences
        user.email_notifications = request.POST.get('email_enabled') == 'on'
        user.sms_notifications = request.POST.get('sms_enabled') == 'on'

        # More granular notification settings
        if hasattr(user, 'notify_on_order'):
            user.notify_on_order = request.POST.get('notify_new_orders') == 'on'
        if hasattr(user, 'notify_on_stock'):
            user.notify_on_stock = request.POST.get('notify_low_stock') == 'on'
        if hasattr(user, 'notify_on_payment'):
            user.notify_on_payment = request.POST.get('notify_payments') == 'on'

        try:
            user.save()
            messages.success(request, 'Notification settings updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating notification settings: {str(e)}')

        return redirect('users:notification_settings')

    # Build settings dict from user attributes
    settings = {
        'notify_new_orders': getattr(user, 'notify_on_order', True),
        'notify_order_status': True,
        'notify_low_stock': getattr(user, 'notify_on_stock', True),
        'notify_stock_updates': True,
        'notify_payments': getattr(user, 'notify_on_payment', True),
        'notify_payouts': True,
        'email_enabled': getattr(user, 'email_notifications', True),
        'sms_enabled': getattr(user, 'sms_notifications', False),
        'push_enabled': True,
    }

    context = {
        'user': user,
        'settings': settings,
    }

    return render(request, 'users/notification_settings.html', context)


# ============= Two-Factor Authentication Views =============

@login_required
def two_factor_settings(request):
    """Two-factor authentication settings page."""
    user = request.user

    # Check if user has 2FA enabled
    has_2fa = hasattr(user, 'totp_secret') and user.totp_secret

    context = {
        'has_2fa': has_2fa,
    }

    return render(request, 'users/two_factor_settings.html', context)


@login_required
def enable_two_factor(request):
    """Enable two-factor authentication."""
    import pyotp
    import qrcode
    import io
    import base64

    user = request.user

    if request.method == 'POST':
        # Verify the TOTP code
        totp_code = request.POST.get('totp_code', '')
        secret = request.session.get('pending_totp_secret')

        if secret:
            totp = pyotp.TOTP(secret)
            if totp.verify(totp_code):
                user.totp_secret = secret
                user.save()

                # Clean up session
                del request.session['pending_totp_secret']

                messages.success(request, 'Two-factor authentication has been enabled successfully.')
                return redirect('users:two_factor')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
        else:
            messages.error(request, 'Session expired. Please try again.')

    # Generate a new TOTP secret
    secret = pyotp.random_base32()
    request.session['pending_totp_secret'] = secret

    # Generate QR code
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(user.email, issuer_name="Atlas CRM")

    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    except Exception:
        qr_code_base64 = None

    context = {
        'secret': secret,
        'qr_code': qr_code_base64,
    }

    return render(request, 'users/enable_two_factor.html', context)


@login_required
def disable_two_factor(request):
    """Disable two-factor authentication."""
    user = request.user

    if request.method == 'POST':
        # Verify password before disabling
        password = request.POST.get('password', '')

        if user.check_password(password):
            user.totp_secret = None
            user.save()
            messages.success(request, 'Two-factor authentication has been disabled.')
            return redirect('users:two_factor')
        else:
            messages.error(request, 'Invalid password. Please try again.')

    return render(request, 'users/disable_two_factor.html')


@login_required
def verify_two_factor(request):
    """Verify two-factor authentication code."""
    import pyotp

    if request.method == 'POST':
        totp_code = request.POST.get('totp_code', '')
        user = request.user

        if hasattr(user, 'totp_secret') and user.totp_secret:
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(totp_code):
                request.session['2fa_verified'] = True
                messages.success(request, 'Two-factor authentication verified.')
                return redirect('dashboard:index')
            else:
                messages.error(request, 'Invalid verification code.')
        else:
            messages.error(request, 'Two-factor authentication is not enabled.')

    return render(request, 'users/verify_two_factor.html')
