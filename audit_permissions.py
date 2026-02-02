import os
import django
from django.conf import settings

# Setup Django standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Community, CommunityMembership
from projects.models import Project
from events.models import Event
from rest_framework.test import APIRequestFactory, force_authenticate
from projects.views import ProjectViewSet
from events.views.events import EventViewSet

User = get_user_model()
factory = APIRequestFactory()

def run_audit():
    print("🛡️  Starting Permission & Boundary Audit...\n")

    # 1. SETUP
    print("1️⃣  Setting up test environment...")
    user_a = User.objects.create_user(username='audit_user_a', email='a@test.com', password='password')
    user_b = User.objects.create_user(username='audit_user_b', email='b@test.com', password='password')

    comm_a = Community.objects.create(name='Audit Community A', slug='audit-a', owner=user_a)
    comm_b = Community.objects.create(name='Audit Community B', slug='audit-b', owner=user_b)

    # User A is member of A, NOT B
    CommunityMembership.objects.create(community=comm_a, user=user_a, role='member')

    # Project in B
    project_b = Project.objects.create(community=comm_b, owner=user_b, title='Project B', description='Desc')

    print("   Done.\n")

    # 2. TEST: User A creating project in Community B (Should FAIL)
    print("2️⃣  Test: Cross-Community Creation (User A -> Community B)")
    view = ProjectViewSet.as_view({'post': 'create'})
    req = factory.post('/api/ncos/projects/', {
        'title': 'Intruder Project',
        'description': 'Should fail',
        'community': comm_b.id
    })
    force_authenticate(req, user=user_a)

    try:
        resp = view(req)
        if resp.status_code in [403, 400]: # 400 if validation catches it, 403 if permission
            print(f"   ✅ Blocked correctly (Status: {resp.status_code})")
            if resp.status_code == 400 and 'community' in resp.data:
                 print(f"      Reason: {resp.data['community'][0]}")
        else:
            print(f"   ❌ FAILED: Start {resp.status_code} - Allowed incorrectly!")
    except Exception as e:
        print(f"   ❌ FAILED: Exception {e}")

    # 3. TEST: User A listing projects (Should NOT see Project B)
    print("\n3️⃣  Test: Cross-Community Read (User A listing)")
    view_list = ProjectViewSet.as_view({'get': 'list'})
    req_list = factory.get('/api/ncos/projects/')
    force_authenticate(req_list, user=user_a)

    resp_list = view_list(req_list)
    data = resp_list.data
    # Filtered by what? The view likely returns user's stuff or checks params?
    # ProjectViewSet usually needs `?community_slug=` or filters by membership.
    # Let's see if it leaks EVERYTHING if no filter provided.

    found_b = any(p['id'] == project_b.id for p in data)
    if found_b:
        print("   ❌ FAILED: User A can see Project B in global list")
    else:
        print("   ✅ Verified: User A cannot see Project B (or list is empty/filtered)")

    # 4. TEST: User A deleting Project B (Should FAIL)
    print("\n4️⃣  Test: Unauthorized Deletion (User A -> Project B)")
    view_detail = ProjectViewSet.as_view({'delete': 'destroy'})
    req_del = factory.delete(f'/api/ncos/projects/{project_b.id}/')
    force_authenticate(req_del, user=user_a)

    try:
        resp_del = view_detail(req_del, pk=project_b.id)
        if resp_del.status_code in [403, 404]:
            print(f"   ✅ Blocked correctly (Status: {resp_del.status_code})")
        else:
            print(f"   ❌ FAILED: Status {resp_del.status_code} - Allowed delete!")
    except Exception as e:
        print(f"   ⚠️  Exception: {e}")

    # CLEANUP
    print("\n🧹  Cleaning up...")
    user_a.delete()
    user_b.delete()
    comm_a.delete()
    comm_b.delete()

if __name__ == '__main__':
    run_audit()
