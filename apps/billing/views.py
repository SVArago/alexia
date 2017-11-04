from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.core.urlresolvers import reverse
from django.db.models import Count, Sum
from django.db.models.functions import ExtractYear, ExtractMonth
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views.generic.base import RedirectView, TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView
from django.views.generic.list import ListView

from apps.billing.forms import (
    FilterEventForm, PermanentProductForm, SellingPriceForm, CreateOrderFormSet
)
from apps.billing.models import (
    PermanentProduct, PriceGroup, Product, ProductGroup, SellingPrice,
    TemporaryProduct,
)
from apps.scheduling.models import Event
from utils.auth.decorators import treasurer_required
from utils.auth.mixins import TreasurerRequiredMixin
from utils.mixins import (
    CreateViewForOrganization, CrispyFormMixin, EventOrganizerFilterMixin,
    FixedValueCreateView, OrganizationFilterMixin, OrganizationFormMixin,
)
from .models import Order, Purchase


@login_required
@treasurer_required
def order_list(request):
    event_list = Event.objects.filter(organizer=request.organization) \
        .annotate(order_count=Count('orders'), revenue=Sum('orders__amount')) \
        .filter(order_count__gt=0, ) \
        .order_by('-starts_at')
    paginator = Paginator(event_list, 20)

    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        events = paginator.page(1)
    except EmptyPage:
        events = paginator.page(paginator.num_pages)

    stats_years = Event.objects.annotate(year=ExtractYear('starts_at')) \
                       .filter(organizer=request.organization).values('year') \
                       .annotate(revenue=Sum('orders__amount')).order_by('-year')[:3]

    return render(request, "order/list.html", locals())


