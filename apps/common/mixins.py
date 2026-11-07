class OptionalPaginationMixin:
    def paginate_queryset(self, queryset):
        if self.request.query_params.get('no_pagination') == 'true':
            return None
        return super().paginate_queryset(queryset)


class ActiveFilterMixin:
    """?is_active=true|false para ocultar los desactivados en los selects."""
 
    def get_queryset(self):
        qs = super().get_queryset()
        value = self.request.query_params.get("is_active")
        if value in ("true", "false"):
            qs = qs.filter(is_active=(value == "true"))
        return qs