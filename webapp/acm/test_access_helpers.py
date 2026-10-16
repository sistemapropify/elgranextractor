"""Authenticated Propify fixtures for pre-existing ACM calculation/report tests."""
from .access import ACMAccess, DEFAULTS
from .access_data import opaque_id


def install_propify_fixture(test):
    from unittest.mock import patch

    def access(request):
        user = getattr(request, 'current_user', None)
        if not user or not user.is_authenticated or not user.is_active:
            return None
        user.username = 'test-propify-user'
        if not hasattr(user, 'is_superuser'):
            user.is_superuser = False
        role = {'id': 100, 'name': 'Rol de prueba'}
        value = ACMAccess(user, role, role, {key: True for key in DEFAULTS}, 0, '')
        request.acm_access = value
        request.acm_identity = user
        return value

    fixture = patch('acm.access.get_access', side_effect=access)
    fixture.start()
    test.addCleanup(fixture.stop)


def client_selection(request, data):
    import copy
    value = copy.deepcopy(data)
    # Original fixture IDs still name source evidence; the browser uses opaque IDs.
    for key in ('excluded', 'report_ids'):
        if isinstance(value.get(key), list):
            value[key] = [item if item.startswith('c-') else opaque_id(request, item) for item in value[key]]
    return value
