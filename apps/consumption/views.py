import calendar
import datetime

from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse_lazy
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView
from wkhtmltopdf.views import PDFTemplateResponse, PDFTemplateView

from apps.scheduling.models import Event
from utils.auth.decorators import foundation_manager_required
from utils.auth.mixins import FoundationManagerRequiredMixin
from utils.mixins import CrispyFormMixin

from .forms import (
    ConsumptionFormConfirmationForm, ConsumptionFormForm,
    ExportConsumptionFormsForm, UnitEntryFormSet, WeightEntryFormSet,
)
from .models import (
    ConsumptionForm, ConsumptionProduct, WeightConsumptionProduct,
)


def dcf(request, pk):
    # Get event and verify rights
    event = get_object_or_404(Event, pk=pk)

    if not event.is_tender(request.user):
        return render(request, '403.html', {'reason': _('You are not a tender for this event.')}, status=403)

    # Get consumption form or create one
    cf = event.consumptionform if hasattr(event, 'consumptionform') else ConsumptionForm(event=event)

    if cf.is_completed():
        return render(request, '403.html', {'reason': _('This consumption form has been completed.')}, status=403)

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


def complete_dcf(request, pk):
    # Get event and verify rights
    event = get_object_or_404(Event, pk=pk)

    if not event.is_tender(request.user):
        return render(request, '403.html', {'reason': _('You are not a tender for this event.')}, status=403)

    if not hasattr(event, 'consumptionform'):
        raise Http404

    cf = event.consumptionform

    if request.method == 'POST':
        form = ConsumptionFormConfirmationForm(request.POST)
        if form.is_valid() and cf.is_valid():
            cf.completed_by = request.user
            cf.completed_at = timezone.now()
            cf.save()
            return render(request, 'consumption/dcf_finished.html', locals())
    else:
        form = ConsumptionFormConfirmationForm()

    return render(request, 'consumption/dcf_check.html', locals())


@foundation_manager_required
def consumptionform_export(request):
    if request.method == 'POST':
        form = ExportConsumptionFormsForm(request.POST)
        if form.is_valid():
            # Create date range
            month = form.cleaned_data['month']
            year = form.cleaned_data['year']
            last_day = calendar.monthrange(year, month)[1]
            from_time = datetime.datetime(year, month, 1)
            till_time = datetime.datetime(year, month, last_day, 23, 59, 59)
            # Export pdf
            objects = ConsumptionForm.objects.filter(
                completed_at__isnull=False,
                event__starts_at__gte=from_time,
                event__starts_at__lte=till_time,
            )
            filename = 'Verbruiksformulieren %s %d.pdf' % (from_time.strftime('%B'), year)
            return PDFTemplateResponse(request, 'consumption/dcf_pdf.html',
                                       context={'objects': objects}, filename=filename)
    else:
        form = ExportConsumptionFormsForm()

    return render(request, 'consumption/dcf_export.html', locals())


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


class ConsumptionFormListView(ListView):
    paginate_by = 30

    def get_queryset(self):
        profile = self.request.user.profile

        if profile.is_foundation_manager or self.request.user.is_superuser:
            qs = ConsumptionForm.objects.all()
        elif profile.is_manager(self.request.organization) or profile.is_treasurer(self.request.organization):
            qs = ConsumptionForm.objects.filter(event__organizer=self.request.organization)
        else:
            raise PermissionDenied

        return qs.order_by('-event__starts_at').select_related('event__organizer')


class ConsumptionFormDetailView(DetailView):
    model = ConsumptionForm

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        if not request.user.is_superuser and not request.user.profile.is_foundation_manager \
                and not request.user.profile.is_manager(self.object.event.organizer) \
                and not request.user.profile.is_treasurer(self.object.event.organizer):
            raise PermissionDenied

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ConsumptionFormPDFView(PDFTemplateView):
    template_name = 'consumption/dcf_pdf.html'

    def get(self, request, *args, **kwargs):
        self.object = get_object_or_404(ConsumptionForm, pk=kwargs['pk'])

        if not request.user.is_superuser and not request.user.profile.is_foundation_manager \
                and not request.user.profile.is_manager(self.object.event.organizer) \
                and not request.user.profile.is_treasurer(self.object.event.organizer):
            raise PermissionDenied

        return super(ConsumptionFormPDFView, self).get(request, *args, **kwargs)

    def get_filename(self):
        return 'Verbruiksformulier %s.pdf' % self.object.event

    def get_context_data(self, **kwargs):
        context = super(ConsumptionFormPDFView, self).get_context_data(**kwargs)
        context['object'] = self.object
        return context
