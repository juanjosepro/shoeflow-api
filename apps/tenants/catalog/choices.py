"""Opciones compartidas. Viven en catalog porque las usan Dozen (production)
y SpecialtyRate (payroll) y así ninguna depende de la otra."""
from django.db import models

class Material(models.TextChoices):
    LEATHER = "CUERO", "Cuero"
    GAMUSA = "GAMUSA", "Gamusa"
    SYNTHETIC = "SINTETICO", "Sintético"
    OTHER = "OTRO", "Otro"


class Color(models.TextChoices):
    WHITE = "WHITE", "Blanco"
    BLACK = "BLACK", "Negro"
    DARKGRAY = "DARKGRAY", "Plomo"
    TAN = "TAN", "Beige"
    SADDLEBROWN = "SADDLEBROWN", "Café"
    GOLDENROD = "GOLDENROD", "Dorado"
    DARKSLATEBLUE = "DARKSLATEBLUE", "Azul acero"
    OTHER = "OTHER", "Otro"


class PlantType(models.TextChoices):
    RUBBER = "GOMA", "Goma"
    PVC = "PVC", "PVC"
    TR = "TR", "TR"
    PU = "PU", "PU"
    EVA = "EVA", "EVA"
    CAUCHO = "CAUCHO", "Caucho"
    OTHER = "OTRO", "Otro"