@login_required
@treasurer_required
def order_show(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if request.organization != event.organizer:
        raise PermissionDenied

    products = Purchase.objects.filter(order__event=event) \
        .values('product', 'product__name') \
        .annotate(amount=Sum('amount'), price=Sum('price'))

    external = Purchase.objects.filter(order__event=event,
                                       order__authorization__user__profile__is_external_entity=True) \
        .values('order__authorization__user',
                'order__authorization__user__first_name',
                'order__authorization__user__last_name') \
        .annotate(price=Sum('price'))
    external = [{
        'price': e['price'],
        'name': (e['order__authorization__user__first_name'] + ' ' + e['order__authorization__user__last_name']).strip()
    } for e in external]

    external_revenue = sum([x['price'] for x in external])

    internal_revenue = Purchase.objects.filter(order__event=event) \
                               .exclude(order__authorization__user__profile__is_external_entity=True) \
                               .aggregate(price=Sum('price'))['price']
    if internal_revenue is None:
        internal_revenue = 0

    orders = event.orders.select_related('authorization__user').prefetch_related('purchases', 'purchases__product').order_by('-placed_at')
    order_count = len(orders)  # efficientie: len() ipv count()
    order_sum = orders.aggregate(Sum('amount'))['amount__sum']

    return render(request, "order/show.html", locals())


class OrderCreateView(FormView, TreasurerRequiredMixin):
    template_name = 'billing/order_create_form.html'
    form_class = CreateOrderFormSet

    def get_event(self):
        event = get_object_or_404(Event, pk=self.kwargs['event_pk'])
        if event.organizer != self.request.organization:
            raise PermissionDenied
        return event

    def get_context_data(self, **kwargs):
        kwargs['event'] = self.get_event()
        return super(OrderCreateView, self).get_context_data(**kwargs)

    def get_success_url(self):
        return reverse(order_show, kwargs={'pk': self.get_event().id})

    def get_form_kwargs(self, **kwargs):
        kwargs = super(OrderCreateView, self).get_form_kwargs()
        kwargs['form_kwargs'] = {'event': self.get_event()}
        return kwargs

    def form_valid(self, formset):
        event = self.get_event()
        for form in formset:
            if len(form.cleaned_data) == 0:
                continue

            price = form.cleaned_data['amount'] * form.cleaned_data['product'].get_price(event)

            order = Order.objects.create(event=event, authorization=form.cleaned_data['authorization'],
                                         added_by=self.request.user)
            Purchase.objects.create(order=order, product=form.cleaned_data['product'],
                                    amount=form.cleaned_data['amount'], price=price)
            # We need to save the order again, as Order.save() calculates the order amount, so it has been set to
            # zero in the create() call. Yes, this is retarded behaviour but I don't dare to change it yet.
            order.save()

        return super(OrderCreateView, self).form_valid(formset)


class OrderDeleteView(TreasurerRequiredMixin, OrganizationFormMixin, CrispyFormMixin, DeleteView):
    model = Order
    template_name = "billing/order_confirm_delete.html"

    def get_queryset(self):
        return super(OrderDeleteView, self).get_queryset().filter(synchronized=False, event__organizer=self.request.organization)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()

        for purchase in self.object.purchases.all():
            purchase.delete()
        self.object.delete()

        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('event-orders', args=[self.object.event.id])


@login_required
@treasurer_required
def order_export(request):
    if request.method == 'POST':
        form = FilterEventForm(request.POST)
        if form.is_valid():
            event_list = Event.objects \
                .filter(
                    organizer=request.organization,
                    starts_at__gte=form.cleaned_data['from_time'],
                    starts_at__lte=form.cleaned_data['till_time'],
                )
            events = event_list \
                .annotate(order_count=Count('orders'), revenue=Sum('orders__amount')) \
                .filter(order_count__gt=0, ) \
                .order_by('starts_at')
            summary = event_list \
                .annotate(month=ExtractMonth('starts_at')) \
                .values('month') \
                .annotate(revenue=Sum('orders__amount')) \
                .order_by('month')
            return render(request, 'order/export_result.html', locals())
    else:
        form = FilterEventForm()

    return render(request, 'order/export_form.html', locals())


@login_required
def payment_show(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # bekijk als: * dit mijn transactie is
    #             * ik penningmeester van de organisatie in kwestie ben
    #             * ik superuser ben
    is_treasurer = request.user.is_superuser or (
        request.organization and
        request.organization == order.authorization.organization and
        request.user.profile.is_treasurer(request.organization)
    )
    if (order.authorization.user == request.user) \
            or request.user.is_superuser \
            or is_treasurer:
        return render(request, 'payment/show.html', locals())

    raise PermissionDenied


@login_required
@treasurer_required
def stats_year(request, year):
    months = Event.objects.annotate(month=ExtractMonth('starts_at')) \
        .filter(organizer=request.organization, starts_at__year=year) \
        .values('month').annotate(revenue=Sum('orders__amount')) \
        .order_by('month')
    return render(request, "order/stats_year.html", locals())


@login_required
@treasurer_required
def stats_month(request, year, month):
    month = int(month)
    if month not in range(1, 12):
        raise Http404
    events = Event.objects.filter(
        organizer=request.organization,
        starts_at__year=year,
        starts_at__month=month,
    ).annotate(revenue=Sum('orders__amount')).order_by('starts_at')

    return render(request, "order/stats_month.html", locals())


class PriceGroupListView(TreasurerRequiredMixin, OrganizationFilterMixin, ListView):
    model = PriceGroup


class PriceGroupDetailView(TreasurerRequiredMixin, OrganizationFilterMixin, DetailView):
    model = PriceGroup


class PriceGroupCreateView(TreasurerRequiredMixin, OrganizationFilterMixin, CrispyFormMixin, CreateViewForOrganization):
    model = PriceGroup
    fields = ['name']


class PriceGroupUpdateView(TreasurerRequiredMixin, OrganizationFilterMixin, CrispyFormMixin, UpdateView):
    model = PriceGroup
    fields = ['name']


class ProductGroupListView(TreasurerRequiredMixin, OrganizationFilterMixin, ListView):
    model = ProductGroup
    queryset = ProductGroup.objects.order_by('name')


class ProductGroupDetailView(TreasurerRequiredMixin, OrganizationFilterMixin, DetailView):
    model = ProductGroup


class ProductGroupCreateView(TreasurerRequiredMixin, OrganizationFilterMixin, CrispyFormMixin,
                             CreateViewForOrganization):
    model = ProductGroup
    fields = ['name']


class ProductGroupUpdateView(TreasurerRequiredMixin, OrganizationFilterMixin, CrispyFormMixin, UpdateView):
    model = ProductGroup
    fields = ['name']


class ProductGroupDeleteView(TreasurerRequiredMixin, OrganizationFilterMixin, CrispyFormMixin, DeleteView):
    model = ProductGroup

    def get_success_url(self):
        return reverse('productgroup_list')


class ProductRedirectView(TreasurerRequiredMixin, SingleObjectMixin, RedirectView):
    """
    View to redirect to either the PermanentProductDetailView or the
    TemporaryProductDetailView depending on the type of product.
    """
    model = Product
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        obj = self.get_object()

        if obj.is_permanent:
            self.pattern_name = 'permanentproduct_detail'
        elif obj.is_temporary:
            self.pattern_name = 'temporaryproduct_detail'
        else:
            raise ValueError('Product is neither permament nor temporary')

        return super(ProductRedirectView, self).get_redirect_url(*args, **kwargs)


class PermanentProductListView(TreasurerRequiredMixin, OrganizationFilterMixin, ListView):
    model = PermanentProduct

    def get_queryset(self):
        return super(PermanentProductListView, self).get_queryset().order_by('position')


class PermanentProductDetailView(TreasurerRequiredMixin, OrganizationFilterMixin, DetailView):
    model = PermanentProduct


class PermanentProductCreateView(TreasurerRequiredMixin, OrganizationFormMixin, CrispyFormMixin,
                                 CreateViewForOrganization):
    """
    Create view for permanent products.

    Sets initial ProductGroup if productgroup_pk is provided.
    """

    model = PermanentProduct
    form_class = PermanentProductForm

    def get_initial(self):
        initial = super(PermanentProductCreateView, self).get_initial()
        if 'productgroup_pk' in self.kwargs:
            initial['productgroup'] = get_object_or_404(ProductGroup, pk=self.kwargs['productgroup_pk'])
        return initial


class PermanentProductUpdateView(TreasurerRequiredMixin, OrganizationFilterMixin, OrganizationFormMixin, CrispyFormMixin,
                                 UpdateView):
    model = PermanentProduct
    form_class = PermanentProductForm


class PermanentProductDeleteView(TreasurerRequiredMixin, OrganizationFilterMixin, OrganizationFormMixin, CrispyFormMixin,
                                 DeleteView):
    model = PermanentProduct
    template_name = "billing/product_confirm_delete.html"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save()
        return HttpResponseRedirect(reverse('permanentproduct_list'))


class TemporaryProductDetailView(TreasurerRequiredMixin, EventOrganizerFilterMixin, DetailView):
    model = TemporaryProduct


class TemporaryProductCreateView(TreasurerRequiredMixin, CrispyFormMixin, FixedValueCreateView):
    model = TemporaryProduct
    fields = ['name', 'price', 'text_color', 'background_color', 'is_food']

    def get_instance(self):
        event = get_object_or_404(Event, pk=self.kwargs['event_pk'])
        return self.model(event=event)


class TemporaryProductUpdateView(TreasurerRequiredMixin, EventOrganizerFilterMixin, CrispyFormMixin, UpdateView):
    model = TemporaryProduct
    fields = ['name', 'price', 'text_color', 'background_color']


class TemporaryProductDeleteView(TreasurerRequiredMixin, EventOrganizerFilterMixin, CrispyFormMixin, DeleteView):
    model = TemporaryProduct
    template_name = "billing/product_confirm_delete.html"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save()
        return HttpResponseRedirect(self.object.event.get_absolute_url())


class SellingPriceCreateView(TreasurerRequiredMixin, OrganizationFormMixin, CrispyFormMixin, CreateView):
    """
    Create view for selling prices.

    Sets initial PriceGroup or ProductGroup if pricegroup_pk or productgroup_pk is provided.
    """

    model = SellingPrice
    form_class = SellingPriceForm

    def get_initial(self):
        initial = super(SellingPriceCreateView, self).get_initial()
        if 'pricegroup_pk' in self.kwargs:
            initial['pricegroup'] = get_object_or_404(PriceGroup, pk=self.kwargs['pricegroup_pk'])
        if 'productgroup_pk' in self.kwargs:
            initial['productgroup'] = get_object_or_404(ProductGroup, pk=self.kwargs['productgroup_pk'])
        return initial


class SellingPriceFilterMixin(object):
    """
    Mixin to select only SellingPrice object belonging to the current organization.
    """

    def get_queryset(self):
        organization = self.request.organization
        return super(SellingPriceFilterMixin, self).get_queryset().filter(pricegroup__organization=organization,
                                                                          productgroup__organization=organization)


class SellingPriceUpdateView(TreasurerRequiredMixin, SellingPriceFilterMixin, OrganizationFormMixin, CrispyFormMixin,
                             UpdateView):
    model = SellingPrice
    form_class = SellingPriceForm


class SellingPriceDeleteView(TreasurerRequiredMixin, SellingPriceFilterMixin, DeleteView):
    model = SellingPrice

    def get_success_url(self):
        return self.object.pricegroup.get_absolute_url()


class SellingPriceMatrixView(TreasurerRequiredMixin, TemplateView):
    """
    Price matrix view.

    Displays a matrix with all pricegroup-productgroup combinations.
    """
    template_name = 'billing/sellingprice_matrix.html'

    def get_context_data(self, **kwargs):
        context = super(SellingPriceMatrixView, self).get_context_data(**kwargs)

        organization = self.request.organization

        pricegroups = PriceGroup.objects.filter(organization=organization) \
            .prefetch_related('sellingprice_set', 'sellingprice_set__productgroup')
        productgroups = ProductGroup.objects.filter(organization=organization) \
            .prefetch_related('permanentproduct_set')

        pricedata = dict([(pricegroup,
                           dict([(sellingprice.productgroup, sellingprice)
                                 for sellingprice in pricegroup.sellingprice_set.all()]))
                          for pricegroup in pricegroups])
        """ Dict pricegroup -> productgroup -> sellingprice """

        data = []
        """ List of (productgroup, [(pricegroup, sellingprice), ...], has_product) tuples """

        for productgroup in productgroups:
            data.append((productgroup,
                         [(pricegroup,
                           pricedata[pricegroup][productgroup] if productgroup in pricedata[pricegroup] else None)
                          for pricegroup in pricegroups],
                         productgroup.permanentproduct_set.filter(deleted=False).count() > 0
                         ))

        # Order product groups in such that groups without any product are shown at the bottom,
        # and the others in alphabetical order.
        context['pricegroups'] = pricegroups
        context['productgroups'] = sorted(data, key=lambda p: (not p[2], p[0].name))
        return context
