import os
import django
import sys

# Setup Django environment
sys.path.append('d:/cos-backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from events.models import EventRegistration, EventAttendance

def fix_orphans():
    print("Checking for orphan registrations...")
    # Find registrations that have no related attendance
    orphans = EventRegistration.objects.filter(attendance__isnull=True)
    count = orphans.count()

    if count == 0:
        print("No orphan registrations found. Data is healthy.")
        return

    print(f"Found {count} orphan registrations. Fixing...")

    fixed = 0
    for reg in orphans:
        try:
            EventAttendance.objects.create(registration=reg)
            print(f"Created attendance for Registration ID {reg.id} (User: {reg.user.username}, Event: {reg.event.title})")
            fixed += 1
        except Exception as e:
            print(f"Failed to fix Registration ID {reg.id}: {e}")

    print(f"Fixed {fixed}/{count} orphans.")

if __name__ == "__main__":
    fix_orphans()
