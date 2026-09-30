"""Shared access policy for scraped property editing and identity review."""
def user_for(request):
    return getattr(request, 'current_user', None) or getattr(request, 'user', None)


def allowed(user):
    return bool(user and getattr(user, 'is_active', False) and
                (getattr(user, 'is_staff', False) or user.has_perm('ingestas.change_propiedadescompetencia')))
