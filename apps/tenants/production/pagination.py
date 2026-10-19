from rest_framework.pagination import PageNumberPagination


class ProductionPagination(PageNumberPagination):
    page_size = 50  # Cantidad por defecto del backend si no mandas limit
    page_size_query_param = 'limit'  # Permite que el Frontend controle la cantidad mediante ?limit=
    max_page_size = 200  # Máximo que se puede solicitar