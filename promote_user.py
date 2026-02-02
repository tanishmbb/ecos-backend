import os
import django
import sys

# Setup Django environment
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangosettings.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = 'test_browser_4821'

try:
    u = User.objects.get(username=username)
    u.role = 'organizer'
    u.save()
    print(f"SUCCESS: Promoted {u.username} to organizer")
except User.DoesNotExist:
    print(f"ERROR: User {username} not found")
except Exception as e:
    print(f"ERROR: {e}")
