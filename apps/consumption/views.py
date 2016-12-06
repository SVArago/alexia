from django.core.urlresolvers import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import ugettext as _
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView

from apps.scheduling.models import Event
from utils.auth.mixins import FoundationManagerRequiredMixin
from utils.mixins import CrispyFormMixin

from .forms import ConsumptionFormForm, WeightEntryFormSet, UnitEntryFormSet
from .models import ConsumptionProduct, WeightConsumptionProduct, ConsumptionForm


def dcf(request, pk):
    # Get event and verify rights
    event = get_object_or_404(Event, pk=pk)

    if not event.is_tender(request.user):
        return render(request, '403.html', {'reason': _('You are not a tender for this event')}, status=403)

    # Get consumption form or create one
    if hasattr(event, 'consumptionform'):
        cf = event.consumptionform
    else:
        cf = ConsumptionForm(event=event)

    # Post or show form?
    if request.method == 'POST':
        form = ConsumptionFormForm(request.POST, instance=cf)
        weight_form = WeightEntryFormSet(request.POST, instance=cf)
        unit_form = UnitEntryFormSet(request.POST, instance=cf)
        if form.is_valid() and weight_form.is_valid() and unit_form.is_valid():
            form.save()
            weight_form.save()
            unit_form.save()
            return redirect('dcf', event.pk)
    else:
        form = ConsumptionFormForm(instance=cf)
        weight_form = WeightEntryFormSet(instance=cf)
        unit_form = UnitEntryFormSet(instance=cf)

    return render(request, 'consumption/dcf.html', locals())


class ConsumptionProductListView(FoundationManagerRequiredMixin, ListView):
    model = ConsumptionProduct


class ConsumptionProductCreateView(FoundationManagerRequiredMixin, CrispyFormMixin, CreateView):
    model = ConsumptionProduct
    fields = ['name']
    success_url = reverse_lazy('consumptionproduct_list')
    template_name = 'consumption/consumptionproduct_form.html'


class WeightConsumptionProductCreateView(ConsumptionProductCreateView):
    model = WeightConsumptionProduct
    fields = ['name', 'full_weight', 'empty_weight', 'has_flowmeter']


class ConsumptionProductUpdateView(FoundationManagerRequiredMixin, CrispyFormMixin, UpdateView):
    model = ConsumptionProduct
    fields = ['name']
    success_url = reverse_lazy('consumptionproduct_list')
    template_name = 'consumption/consumptionproduct_form.html'


class WeightConsumptionProductUpdateView(ConsumptionProductUpdateView):
    model = WeightConsumptionProduct
    fields = ['name', 'full_weight', 'empty_weight', 'has_flowmeter']
