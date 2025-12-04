from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

class UserManager(BaseUserManager):
    """Custom user manager for the CRM system."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        
        # Remove username from extra_fields if present (we use email instead)
        extra_fields.pop('username', None)
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        
        # Check if the current user is admin/superuser
        current_user = getattr(self, '_current_user', None)
        is_admin_creating = current_user and (current_user.has_role('Admin') or current_user.is_superuser)
        
        # Only set approval status for new users (not existing ones being updated)
        # Check if this is a new user by looking for pk
        if not user.pk:
            # Check if is_active and approval_status were explicitly provided
            is_active_provided = 'is_active' in extra_fields
            approval_status_provided = 'approval_status' in extra_fields

            # Set new users as inactive and pending approval (unless they're superuser, created by admin, or explicitly set)
            if not extra_fields.get('is_superuser', False) and not is_admin_creating:
                # Only override if not explicitly provided (e.g., in tests)
                if not is_active_provided:
                    user.is_active = False
                if not approval_status_provided:
                    user.approval_status = 'pending'
                user.email_verified = False  # Regular users need email verification
            else:
                # Superusers and admin-created users are automatically active and approved
                if not is_active_provided:
                    user.is_active = True
                if not approval_status_provided:
                    user.approval_status = 'approved'
                user.email_verified = True  # Admin-created users don't need email verification
                if is_admin_creating:
                    user.approved_by = current_user
                    user.approved_at = timezone.now()
        
        user.save(using=self._db)
        
        # Send pending approval email only for new regular users
        if not user.pk and not extra_fields.get('is_superuser', False) and not is_admin_creating:
            try:
                user.send_pending_approval_email()
            except Exception as e:
                print(f"Error sending email: {e}")
        
        # Automatically assign Seller role to new users (but they won't be active until approved)
        # Only assign Seller role to non-superusers (only one role)
        if not user.pk and not extra_fields.get('is_superuser', False):
            self._assign_default_role(user, 'Seller')
        
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('approval_status', 'approved')  # Superusers are automatically approved
        extra_fields.setdefault('email_verified', True)  # Superusers don't need email verification
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        user = self.create_user(email, password, **extra_fields)
        
        # Automatically assign Super Admin role to superusers (not Admin or Seller)
        self._assign_default_role(user, 'Super Admin')
        
        return user
    
    def _assign_default_role(self, user, role_name):
        """Assign a default role to a user"""
        try:
            from roles.models import Role, UserRole
            
            # Get or create the role
            if role_name == 'Super Admin':
                role, created = Role.objects.get_or_create(
                    name='Super Admin',
                    defaults={
                        'role_type': 'admin',
                        'description': 'Full system access with all permissions',
                        'is_active': True,
                        'is_default': False,
                        'is_protected': True,
                    }
                )
            else:
                # Get the role (for other roles like Admin, Seller)
                role = Role.objects.filter(name=role_name, is_active=True).first()
            
            if role:
                # Check if user already has this role
                if not UserRole.objects.filter(user=user, role=role).exists():
                    # Assign the role as primary
                    UserRole.objects.create(
                        user=user,
                        role=role,
                        is_primary=True,
                        is_active=True
                    )
                    print(f"Assigned {role_name} role to {user.email}")
                else:
                    # Update existing role to be primary if it's not
                    existing_role = UserRole.objects.filter(user=user, role=role).first()
                    if existing_role and not existing_role.is_primary:
                        existing_role.is_primary = True
                        existing_role.is_active = True
                        existing_role.save()
                        print(f"Updated {role_name} role to primary for {user.email}")
        except Exception as e:
            print(f"Error assigning role {role_name} to {user.email}: {e}")

class User(AbstractUser, PermissionsMixin):
    """Custom user model for the CRM system with role-based access control."""
    
    # Override username with email as primary identifier
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # Personal information
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True)
    full_name = models.CharField(_('full name'), max_length=150)
    phone_number = models.CharField(_('phone number'), max_length=20)
    
    # ID verification
    id_front_image = models.ImageField(_('ID front image'), upload_to='id_images/', null=True, blank=True)
    id_back_image = models.ImageField(_('ID back image'), upload_to='id_images/', null=True, blank=True)
    
    # Role and permissions - now handled through UserRole model
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    
    # Tracking
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    last_login = models.DateTimeField(_('last login'), blank=True, null=True)
    
    # Profile
    profile_image = models.ImageField(_('profile image'), upload_to='profile_images/', null=True, blank=True)
    
    # Additional fields for business users
    company_name = models.CharField(_('company name'), max_length=150, blank=True, null=True)
    country = models.CharField(_('country'), max_length=100, blank=True, null=True)
    expected_daily_orders = models.PositiveIntegerField(_('expected daily orders'), default=0)
    
    # E-commerce store details
    store_name = models.CharField(_('store name'), max_length=150, blank=True, null=True)
    store_link = models.URLField(_('store link'), blank=True, null=True)
    store_type = models.CharField(_('store type'), max_length=50, blank=True, null=True, 
                                choices=[
                                    ('general', 'General'),
                                    ('specialized', 'Specialized')
                                ])
    store_specialization = models.CharField(_('store specialization'), max_length=100, blank=True, null=True)
    marketing_platforms = models.JSONField(_('marketing platforms'), default=list, blank=True)
    
    # Bank details
    bank_name = models.CharField(_('bank name'), max_length=100, blank=True, null=True)
    account_holder_name = models.CharField(_('account holder name'), max_length=150, blank=True, null=True)
    account_number = models.CharField(_('account number (IBAN)'), max_length=50, blank=True, null=True)
    iban_confirmation = models.CharField(_('IBAN confirmation'), max_length=50, blank=True, null=True)
    
    # System fields
    user_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Approval system
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    approval_status = models.CharField(
        _('approval status'), 
        max_length=20, 
        choices=APPROVAL_STATUS_CHOICES, 
        default='pending'
    )
    rejection_reason = models.TextField(_('rejection reason'), blank=True, null=True)
    approved_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_users',
        verbose_name=_('approved by')
    )
    approved_at = models.DateTimeField(_('approved at'), null=True, blank=True)
    
    # Email verification system
    email_verified = models.BooleanField(_('email verified'), default=False)
    verification_code = models.CharField(_('verification code'), max_length=6, blank=True, null=True)
    verification_code_sent_at = models.DateTimeField(_('verification code sent at'), null=True, blank=True)
    verification_code_expires_at = models.DateTimeField(_('verification code expires at'), null=True, blank=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone_number']
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return self.full_name
    
    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.email
    
    def get_initials(self):
        """Get user initials for avatar display"""
        if self.full_name:
            names = self.full_name.split()
            if len(names) >= 2:
                return f"{names[0][0]}{names[-1][0]}".upper()
            return names[0][0].upper()
        return self.email[0].upper()
    
    def generate_verification_code(self):
        """Generate a 6-digit verification code"""
        import random
        from django.utils import timezone
        from datetime import timedelta
        
        code = str(random.randint(100000, 999999))
        self.verification_code = code
        self.verification_code_sent_at = timezone.now()
        self.verification_code_expires_at = timezone.now() + timedelta(minutes=15)  # Code expires in 15 minutes
        self.save()
        return code
    
    def verify_code(self, code):
        """Verify the provided code"""
        from django.utils import timezone
        
        if not self.verification_code or not code:
            return False
        
        if self.verification_code != code:
            return False
        
        if self.verification_code_expires_at and timezone.now() > self.verification_code_expires_at:
            return False
        
        # Code is valid, mark email as verified
        self.email_verified = True
        self.verification_code = None  # Clear the code after successful verification
        self.verification_code_expires_at = None
        self.save()
        return True
    
    @property
    def primary_role(self):
        """Get the user's primary role"""
        try:
            user_role = self.user_roles.filter(is_primary=True, is_active=True).first()
            return user_role.role if user_role else None
        except:
            return None
    
    def get_primary_role(self):
        """Get the user's primary role (legacy method)"""
        return self.primary_role
    
    def get_all_roles(self):
        """Get all active roles for the user"""
        return [user_role.role for user_role in self.user_roles.filter(is_active=True)]

    def get_roles(self):
        """Get all active roles for the user (returns QuerySet for compatibility)"""
        from roles.models import Role
        role_ids = self.user_roles.filter(is_active=True).values_list('role_id', flat=True)
        return Role.objects.filter(id__in=role_ids)

    def has_role(self, role_name):
        """Check if user has the specified role"""
        return self.user_roles.filter(role__name=role_name, is_active=True).exists()
    
    def has_permission(self, permission_codename, module=None):
        """Check if user has the specified permission"""
        from roles.models import Permission
        
        # Superusers have all permissions
        if self.is_superuser:
            return True
        
        # Check through user's roles
        for user_role in self.user_roles.filter(is_active=True):
            if user_role.role.role_permissions.filter(
                permission__codename=permission_codename,
                granted=True
            ).exists():
                if module is None or user_role.role.role_permissions.filter(
                    permission__codename=permission_codename,
                    permission__module=module,
                    granted=True
                ).exists():
                    return True
        return False
    
    def can_create_roles(self):
        """Check if user can create roles (only super admin)"""
        return self.has_role('Super Admin') or self.is_superuser
    
    @property
    def has_role_call_center_manager(self):
        """Check if user has Call Center Manager role"""
        return self.has_role('Call Center Manager')
    
    @property
    def has_role_call_center_agent(self):
        """Check if user has Call Center Agent role"""
        return self.has_role('Call Center Agent')
    
    @property
    def has_role_accountant(self):
        """Check if user has Accountant role"""
        return self.has_role('Accountant')
    
    @property
    def has_role_admin(self):
        """Check if user has Admin or Super Admin role"""
        return self.has_role('Admin') or self.has_role('Super Admin') or self.is_superuser
    
    @property
    def has_role_seller(self):
        """Check if user has Seller role"""
        return self.has_role('Seller')
    
    @property
    def has_role_super_admin(self):
        """Check if user has Super Admin role"""
        return self.has_role('Super Admin')
    
    @property
    def has_role_stock_keeper(self):
        """Check if user has Stock Keeper role"""
        return self.has_role('Stock Keeper')
    
    @property
    def has_role_packaging(self):
        """Check if user has Packaging Agent role"""
        return self.has_role('Packaging Agent')
    
    @property
    def has_role_delivery(self):
        """Check if user has Delivery Agent role"""
        return self.has_role('Delivery Agent')

    @property
    def has_role_delivery_manager(self):
        """Check if user has Delivery Manager role"""
        return self.has_role('Delivery Manager')
    
    def approve_user(self, approved_by_user):
        """Approve a user account"""
        from django.utils import timezone
        self.approval_status = 'approved'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.is_active = True
        self.save()
        
        # Send approval email
        self.send_approval_email()
    
    def reject_user(self, rejected_by_user, reason):
        """Reject a user account"""
        from django.utils import timezone
        self.approval_status = 'rejected'
        self.rejection_reason = reason
        self.approved_by = rejected_by_user
        self.approved_at = timezone.now()
        self.is_active = False
        self.save()
        
        # Send rejection email
        self.send_rejection_email(reason)
    
    def send_pending_approval_email(self):
        """Send email notification for pending approval"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = 'حسابك في انتظار الموافقة - Your Account is Pending Approval'
        message = f"""
        مرحباً {self.full_name}،
        
        شكراً لك على التسجيل في نظام Atlas Fulfillment. 
        حسابك حالياً في انتظار الموافقة من الإدارة.
        ستتم إشعارك عبر البريد الإلكتروني عند مراجعة طلبك.
        
        Hello {self.full_name},
        
        Thank you for registering with Atlas Fulfillment System.
        Your account is currently pending approval from administration.
        You will be notified via email once your request has been reviewed.
        
        Best regards,
        Atlas Fulfillment Team
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error sending pending approval email: {e}")
    
    def send_approval_email(self):
        """Send email notification for account approval"""
        try:
            from users.email_utils import send_approval_email
            # Use the email_utils function which has better HTML template
            send_approval_email(self, self.approved_by if hasattr(self, 'approved_by') and self.approved_by else None)
        except Exception as e:
            print(f"Error sending approval email: {e}")
            # Fallback to simple email if template fails
            from django.core.mail import send_mail
            from django.conf import settings
            
            subject = 'تمت الموافقة على حسابك - Your Account Has Been Approved'
            message = f"""
            مرحباً {self.full_name}،
            
            تمت الموافقة على حسابك في نظام Atlas Fulfillment!
            يمكنك الآن تسجيل الدخول والبدء في استخدام النظام.
            
            Hello {self.full_name},
            
            Your Atlas Fulfillment account has been approved!
            You can now log in and start using the system.
            
            Best regards,
            Atlas Fulfillment Team
            """
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [self.email],
                    fail_silently=False,
                )
            except Exception as e2:
                print(f"Error sending fallback approval email: {e2}")
    
    def send_rejection_email(self, reason):
        """Send email notification for account rejection"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = 'تم رفض حسابك - Your Account Has Been Rejected'
        message = f"""
        مرحباً {self.full_name}،
        
        للأسف، تم رفض طلب تسجيل حسابك في نظام Atlas Fulfillment.
        
        السبب: {reason}
        
        إذا كنت تعتقد أن هذا خطأ، يرجى التواصل معنا.
        
        Hello {self.full_name},
        
        Unfortunately, your Atlas Fulfillment account registration has been rejected.
        
        Reason: {reason}
        
        If you believe this is an error, please contact us.
        
        Best regards,
        Atlas Fulfillment Team
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error sending rejection email: {e}")

