from rest_framework.pagination import PageNumberPagination

class ProductionPagination(PageNumberPagination):
    page_size = 50  # En este módulo mostramos 50 por defecto
    page_size_query_param = 'limit' # El frontend puede usar ?limit=100
    max_page_size = 200