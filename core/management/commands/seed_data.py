import random
import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import Community, CommunityMembership, FeedItem, FeedLike, FeedComment
from events.models import Event, EventRegistration, EventAttendance

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with sample community, events, and feed interactions"

    def handle(self, *args, **options):
        self.stdout.write("🌱 Seeding data...")

        # 1. Ensure Users
        admin, _ = User.objects.get_or_create(username="admin", defaults={"email": "admin@example.com", "role": "admin"})
        if not admin.check_password("admin"):
            admin.set_password("admin")
            admin.save()

        alice, _ = User.objects.get_or_create(username="alice", defaults={"email": "alice@example.com", "role": "student"})
        alice.set_password("password")
        alice.save()

        bob, _ = User.objects.get_or_create(username="bob", defaults={"email": "bob@example.com", "role": "student"})
        bob.set_password("password")
        bob.save()

        # 2. Create Community
        # Handle case where one field exists but not both to avoid get_or_create issues
        try:
            comm = Community.objects.get(slug="tech-innovators")
        except Community.DoesNotExist:
            try:
                comm = Community.objects.get(name="Tech Innovators")
            except Community.DoesNotExist:
                comm = Community.objects.create(
                    slug="tech-innovators",
                    name="Tech Innovators",
                    description="A community for forward-thinking tech enthusiasts building the future.",
                    primary_color="#8b5cf6", # Violet
                    created_by=admin,
                    is_active=True
                )
        self.stdout.write(f"Used Community: {comm.name}")

        # Memberships & Registrations
        for u, role in [(admin, "owner"), (alice, "organizer"), (bob, "member")]:
            CommunityMembership.objects.get_or_create(community=comm, user=u, defaults={"role": role, "is_active": True})

        # 3. Create Events
        # Images from Unsplash/Picsum
        events_data = [
            {
                "title": "AI Revolution Summit",
                "description": "Join us for a deep dive into Large Language Models and the future of generative AI. Keynote speakers from top tech firms.",
                "start_time": timezone.now() + timezone.timedelta(days=5),
                "end_time": timezone.now() + timezone.timedelta(days=5, hours=4),
                "banner": "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=800&q=80",
                "location": "Innovation Hub, Hall A"
            },
            {
                "title": "Hackathon: Build for Good",
                "description": "48-hour coding marathon to solve social issues. Prizes worth $5k!",
                "start_time": timezone.now() + timezone.timedelta(days=12),
                "end_time": timezone.now() + timezone.timedelta(days=14),
                "banner": "https://images.unsplash.com/photo-1504384308090-c54be38558bd?auto=format&fit=crop&w=800&q=80",
                "location": "Online"
            },
            {
                "title": "Tech Mixer Night",
                "description": "Networking event for local developers and designers. Free pizza!",
                "start_time": timezone.now() + timezone.timedelta(days=2),
                "end_time": timezone.now() + timezone.timedelta(days=2, hours=3),
                "banner": "https://images.unsplash.com/photo-1515187029135-18ee286d815b?auto=format&fit=crop&w=800&q=80",
                "location": "Downtown Cafe"
            },
            {
                "title": "Future of Web Development",
                "description": "Exploring new frameworks and the death of traditional DOM manipulation. Join us!",
                "start_time": timezone.now() + timezone.timedelta(days=20),
                "end_time": timezone.now() + timezone.timedelta(days=20, hours=2),
                "banner": "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?auto=format&fit=crop&w=800&q=80",
                "location": "Virtual"
            }
        ]

        for data in events_data:
            evt, created = Event.objects.get_or_create(
                title=data["title"],
                defaults={
                    "community": comm,
                    "organizer": admin,
                    "description": data["description"],
                    "start_time": data["start_time"],
                    "end_time": data["end_time"],
                    "capacity": 100,
                    "venue": data["location"],
                    "banner": data["banner"],
                    "status": "approved",
                    "is_public": True
                }
            )
            if created:
                self.stdout.write(f"Created Event: {evt.title}")
                # Signal might have created FeedItem, but let's ensure
                FeedItem.objects.get_or_create(type="event", event=evt)

            # Register admin, alice, bob for this event
            for u in [admin, alice, bob]:
                reg, _ = EventRegistration.objects.get_or_create(event=evt, user=u)
                EventAttendance.objects.get_or_create(registration=reg)

        # 4. Generate Interactions
        items = FeedItem.objects.all()
        users = [admin, alice, bob]
        comments = [
            "This looks amazing! Can't wait.",
            "Is there a student discount?",
            "Registered! See you there.",
            "Will this be recorded?",
            "Love the venue choice!"
        ]

        for item in items:
            # Random likes
            for u in users:
                if random.choice([True, False]):
                    FeedLike.objects.get_or_create(feed_item=item, user=u)

            # Random comments
            if random.choice([True, False]):
                u = random.choice(users)
                text = random.choice(comments)
                FeedComment.objects.create(feed_item=item, user=u, text=text)

        self.stdout.write("✅ Seeding Complete!")

        # 5. Add Community Images (Logos)
        self.stdout.write("🖼️  Populating Community Images...")
        communities = Community.objects.all()
        logos = [
            "https://images.unsplash.com/photo-1614680376593-902f74cf0d41?auto=format&fit=crop&w=300&q=80",
            "https://images.unsplash.com/photo-1611162617474-5b21e879e113?auto=format&fit=crop&w=300&q=80",
            "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=300&q=80",
            "https://images.unsplash.com/photo-1560179707-f14e90ef3623?auto=format&fit=crop&w=300&q=80",
            "https://images.unsplash.com/photo-1493612276216-ee3925520721?auto=format&fit=crop&w=300&q=80",
        ]

        for comm in communities:
            if not comm.logo:
                self.stdout.write(f"  Downloading logo for {comm.name}...")
                try:
                    url = random.choice(logos)
                    res = requests.get(url, timeout=10)
                    if res.status_code == 200:
                        comm.logo.save(f"{comm.slug}_logo.jpg", ContentFile(res.content), save=True)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Failed to set logo for {comm.name}: {e}"))
            else:
                self.stdout.write(f"  Logo already exists for {comm.name}")