class UserPermission(models.Model):
    """Model to store custom permissions for users."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_permissions')
    permission_name = models.CharField(_('permission name'), max_length=100)
    description = models.TextField(_('description'), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'permission_name')
        verbose_name = _('user permission')
        verbose_name_plural = _('user permissions')
    
    def __str__(self):
        return f"{self.user.email} - {self.permission_name}"

class AuditLog(models.Model):
    """Model to track critical actions in the system."""
    
    ACTION_CHOICES = (
        ('create', _('Create')),
        ('update', _('Update')),
        ('delete', _('Delete')),
        ('view', _('View')),
        ('login', _('Login')),
        ('logout', _('Logout')),
        ('password_change', _('Password Change')),
        ('permission_change', _('Permission Change')),
        ('status_change', _('Status Change')),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(_('action'), max_length=30, choices=ACTION_CHOICES)
    entity_type = models.CharField(_('entity type'), max_length=100)
    entity_id = models.CharField(_('entity ID'), max_length=100)
    description = models.TextField(_('description'))
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('audit log')
        verbose_name_plural = _('audit logs')
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.action} - {self.entity_type}"


class User2FAProfile(models.Model):
    """Model to store 2FA settings for users."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='twofa_profile')
    is_enabled = models.BooleanField(_('2FA enabled'), default=False)
    backup_codes = models.JSONField(_('backup codes'), default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('2FA profile')
        verbose_name_plural = _('2FA profiles')
    
    def __str__(self):
        return f"{self.user.email} - 2FA Profile"
    
    def generate_backup_codes(self, count=10):
        """Generate backup codes for 2FA"""
        import secrets
        import string
        
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            codes.append(code)
        
        self.backup_codes = codes
        self.save()
        return codes
    
    def verify_backup_code(self, code):
        """Verify a backup code"""
        if code in self.backup_codes:
            # Remove used backup code
            self.backup_codes.remove(code)
            self.save()
            return True
        return False
    
    def has_backup_codes(self):
        """Check if user has backup codes"""
        return len(self.backup_codes) > 0


class LoginAttempt(models.Model):
    """Model to track login attempts for security purposes."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_attempts')
    ip_address = models.GenericIPAddressField(_('IP address'))
    user_agent = models.TextField(_('user agent'), blank=True)
    success = models.BooleanField(_('success'), default=False)
    failure_reason = models.CharField(_('failure reason'), max_length=200, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('login attempt')
        verbose_name_plural = _('login attempts')
        ordering = ['-timestamp']
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.user.email} - {status} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """Override save to ensure user remains active when they have roles."""
        # If user has active roles, ensure they remain active
        if hasattr(self, 'user_roles') and self.user_roles.filter(is_active=True).exists():
            self.is_active = True
        
        super().save(*args, **kwargs)