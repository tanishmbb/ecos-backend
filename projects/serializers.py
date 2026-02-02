from rest_framework import serializers
from .models import Project

class ProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id',
            'community',
            'community_name',
            'owner',
            'owner_name',
            'title',
            'description',
            'status',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Auto-assign owner from request context
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)
