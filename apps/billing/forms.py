import calendar
import datetime

from django import forms
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.db.models.functions import Lower
from django.forms import formset_factory
from django.utils import timezone
from django.utils.translation import ugettext as _

from apps.billing.models import (
    PermanentProduct, PriceGroup, ProductGroup, SellingPrice, Authorization,
    Product)
from utils.forms import AlexiaForm, _default_crispy_helper


class PermanentProductForm(forms.ModelForm):
    class Meta:
        model = PermanentProduct
        fields = ['name', 'productgroup', 'position', 'text_color', 'background_color', 'is_food']

    def __init__(self, organization, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.fields['productgroup'].queryset = ProductGroup.objects.filter(organization=organization)


class SellingPriceForm(forms.ModelForm):
    class Meta:
        model = SellingPrice
        fields = ['pricegroup', 'productgroup', 'price']

    def __init__(self, organization, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.fields['pricegroup'].queryset = PriceGroup.objects.filter(organization=organization)
        self.fields['productgroup'].queryset = ProductGroup.objects.filter(organization=organization)


class FilterEventForm(AlexiaForm):
    helper = _default_crispy_helper(_('Export'))
    helper.attrs = {'target': '_blank'}

    now = timezone.now()
    if now.month > 1:
        last_month = now.month - 1
        year = now.year
    else:
        last_month = 12
        year = now.year - 1

    last_day = calendar.monthrange(now.year, last_month)[1]

    from_time = forms.SplitDateTimeField(
        label=_('From time'),
        initial=datetime.datetime(year, last_month, 1),
    )
    till_time = forms.SplitDateTimeField(
        label=_('Till time'),
        initial=datetime.datetime(year, last_month, last_day, 23, 59, 59),
    )


class CreateOrderForm(AlexiaForm):
    authorization = forms.ModelChoiceField(queryset=Authorization.objects)
    product = forms.ModelChoiceField(queryset=Product.objects)
    amount = forms.IntegerField()

    def __init__(self, event, *args, **kwargs):
        super(CreateOrderForm, self).__init__(*args, **kwargs)

        self.fields['authorization'].queryset = Authorization.objects.select_related('user') \
            .filter(organization=event.organizer, end_date__isnull=True) \
            .order_by(Coalesce('user__profile__is_external_entity', False).desc(), Lower('user__first_name').asc(), 'user__last_name')
        self.fields['authorization'].label_from_instance = lambda a: a.user.get_full_name()

        self.fields['product'].queryset = Product.objects.filter(
            Q(deleted=False),
            Q(permanentproduct__organization=event.organizer,
              permanentproduct__productgroup__sellingprice__pricegroup=event.pricegroup,
              permanentproduct__productgroup__sellingprice__isnull=False) |
            Q(temporaryproduct__event=event)
        ).order_by('name')


CreateOrderFormSet = formset_factory(CreateOrderForm, extra=20, can_delete=False)