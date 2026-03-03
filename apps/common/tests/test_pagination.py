import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from apps.common.pagination import StandardResultsSetPagination

@pytest.mark.django_db
def test_standard_pagination_structure():
    factory = APIRequestFactory()
    request = factory.get('/fake-url/?page=1')
    paginator = StandardResultsSetPagination()
    queryset = list(range(30))  # имитируем 30 объектов

    paginated = paginator.paginate_queryset(queryset, Request(request))
    response = paginator.get_paginated_response(paginated).data

    assert set(response.keys()) == {'count', 'next', 'previous', 'results'}
    assert response['count'] == 30
    assert isinstance(response['results'], list)