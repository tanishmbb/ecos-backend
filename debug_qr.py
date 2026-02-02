import requests
import random
import string

BASE_URL = "http://localhost:8000/api"

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

username = f"qr_debug_{random_string()}"
email = f"{username}@example.com"
password = "TestPassword123!"

s = requests.Session()

# 1. Signup
print(f"Registering user: {username}")
resp = s.post(f"{BASE_URL}/auth/signup/", json={
    "username": username,
    "email": email,
    "password": password,
    "role": "student"
})
if resp.status_code != 201:
    print(f"Signup failed: {resp.status_code} {resp.text}")
    exit(1)

# 2. Login
resp = s.post(f"{BASE_URL}/auth/login/", json={
    "email": email,
    "password": password
})
access_token = resp.json()['access']
headers = {"Authorization": f"Bearer {access_token}"}

# 3. Find event
resp = s.get(f"{BASE_URL}/events/", headers=headers)
events = resp.json()
if not events:
    print("No events found.")
    exit(1)
event_id = events[0]['id']

# 4. Register
print(f"Registering for event {event_id}...")
resp = s.post(f"{BASE_URL}/events/{event_id}/register/", headers=headers)
print(f"Registration status: {resp.status_code}")

# 5. Check My Registrations
print("Fetching My Upcoming Events...")
resp = s.get(f"{BASE_URL}/events/me/upcoming/", headers=headers)
if resp.status_code != 200:
    print(f"Failed to fetch my events: {resp.status_code} {resp.text}")
    exit(1)

data = resp.json()
print("My Registrations Response:")
import json
print(json.dumps(data, indent=2))

# Verify QR
found = False
for event in data:
    if event['id'] == event_id:
        found = True
        att = event.get('attendance')
        print(f"Attendance Data for event {event_id}: {att}")
        if att and att.get('qr_code'):
            print("SUCCESS: QR Code is present.")
        else:
            print("FAILURE: QR Code is missing.")

if not found:
    print("FAILURE: Registered event not found in upcoming list.")
