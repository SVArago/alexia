from __future__ import unicode_literals

from crispy_forms.helper import FormHelper
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django.utils.dates import MONTHS
from django.utils.translation import ugettext as _

from utils.forms import _default_crispy_helper

from .models import ConsumptionForm, ConsumptionProduct, UnitEntry, WeightEntry


class ConsumptionFormForm(forms.ModelForm):
    class Meta:
        model = ConsumptionForm
        fields = ['comments']
        widgets = {
            'comments': forms.Textarea(attrs={'placeholder': _('Comments...'), 'rows': '4'}),
        }


class WeightEntryForm(forms.ModelForm):
    class Meta:
        model = WeightEntry
        fields = ['product', 'start_weight', 'kegs_changed', 'end_weight', 'flow_start', 'flow_end']

    def __init__(self, *args, **kwargs):
        super(WeightEntryForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(WeightEntryForm, self).clean()
        product = cleaned_data.get('product')
        start_weight = cleaned_data.get('start_weight')
        end_weight = cleaned_data.get('end_weight')
        flow_start = cleaned_data.get('flow_start')
        flow_end = cleaned_data.get('flow_end')

        if product and product.full_weight < start_weight:
            self.add_error('start_weight', ValidationError(_('Begin weight is higher than product max weight.')))

        if product and end_weight and product.empty_weight > end_weight:
            self.add_error('end_weight', ValidationError(_('End weight is lower than product min weight.')))

        if hasattr(product, 'has_flowmeter') and product.has_flowmeter and not flow_start:
            self.add_error('flow_start', ValidationError(_('Flowmeter positions are required for this product.')))

        if flow_start and flow_end and flow_start > flow_end:
            self.add_error('flow_end', ValidationError(_('Flowmeter start position is bigger than end.')))

        return cleaned_data


WeightEntryFormSet = inlineformset_factory(ConsumptionForm, WeightEntry, form=WeightEntryForm)


class UnitEntryForm(forms.ModelForm):
    class Meta:
        model = UnitEntry
        fields = ['product', 'amount']

    def __init__(self, *args, **kwargs):
        super(UnitEntryForm, self).__init__(*args, **kwargs)
        self.fields['product'].queryset = ConsumptionProduct.objects.filter(weightconsumptionproduct=None)


UnitEntryFormSet = inlineformset_factory(ConsumptionForm, UnitEntry, form=UnitEntryForm)


class ConsumptionFormConfirmationForm(forms.Form):
    cleaned = forms.BooleanField(
        label=_('I declare that I have cleaned the rooms'),
        help_text=_('After each event the rooms have to cleaned according to the cleaning checklist.'),
    )
    truth = forms.BooleanField(
        label=_('I declare that this form has been filled in truthfully'),
        help_text=_('I am sure that the values above are filled in correct and has been verified.'),
    )

    helper = FormHelper()
    helper.form_tag = False


class ExportConsumptionFormsForm(forms.Form):
    now = timezone.now()
    if now.month > 1:
        last_month = now.month - 1
        correct_year = now.year
    else:
        last_month = 12
        correct_year = now.year - 1
    month = forms.TypedChoiceField(label=_('Month'), choices=MONTHS.items(), coerce=int, initial=last_month)
    year = forms.IntegerField(label=_('Year'), initial=correct_year)

    helper = _default_crispy_helper(_('Export'))
