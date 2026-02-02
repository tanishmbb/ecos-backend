from django.contrib.auth import get_user_model
User = get_user_model()
try:
    u = User.objects.get(username='test_browser_4821')
    u.role = 'organizer'
    u.save()
    print(f"SUCCESS_PROMOTION: {u.username}")
except Exception as e:
    print(f"ERROR_PROMOTION: {e}")
