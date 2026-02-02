from rest_framework import serializers
from .models import Certificate



class CertificateSerializer(serializers.ModelSerializer):
    event = serializers.CharField(
        source="registration.event.title",
        read_only=True
    )

    event_id = serializers.IntegerField(
        source="registration.event.id",
        read_only=True
    )

    user = serializers.CharField(
        source="registration.user.username",
        read_only=True
    )

    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "id",
            "event",
            "event_id",     # ✅ REQUIRED
            "user",
            "issued_at",
            "cert_token",   # ✅ REQUIRED
            "pdf_url",
        ]
        read_only_fields = fields

    def get_pdf_url(self, obj):
        request = self.context.get("request")
        if obj.pdf and request:
            return request.build_absolute_uri(obj.pdf.url)
        if obj.pdf:
            return obj.pdf.url
        return None
