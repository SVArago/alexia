from jsonrpc.site import JSONRPCSite

from apps.organization.models import AuthenticationData, Profile
from utils.auth.backends import RADIUS_BACKEND_NAME

api_v1_site = JSONRPCSite()
api_v1_site.name = 'Alexia API v1'


def format_authorization(authorization):
    return {
        'id': authorization.pk,
        'user': authorization.user.username,
        'user_id': authorization.user.id,
        'start_date': authorization.start_date.isoformat(),
        'end_date': authorization.end_date.isoformat() if authorization.end_date else None,
        'account': authorization.account,
    }


def format_location(location):
    """
    :type location: apps.organization.models.Location
    """
    return {
        'id': location.pk,
        'name': location.name
    }


def format_event(event):
    """
    :type event: apps.scheduling.models.Event
    """
    return {
        'id': event.pk,
        'name': event.name
    }


def format_event_extended(event):
    """
    :type event: apps.scheduling.models.Event
    """
    return {
        'id': event.pk,
        'name': event.name,
        'organizer': format_organization(event.organizer),
        'participants': [format_organization(x) for x in event.participants.all()],
        'locations': [format_location(x) for x in event.location.all()],
        'starts_at': event.starts_at.isoformat(),
        'ends_at': event.ends_at.isoformat()
    }



def format_organization(organization):
    """
    :type organization: apps.organization.models.Organization
    """
    return {
        'slug': organization.slug,
        'name': organization.name
    }


def format_order(order):
    purchases = [{
        'product': {
            'id': p.product.pk,
            'name': p.product.name,
        },
        'amount': p.amount,
        'price': p.price,
    } for p in order.purchases.all()]

    rfid = None
    if order.rfidcard:
        rfid = {
            'atqa': order.rfidcard.atqa if len(order.rfidcard.atqa) > 0 else None,
            'sak': order.rfidcard.sak if len(order.rfidcard.sak) > 0 else None,
            'uid': order.rfidcard.uid
        }

    return {
        'id': order.pk,
        'rfid': rfid,
        'event': format_event(order.event),
        'authorization': format_authorization(order.authorization),
        'placed_at': order.placed_at.isoformat(),
        'synchronized': order.synchronized,
        'purchases': purchases,
    }


def format_rfidcard(rfidcard):
    """

    :type rfidcard: apps.billing.models.RfidCard
    """
    return {
        'atqa': rfidcard.atqa if len(rfidcard.atqa) > 0 else None,
        'sak': rfidcard.sak if len(rfidcard.sak) > 0 else None,
        'uid': rfidcard.uid,
        'registered_at': rfidcard.registered_at.isoformat(),
        'user': rfidcard.user.username,
    }


def format_user(user):
    """

    :type user: django.contrib.auth.models.User
    """
    try:
        user_name = user.authenticationdata_set.get(backend=RADIUS_BACKEND_NAME).username
    except AuthenticationData.DoesNotExist:
        user_name = None

    auth_data = [{
        'backend': u.backend,
        'username': u.username,
    } for u in user.authenticationdata_set.all()]

    try:
       external_entity = user.profile.is_external_entity
    except Profile.DoesNotExist:
       external_entity = False

    return {
        'id': user.id,
        'radius_username': user_name,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'authentication_data': auth_data,
        'is_external_entity': external_entity
    }
