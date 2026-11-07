"""Portal del trabajador: consulta de solo lectura con su DNI (el PIN está listo pero apagado).

Es un acceso SEPARADO del de los administradores:
  - Token propio, firmado y con vencimiento (cabecera `Authorization: Worker <token>`).
  - El token de administrador (`Token ...`) no sirve aquí, y el de trabajador no sirve en el resto del API.
  - Solo GET, y siempre filtrado al trabajador del token: nunca ve datos de otro.
"""
from datetime import timedelta

from django.contrib.auth.hashers import make_password  # + check_password si activas el PIN
from django.core import signing
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from django.contrib.auth.hashers import check_password   # ← PIN
from django.core.cache import cache                      # ← PIN (bloqueo por intentos)
from apps.tenants.production.models import DozenStageAssignment
from apps.tenants.production.serializers import DozenStageAssignmentSerializer
from apps.tenants.staff.models import Worker

from . import services
from .models import PaymentSettlement
from .serializers import PaymentSettlementSerializer, SettlementAdjustmentSerializer

TOKEN_SALT = "shoeflow.worker-portal"
TOKEN_MAX_AGE = 60 * 60 * 8  # la sesión dura 8 horas; luego vuelve a ingresar con su DNI
HISTORY_DAYS = 180  # trabajo ya pagado que se muestra por defecto (lo pendiente siempre se muestra)

LOGIN_ERROR = "No pudimos ingresar. Revisa tus datos o consulta con el administrador."
SESSION_ERROR = "Tu sesión venció. Ingresa de nuevo con tu DNI."


# --------------------------------------------------------------------------
# Acceso: token firmado del trabajador
# --------------------------------------------------------------------------

