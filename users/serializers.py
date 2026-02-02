from rest_framework import serializers
from .models import User
from events.models import EventRegistration, EventAttendance
from events.serializers import EventSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'role',
            'phone',
            'bio',
            'interests',
            'profile_picture',
            'verified',
            'is_onboarded',
            'points',
            'date_joined',
            # Profile Fields
            'intent',
            'availability',
            'domains',
            'skills',
            'institution',
            'degree',
        ]


class UpdateProfileSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['username', 'phone', 'bio', 'interests', 'profile_picture', 'is_onboarded', 'password']

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class RegistrationSummarySerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)

    class Meta:
        model = EventRegistration
        fields = ['id', 'event', 'registered_at', 'approved']


class AttendanceSummarySerializer(serializers.ModelSerializer):
    event = serializers.SerializerMethodField()

    class Meta:
        model = EventAttendance
        fields = ['id', 'event', 'check_in', 'check_out']

    def get_event(self, obj):
        return EventSerializer(obj.registration.event).data
