"""
Create demo users with the exact credentials displayed on the login page.
These users are for demonstration purposes only.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from roles.models import Role, UserRole

User = get_user_model()


class Command(BaseCommand):
    help = 'Create demo users matching the credentials shown on the login page'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Update existing users with the demo passwords',
        )

    def handle(self, *args, **options):
        self.stdout.write('Creating demo users for Atlas CRM...\n')
        force_update = options.get('force', False)

        # Demo users matching the login page credentials
        demo_users = [
            {
                'email': 'superadmin@atlas.com',
                'password': 'admin123',
                'full_name': 'Super Admin',
                'role': 'Super Admin',
                'is_superuser': True,
                'is_staff': True,
            },
            {
                'email': 'admin@atlas.com',
                'password': 'admin123',
                'full_name': 'Admin User',
                'role': 'Admin',
                'is_superuser': False,
                'is_staff': True,
            },
            {
                'email': 'seller@atlas.com',
                'password': 'seller123',
                'full_name': 'Demo Seller',
                'role': 'Seller',
                'is_superuser': False,
                'is_staff': False,
            },
            {
                'email': 'callcenter@atlas.com',
                'password': 'callcenter123',
                'full_name': 'Call Center Agent',
                'role': 'Call Center Agent',
                'is_superuser': False,
                'is_staff': False,
            },
            {
                'email': 'manager@atlas.com',
                'password': 'manager123',
                'full_name': 'Manager User',
                'role': 'Call Center Manager',
                'is_superuser': False,
                'is_staff': False,
            },
            {
                'email': 'stockkeeper@atlas.com',
                'password': 'stock123',
                'full_name': 'Stock Keeper',
                'role': 'Stock Keeper',
                'is_superuser': False,
                'is_staff': False,
            },
            {
                'email': 'packaging@atlas.com',
                'password': 'package123',
                'full_name': 'Packaging Agent',
                'role': 'Packaging Agent',
                'is_superuser': False,
                'is_staff': False,
            },
            {
                'email': 'delivery@atlas.com',
                'password': 'delivery123',
                'full_name': 'Delivery Agent',
                'role': 'Delivery Agent',
                'is_superuser': False,
                'is_staff': False,
            },
        ]

        created_count = 0
        updated_count = 0

        for user_data in demo_users:
            email = user_data['email']

            # Check if user exists
            user = User.objects.filter(email=email).first()

            if user:
                if force_update:
                    # Update existing user
                    user.set_password(user_data['password'])
                    user.full_name = user_data['full_name']
                    user.is_active = True
                    user.is_superuser = user_data['is_superuser']
                    user.is_staff = user_data['is_staff']
                    user.approval_status = 'approved'
                    user.email_verified = True
                    user.save()
                    updated_count += 1
                    self.stdout.write(f'  ✓ Updated: {email}')
                else:
                    self.stdout.write(f'  - Exists: {email} (use --force to update)')
            else:
                # Create new user
                user = User.objects.create_user(
                    email=email,
                    password=user_data['password'],
                    full_name=user_data['full_name'],
                    is_active=True,
                    is_superuser=user_data['is_superuser'],
                    is_staff=user_data['is_staff'],
                    approval_status='approved',
                    email_verified=True,
                )
                created_count += 1
                self.stdout.write(f'  ✓ Created: {email}')

            # Ensure role is assigned
            role_name = user_data['role']
            role = Role.objects.filter(name=role_name).first()

            if not role:
                # Create role if it doesn't exist
                role = Role.objects.create(
                    name=role_name,
                    description=f'{role_name} role',
                    is_active=True,
                )
                self.stdout.write(f'    Created role: {role_name}')

            # Assign role to user
            user_role, ur_created = UserRole.objects.get_or_create(
                user=user,
                role=role,
                defaults={
                    'is_primary': True,
                    'is_active': True,
                }
            )

            if not ur_created:
                user_role.is_primary = True
                user_role.is_active = True
                user_role.save()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done! Created: {created_count}, Updated: {updated_count}'
        ))
        self.stdout.write('')
        self.stdout.write('Demo Credentials:')
        self.stdout.write('-' * 50)
        for user_data in demo_users:
            self.stdout.write(f"  {user_data['role']:20} {user_data['email']:30} {user_data['password']}")