class WorkerPrincipal:
    """Lo que DRF deja en request.user cuando entra un trabajador."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, worker):
        self.worker = worker
        self.pk = self.id = worker.pk


def make_token(worker):
    # Incluye el esquema (empresa): un token de una empresa no sirve en otra
    return signing.dumps({"w": worker.pk, "s": connection.schema_name}, salt=TOKEN_SALT)


class WorkerTokenAuthentication(BaseAuthentication):
    keyword = "Worker"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword.lower().encode():
            return None  # no es un token de trabajador
        if len(parts) != 2:
            raise AuthenticationFailed(SESSION_ERROR)

        try:
            payload = signing.loads(parts[1].decode(), salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        except (signing.BadSignature, UnicodeError):  # incluye token vencido
            raise AuthenticationFailed(SESSION_ERROR)

        if payload.get("s") != connection.schema_name:
            raise AuthenticationFailed(SESSION_ERROR)

        # Se consulta en cada petición: si lo desactivan, pierde el acceso al instante
        worker = Worker.objects.filter(pk=payload.get("w"), is_active=True).first()
        if worker is None:
            raise AuthenticationFailed(SESSION_ERROR)
        return (WorkerPrincipal(worker), None)

    def authenticate_header(self, request):
        return self.keyword  # hace que un token malo responda 401 y no 403


class IsWorkerPortal(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, WorkerPrincipal)


class PortalLoginThrottle(SimpleRateThrottle):
    """Máximo 10 intentos por minuto desde una misma IP (frena a quien pruebe DNIs al azar)."""

    scope = "worker_portal_login"

    def get_rate(self):
        return "10/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


# --------------------------------------------------------------------------
# PIN (APAGADO). Para exigir DNI + PIN de 4 dígitos:
#   1. Descomenta `pin` en PortalLoginSerializer.
#   2. Descomenta el bloque "PIN" en PortalLoginView.post (y los dos imports de arriba).
#   3. Asigna el PIN de cada trabajador con set_worker_pin(worker, "1234")
#      (por ejemplo desde una acción del administrador en WorkerViewSet).
#   4. En el frontend, descomenta el campo PIN en WorkerPortalLogin.tsx.
# El PIN se guarda cifrado en Worker.password (ese campo ya existe y no se usa).
# Si tu WorkerSerializer expone `password`, quítalo para que nunca salga en el API.
# --------------------------------------------------------------------------

def set_worker_pin(worker, pin):
    if not (isinstance(pin, str) and pin.isdigit() and len(pin) == 4):
        raise ValidationError({"pin": "El PIN debe tener exactamente 4 dígitos."})
    worker.password = make_password(pin)
    worker.save(update_fields=["password", "updated_at"])


# --------------------------------------------------------------------------
# Serializers (solo lo que el trabajador necesita ver de sí mismo)
# --------------------------------------------------------------------------

class PortalLoginSerializer(serializers.Serializer):
    dni = serializers.CharField(max_length=15)
    pin = serializers.CharField(min_length=4, max_length=4)  # ← PIN: descomentar


class PortalAssignmentSerializer(DozenStageAssignmentSerializer):
    """Una etapa suya. Sin el trabajador ni notas internas del administrador."""

    class Meta(DozenStageAssignmentSerializer.Meta):
        fields = [
            "id", "dozen_code", "specialty", "status",
            "delivered_at", "completed_at", "unit_price", "amount",
            "week_identifier", "week_label", "settlement",
        ]
        read_only_fields = fields


class PortalSettlementDetailSerializer(PaymentSettlementSerializer):
    items = PortalAssignmentSerializer(many=True, read_only=True)
    adjustments = SettlementAdjustmentSerializer(many=True, read_only=True)

    class Meta(PaymentSettlementSerializer.Meta):
        fields = PaymentSettlementSerializer.Meta.fields + ["items", "adjustments"]
        read_only_fields = fields


# --------------------------------------------------------------------------
# Vistas
# --------------------------------------------------------------------------

class PortalLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PortalLoginThrottle]

    def post(self, request):
        serializer = PortalLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dni = serializer.validated_data["dni"].strip()

        worker = Worker.objects.filter(dni=dni, is_active=True).first()
        if worker is None:
            # Mismo mensaje exista o no el DNI: no revela quién trabaja aquí
            return Response({"detail": LOGIN_ERROR}, status=400)

        # ── PIN (descomentar para exigir DNI + PIN) ─────────────────────────
        pin = serializer.validated_data["pin"]
        fail_key = f"portal-fail:{connection.schema_name}:{dni}"
        if cache.get(fail_key, 0) >= 5:  # 4 dígitos = 10 000 combinaciones: hay que limitar intentos
            return Response({"detail": "Demasiados intentos. Espera 15 minutos."}, status=429)
        if not worker.password or not check_password(pin, worker.password):
            cache.set(fail_key, cache.get(fail_key, 0) + 1, 15 * 60)
            return Response({"detail": LOGIN_ERROR}, status=400)  # sin PIN asignado tampoco entra
        cache.delete(fail_key)
        # ────────────────────────────────────────────────────────────────────

        return Response({
            "token": make_token(worker),
            "expires_in": TOKEN_MAX_AGE,
            "worker": {"id": worker.id, "names": worker.names},
        })


class PortalBaseView(APIView):
    authentication_classes = [WorkerTokenAuthentication]
    permission_classes = [IsWorkerPortal]

    @property
    def worker(self):
        return self.request.user.worker


class PortalSummaryView(PortalBaseView):
    """GET /portal/summary/ -> lo que le corresponde cobrar hoy y su último pago."""

    def get(self, request):
        worker = self.worker
        items = list(services.pending_assignments_all(worker))
        adjustments = list(services.pending_adjustments(worker).select_related("worker").order_by("created_at"))
        last = (
            PaymentSettlement.objects.filter(worker=worker)
            .select_related("worker")
            .order_by("-end_date", "-id")
            .first()
        )
        return Response({
            "worker": {"id": worker.id, "names": worker.names},
            "pending_count": len(items),
            **services.calculate_totals(items, adjustments),  # total_earned, total_adjustments, total_to_pay
            "pending_weeks": services.pending_weeks(worker),
            "pending_adjustments": SettlementAdjustmentSerializer(adjustments, many=True).data,
            "last_payment": PaymentSettlementSerializer(last).data if last else None,
        })


class PortalAssignmentsView(PortalBaseView):
    """GET /portal/assignments/ -> su trabajo (pendiente siempre; lo pagado, últimos 6 meses).
    ?all=true trae todo el historial."""

    def get(self, request):
        qs = (
            DozenStageAssignment.objects.filter(worker=self.worker)
            .exclude(status=DozenStageAssignment.Status.CANCELED)
            .select_related("dozen", "specialty")
        )
        if request.query_params.get("all") != "true":
            since = timezone.localdate() - timedelta(days=HISTORY_DAYS)
            qs = qs.filter(Q(completed_at__gte=since) | Q(settlement__isnull=True))
        qs = qs.order_by("-completed_at", "-id")
        return Response(PortalAssignmentSerializer(qs, many=True).data)


class PortalPaymentsView(PortalBaseView):
    """GET /portal/payments/ -> sus pagos, del más reciente al más antiguo."""

    def get(self, request):
        qs = (
            PaymentSettlement.objects.filter(worker=self.worker)
            .select_related("worker")
            .order_by("-end_date", "-id")
        )
        return Response(PaymentSettlementSerializer(qs, many=True).data)


class PortalPaymentDetailView(PortalBaseView):
    """GET /portal/payments/<id>/ -> un pago suyo con sus etapas y ajustes."""

    def get(self, request, pk):
        qs = PaymentSettlement.objects.filter(worker=self.worker).prefetch_related(
            "adjustments__worker", "items__dozen", "items__specialty"
        ).select_related("worker")
        return Response(PortalSettlementDetailSerializer(get_object_or_404(qs, pk=pk)).data)
