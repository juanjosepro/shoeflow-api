from rest_framework import serializers
from .models import Team, Worker
from django.contrib.auth.hashers import make_password

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'

class WorkerSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)
    team_id = serializers.PrimaryKeyRelatedField(
        source="team",
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = Worker
        fields = [
            "id",
            "team",
            "team_id",
            "names",
            "dni",
            "phone",
            "address",
            "email",
            "password",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        if password:
            validated_data["password"] = make_password(password)
        else:
            validated_data["password"] = ""
        return super().create(validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        if password:  # solo si mandaron una contraseña nueva y no vacía
            instance.password = make_password(password)
        # si no mandaron password o vino vacía, no tocamos el valor existente
        return super().update(instance, validated_data)