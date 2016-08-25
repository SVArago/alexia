from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
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

    # people for on-screen checkout
    onscreen_users = User.objects.filter(
        Q(authorizations__organization=event.organizer),
        Q(authorizations__start_date__lte=timezone.now()),
        Q(authorizations__end_date__isnull=True) | Q(authorizations__end_date__gte=timezone.now()),
        (Q(membership__organization=event.organizer) & Q(membership__is_active=True)) | Q(profile__is_external_entity=True),
    ).order_by('-profile__is_external_entity', 'first_name')
    split_index = next((index for index, user in enumerate(onscreen_users) if not user.profile.is_external_entity), 0)
    onscreen_checkout = [onscreen_users[0:split_index], onscreen_users[split_index:]]

    # settings
    debug = settings.DEBUG
    countdown = settings.JULIANA_COUNTDOWN

    # Detect if connection is made via the Juliana Android app
    androidapp = request.META.get('HTTP_X_REQUESTED_WITH') == 'net.inter_actief.juliananfc'

    return render(request, 'juliana/index.html', locals())
