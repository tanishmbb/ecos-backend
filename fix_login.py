import os
import sys
import django

# Add current directory to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User

email = "tan@gmail.com"
password = "tanish.sneha@2005"

try:
    # Try to find by email or username
    user = User.objects.filter(email=email).first() or User.objects.filter(username=email).first()

    if user:
        print(f"User found: {user.username} ({user.email})")
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.role = 'admin'
        user.save()
        print("Password updated and user promoted to admin.")
    else:
        print("User not found. Creating new superuser...")
        # Use email as username if not specified otherwise
        user = User.objects.create_superuser(username=email, email=email, password=password)
        user.role = 'admin'
        user.save()
        print(f"Superuser created: {user.username}")

except Exception as e:
    print(f"Error: {e}")
