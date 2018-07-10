from __future__ import unicode_literals

import math
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from .managers import EventManager, StandardReservationManager
from .tools import notify_tenders


@python_2_unicode_compatible
class MailTemplate(models.Model):
    NAME_CHOICES = (
        ('enrollopen', _('Enrollment open')),
        ('enrollclosed', _('Enrollment closed')),
        ('reminder', _('Reminder')),
    )

    organization = models.ForeignKey('organization.Organization', models.CASCADE, verbose_name=_('organization'))
    name = models.CharField(_('name'), max_length=32, choices=NAME_CHOICES)
    subject = models.CharField(_('subject'), max_length=255)
    template = models.TextField(_('template'))
    is_active = models.BooleanField(_('is active'), default=False)
    send_at = models.PositiveIntegerField(_('send at'), blank=True, null=True)

    class Meta:
        ordering = ['organization', 'name']
        unique_together = ('organization', 'name')
        verbose_name = _('mail template')
        verbose_name_plural = _('mail templates')

    def __str__(self):
        return '%s, %s' % (self.organization, self.get_name_display())

    def get_absolute_url(self):
        return reverse('mailtemplate_detail', args=[self.name])

    def has_send_at(self):
        return self.name == 'reminder'


@python_2_unicode_compatible
class StandardReservation(models.Model):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7

    DAYS = (
        (MONDAY, _('Monday')),
        (TUESDAY, _('Tuesday')),
        (WEDNESDAY, _('Wednesday')),
        (THURSDAY, _('Thursday')),
        (FRIDAY, _('Friday')),
        (SATURDAY, _('Saturday')),
        (SUNDAY, _('Sunday')),
    )

    organization = models.ForeignKey('organization.Organization', models.CASCADE, verbose_name=_('organization'))
    start_day = models.SmallIntegerField(verbose_name=_('start day'), choices=DAYS)
    start_time = models.TimeField(verbose_name=_('start time'), default=time(16, 0, 0))
    end_day = models.PositiveSmallIntegerField(verbose_name=_('end day'), choices=DAYS)
    end_time = models.TimeField(verbose_name=_('end time'), default=time(23, 59, 59))
    location = models.ForeignKey('organization.Location', models.CASCADE, verbose_name=_('location'))

    objects = StandardReservationManager()

    class Meta:
        verbose_name = _('standard reservation')
        verbose_name_plural = _('standard reservations')

    def __str__(self):
        return '[%s] %s %s %s' % (
            self.organization,
            self.location,
            _('on'),
            self.get_start_day_display(),
        )

    def clean(self):
        """Check whether the range start is before the range end."""
        from django.core.exceptions import ValidationError

        if self.start_day > self.end_day:
            raise ValidationError(
                _('The start day can not be after the end day.'))

        if self.start_day == self.end_day and self.start_time >= self.end_time:
            raise ValidationError(
                _('The start time can not be after the end time.'))


