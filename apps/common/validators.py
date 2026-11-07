from rest_framework import serializers
from rest_framework.validators import UniqueValidator


def unique_iexact(model, message):
    """Validador de unicidad sin distinguir mayúsculas/minúsculas."""
    return UniqueValidator(
        queryset=model.objects.all(),
        lookup='iexact',
        message=message,
    )


def unique_char_field(model, message, max_length=100):
    """Campo de texto único (iexact). Reemplaza a tu _unique_name."""
    return serializers.CharField(
        max_length=max_length,
        validators=[unique_iexact(model, message)],
    )


def ensure_unique(model, field, value, message, instance=None):
    """Para usar dentro de validate_<campo>, excluyendo el registro que se edita."""
    qs = model.objects.filter(**{field: value})
    if instance:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError(message)