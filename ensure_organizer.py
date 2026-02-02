import os
import django
import sys

sys.path.append('d:/cos-backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from events.models import Event, EventRegistration, EventAttendance
from core.models import Community, CommunityMembership
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

def run():
    # 1. Ensure User 'tan' exists
    username = "tan"
    password = "password"
    email = "tan@example.com"

    user, created = User.objects.get_or_create(username=username, defaults={
        "email": email,
        "role": "organizer"
    })
    if created:
        user.set_password(password)
        user.save()
        print(f"Created user {username}")
    else:
        print(f"User {username} exists")

    # 2. Ensure Community exists
    comm, _ = Community.objects.get_or_create(
        slug="cos-community",
        defaults={
            "name": "COS Community",
            "is_active": True
        }
    )

    # 3. Ensure Membership
    CommunityMembership.objects.get_or_create(
        user=user,
        community=comm,
        defaults={
            "role": CommunityMembership.ROLE_OWNER,
            "is_active": True,
            "is_default": True
        }
    )
    print("Community membership ensured.")

    # 4. Ensure an Event exists
    event, _ = Event.objects.get_or_create(
        title="Test Organizer Event",
        community=comm,
        defaults={
            "organizer": user,
            "start_time": timezone.now() + timedelta(days=1),
            "end_time": timezone.now() + timedelta(days=1, hours=2),
            "status": Event.STATUS_APPROVED
        }
    )
    print(f"Event '{event.title}' (ID: {event.id}) ensured.")

    # 5. Ensure Registration
    reg, _ = EventRegistration.objects.get_or_create(user=user, event=event)
    EventAttendance.objects.get_or_create(registration=reg)
    print("Self-registration ensured.")

if __name__ == "__main__":
    run()
