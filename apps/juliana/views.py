from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import ugettext as _

from apps.scheduling.models import Event
from utils.auth.decorators import tender_required


def _get_product_list(event):
    products = []

    for sellingprice in event.pricegroup.sellingprice_set.all():
        for product in sellingprice.productgroup.permanentproduct_set.filter(is_available=True):
            products.append({
                'id': product.pk,
                'name': product.name,
                'text_color': product.text_color,
                'background_color': product.background_color,
                'price': int(sellingprice.price * 100),
                'position': product.position,
            })

    products.sort(key=lambda x: x['position'])

    for product in event.temporaryproducts.all():
        products.append({
            'id': product.pk,
            'name': product.name,
            'text_color': product.text_color,
            'background_color': product.background_color,
            'price': int(product.price * 100),
        })

    return products


def _get_onscreen_users(event):
    # people for on-screen checkout
    onscreen_users = User.objects.filter(
        Q(is_active=True),
        Q(authorizations__organization=event.organizer),
        Q(authorizations__start_date__lte=timezone.now()),
        Q(authorizations__end_date__isnull=True) | Q(authorizations__end_date__gte=timezone.now()),
        (Q(membership__organization=event.organizer) & (Q(membership__is_active=True) | Q(membership__onscreen_checkout=True))) | Q(profile__is_external_entity=True),
    ).order_by('-profile__is_external_entity', 'first_name')
    split_index = next((index for index, user in enumerate(onscreen_users) if not user.profile.is_external_entity), 0)
    return [onscreen_users[0:split_index], onscreen_users[split_index:]]


@login_required
@tender_required
def juliana(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if not event.is_tender(request.user):
        return render(request, '403.html', {'reason': _('You are not a tender for this event.')}, status=403)
    if not event.can_be_opened(request.user):
        return render(request, '403.html', {'reason': _('This event is not open yet.')}, status=403)

    # data
    products = _get_product_list(event)
    onscreen_checkout = _get_onscreen_users(event)

    # settings
    debug = settings.DEBUG
    countdown = settings.JULIANA_COUNTDOWN if hasattr(settings, 'JULIANA_COUNTDOWN') else 5

    # use default websocket URL and protocol
    websocket_url = settings.JULIANA_WEBSOCKET_URL
    websocket_protocol = settings.JULIANA_WEBSOCKET_PROTOCOL

    # use special URL when the Android app is in use
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'net.inter_actief.juliananfc':
        websocket_url = 'ws://localhost:3000'
        websocket_protocol = None

    # allow user to override the values in the request
    if 'websocket_url' in request.GET:
        websocket_url = request.GET.get('websocket_url')
    if 'websocket_protocol' in request.GET:
        websocket_protocol = request.GET.get('websocket_protocol') if len(request.GET.get('websocket_protocol')) > 0 else None

    return render(request, 'juliana/index.html', locals())
