"""Carry one private, owner-bound analysis across role perspectives."""
import secrets

from django.core import signing

from .access_data import seal, unseal, project, issue_snapshot, opaque_id, restore_selection
from .components_engine import calculate, number
from .listing_operation import POLICY_VERSION

SESSION_ANALYSIS = 'acm_role_analysis'


def saved_analysis(request, key):
    saved = request.session.get(SESSION_ANALYSIS)
    if not key or not isinstance(saved, dict) or saved.get('key') != key:
        return None
    data = unseal(saved.get('payload'))
    if data.get('owner') != request.acm_access.user.pk or data.get('policy') != POLICY_VERSION:
        raise signing.BadSignature('analysis owner or policy changed')
    return data


def selection_ui(request, state, ui):
    if not isinstance(ui, dict):
        raise ValueError('Invalid analysis view')
    hidden = restore_selection(request, state, {'report_ids': ui.get('hidden_ids', [])})['report_ids']
    layers = ui.get('layers', [])
    if not isinstance(layers, list) or any(value not in ('land', 'property', 'property_reference', 'other_reference') for value in layers):
        raise ValueError('Invalid map layers')
    output = {'hidden_ids': hidden, 'layers': layers}
    viewport = ui.get('viewport')
    if isinstance(viewport, dict):
        lat, lng, zoom = (number(viewport.get(key)) for key in ('lat', 'lng', 'zoom'))
        if lat is not None and lng is not None and zoom is not None and -90 <= lat <= 90 and -180 <= lng <= 180 and 0 <= zoom <= 22:
            output['viewport'] = dict(lat=lat, lng=lng, zoom=zoom)
    return output


def remember_analysis(request, state, excluded, ui):
    key = secrets.token_urlsafe(18)
    data = {'owner': request.acm_access.user.pk, 'policy': POLICY_VERSION,
            'state': state, 'excluded': excluded, 'ui': ui}
    request.session[SESSION_ANALYSIS] = {'key': key, 'payload': seal(data)}
    return key


def resume_analysis(request):
    key = request.GET.get('analysis_view')
    if not key:
        return None
    try:
        saved = saved_analysis(request, key)
        if saved is None:
            return {'unavailable': True}
        flags = request.acm_access.permissions
        if not flags['property_data'] or not flags['calculate']:
            # Keep the original on the server for returning to an allowed role.
            return {'blocked': True}
        state, excluded = saved['state'], saved['excluded']
        result = calculate(state['records'], state['params'], excluded)
        client, result, excluded = project(request, state, result, excluded)
        ui = dict(saved['ui'])
        ui['hidden_ids'] = [opaque_id(request, value) for value in ui['hidden_ids']]
        return {'snapshot': {**client, 'result': result, 'token': issue_snapshot(request, state)},
                'excluded': excluded, 'ui': ui}
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return {'unavailable': True}
