"""History visibility and original authors, using verified Propify identities."""
import logging

from django.db import DatabaseError, connections
from django.db.utils import ConnectionDoesNotExist

from .access import ACMIdentity, database
from .access_models import ACMPortalAnalysis

logger = logging.getLogger(__name__)


def visible_history(request):
    rows = ACMPortalAnalysis.objects.using(database()).all()
    if not request.acm_access.can_view_all_history:
        rows = rows.filter(owner_id=str(request.acm_access.user.pk))
    return rows


def lookup_authors(owner_ids):
    ids = [int(value) for value in owner_ids if str(value).isdecimal() and 0 < int(value) < 2**31]
    if not ids:
        return {}
    try:
        with connections['propifai'].cursor() as cursor:
            cursor.execute('SELECT id,username,first_name,last_name FROM [dbo].[user] WHERE id IN (' +
                           ','.join(['%s'] * len(ids)) + ')', ids)
            return {str(row[0]): ACMIdentity(str(row[0]), row[1], row[2] or '', row[3] or '')
                    for row in cursor.fetchall()}
    except (DatabaseError, ConnectionDoesNotExist):
        logger.warning('No se pudieron consultar los autores del historial ACM.')
        return {}


def attach_authors(rows, current_user):
    rows = list(rows)
    authors = {str(current_user.pk): current_user}
    for row in rows:
        saved = row.snapshot.get('author', {})
        if isinstance(saved, dict) and str(saved.get('id')) == str(row.owner_id) and saved.get('username'):
            row.author = ACMIdentity(str(row.owner_id), str(saved['username']),
                                     str(saved.get('first_name') or ''), str(saved.get('last_name') or ''))
            authors.setdefault(str(row.owner_id), row.author)
    authors.update(lookup_authors({str(row.owner_id) for row in rows} - authors.keys()))
    for row in rows:
        row.author = getattr(row, 'author', None) or authors.get(str(row.owner_id)) or ACMIdentity(
            str(row.owner_id), 'Usuario ' + str(row.owner_id))
        row.is_own = str(row.owner_id) == str(current_user.pk)
    return rows
