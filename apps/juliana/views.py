from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext_lazy as _

from apps.scheduling.models import Event
from utils.auth.decorators import tender_required


@login_required
@tender_required
def juliana(request, pk):
    event = get_object_or_404(Event, pk=pk)

    # Permission checks
    if not request.user.is_superuser and not event.is_tender(request.user):
        return render(request, "403.html", {'reason': _('You are not a tender for this event')}, status=403)
    if not request.user.is_superuser and not event.can_be_opened():
        return render(request, "403.html", {'reason': _('This event is not open')}, status=403)

    products = []

    for sellingprice in event.pricegroup.sellingprice_set.all():
        for product in sellingprice.productgroup.permanentproduct_set.all():
            products.append({
                'id': product.pk,
                'name': product.name,
                'text_color': product.text_color,
                'background_color': product.background_color,
                'price': int(sellingprice.price * 100),
                'position': product.position,
            })

    products.sort(cmp=lambda x, y: cmp(x['position'], y['position']))

    for product in event.temporaryproducts.all():
        products.append({
            'id': product.pk,
            'name': product.name,
            'text_color': product.text_color,
            'background_color': product.background_color,
            'price': int(product.price * 100),
        })

    # settings
    debug = settings.DEBUG
    countdown = settings.JULIANA_COUNTDOWN

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