@python_2_unicode_compatible
class Event(models.Model):
    organizer = models.ForeignKey('organization.Organization', related_name='events', verbose_name=_("organizer"))
    participants = models.ManyToManyField(
        'organization.Organization',
        related_name='participates',
        verbose_name=_("participants"),
    )
    name = models.CharField(_("name"), max_length=128)
    description = models.TextField(_("description"), blank=True)
    starts_at = models.DateTimeField(_("starts at"), db_index=True)
    ends_at = models.DateTimeField(_("ends at"), db_index=True)
    location = models.ManyToManyField('organization.Location', related_name='events', verbose_name=_("location"))
    is_closed = models.BooleanField(
        verbose_name=_("tender enrollment closed"),
        default=False,
        help_text=_(
            'Designates if tenders can sign up for this event.'
        ),
    )
    bartenders = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='BartenderAvailability',
        blank=True,
        verbose_name=_("bartenders"),
    )
    pricegroup = models.ForeignKey('billing.PriceGroup', related_name='events', verbose_name=_("pricegroup"))
    kegs = models.PositiveSmallIntegerField(verbose_name=_("number of kegs"))
    option = models.BooleanField(
        verbose_name=_("option"),
        default=False,
        help_text=_(
            'Designates that this event is not definitive yet.'
        ),
    )
    tender_comments = models.TextField(_("tender comments"), blank=True)
    is_risky = models.BooleanField(
        verbose_name=_("risky"),
        default=False,
        help_text=_(
            'Designates that this event should be marked as risky.'
        ),
    )
    deleted = models.BooleanField(verbose_name=_("deleted"), default=False)

    objects = EventManager()

    class Meta:
        ordering = ['-starts_at']
        verbose_name = _("event")
        verbose_name_plural = _("events")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('event', args=[self.pk])

    @staticmethod
    def conflicting_events(start, end, location=None):
        """Returns a list of all events that conflict. If a location is given,
        the events within the time range at that location is returned. If no
        location is given, all public locations are assumed.
        """

        occuring_at = Event.objects.occuring_at(start, end)
        if location:
            occuring_at = occuring_at.filter(location=location)
        else:
            occuring_at = occuring_at.filter(location__is_public=True)

        return occuring_at

    def copy(self):
        initial = dict([(f.name, getattr(self, f.name))
                        for f in self._meta.fields
                        if f not in self._meta.parents.values()])
        return self.__class__(**initial)

    def get_assigned_bartenders(self):
        # Result could be cached by earlier call or prefetch
        if not hasattr(self, 'bartender_availabilities_assigned'):
            self.bartender_availabilities_assigned = self.bartender_availabilities.filter(
                availability__nature=Availability.ASSIGNED)
        return [x.user for x in self.bartender_availabilities_assigned]

    def can_be_opened(self, user=None):
        if user and user.is_superuser:
            return True

        return (self.starts_at - timedelta(hours=5)) <= timezone.now() <= \
               (self.ends_at + timedelta(hours=24))

    def is_tender(self, user):
        """
        Returns if the given person is a tender for this event.
        """
        if user.is_superuser:
            return True

        return user in self.get_assigned_bartenders()

    def meets_iva_requirement(self):
        # Result could be cached by earlier call or prefetch
        if not hasattr(self, 'bartender_availabilities_iva'):
            self.bartender_availabilities_iva = self.bartender_availabilities.filter(
                Q(availability__nature=Availability.ASSIGNED),
                Q(user__profile__is_iva=True) | Q(user__profile__certificate__approved_at__isnull=False)).exists()

        return bool(self.bartender_availabilities_iva)

    def needs_iva(self):
        return self.kegs > 0


pre_save.connect(notify_tenders, Event)


@python_2_unicode_compatible
class Availability(models.Model):
    ASSIGNED = 'A'
    YES = 'Y'
    MAYBE = 'M'
    NO = 'N'
    NATURES = ((ASSIGNED, _("Assigned")), (YES, _("Yes")), (MAYBE, _("Maybe")), (NO, _("No")))

    organization = models.ForeignKey(
        'organization.Organization',
        related_name='availabilities',
        verbose_name=_("organization"),
    )
    name = models.CharField(_("name"), max_length=32)
    nature = models.CharField(_("nature"), max_length=1, choices=NATURES)

    class Meta:
        ordering = ['organization', 'name']
        unique_together = ('organization', 'name')
        verbose_name = _("availability type")
        verbose_name_plural = _("availability types")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('availability_detail', args=[self.pk])

    def is_assigned(self):
        return self.nature == Availability.ASSIGNED

    def is_yes(self):
        return self.nature == Availability.YES

    def is_maybe(self):
        return self.nature == Availability.MAYBE

    def is_no(self):
        return self.nature == Availability.NO

    def css_class(self):
        if self.is_assigned():
            return 'info'
        if self.is_yes():
            return 'success'
        if self.is_maybe():
            return 'warning'
        if self.is_no():
            return 'danger'


class BartenderAvailability(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("bartender"),
        related_name='bartender_availability_set',
    )
    event = models.ForeignKey(Event, verbose_name=_("event"), related_name='bartender_availabilities')
    availability = models.ForeignKey(Availability, verbose_name=_("availability"), null=True)
    comment = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = _("bartender availability")
        verbose_name_plural = _("bartender availabilities")
        unique_together = ('user', 'event')
