from __future__ import unicode_literals

import os

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch.dispatcher import receiver
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from apps.scheduling.models import Availability, BartenderAvailability
from utils.validators import validate_color


@python_2_unicode_compatible
class Location(models.Model):
    name = models.CharField(_('name'), max_length=32)
    is_public = models.BooleanField(_('is public'), default=False)
    prevent_conflicting_events = models.BooleanField(_('prevent conflicting events'), default=True)
    color = models.CharField(_('color'), blank=True, max_length=6, validators=[validate_color])

    class Meta:
        ordering = ['name']
        verbose_name = _('location')
        verbose_name_plural = _('locations')

    def __str__(self):
        return self.name


class AuthenticationData(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        verbose_name=_('user'),
    )
    backend = models.CharField(_('authentication backend'), max_length=50)
    username = models.CharField(_('username'), max_length=50)
    additional_data = models.TextField(_('additional data'), null=True)

    class Meta:
        unique_together = (('backend', 'username'), ('user', 'backend'))


@python_2_unicode_compatible
class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        unique=True,
        verbose_name=_('user'),
    )
    is_iva = models.BooleanField(
        _('has IVA-certificate'),
        default=False,
        help_text=_(
            'Override for an user to indicate IVA rights without uploading a certificate.'
        ),
    )
    is_bhv = models.BooleanField(
        _('has BHV-certificate'),
        default=False,
        help_text=_(
            'Designates that this user has a valid, non-expired BHV (Emergency Response Officer) certificate.'
        ),
    )
    is_foundation_manager = models.BooleanField(
        _('is foundation manager'),
        default=False,
        help_text=_(
            'Designates that this user is manager of the purchasing foundation.'
        ),
    )
    is_external_entity = models.BooleanField(_('is external entity'), default=False)
    birthdate = models.DateField(_('birth date'), null=True)
    current_organization = models.ForeignKey(
        'Organization',
        models.SET_NULL,
        null=True,
        verbose_name=_('current organization'),
    )
    current_language = models.CharField(_('current language'), max_length=5, null=True)
    ical_id = models.CharField(_('iCal identifier'), max_length=36, null=True)

    class Meta:
        ordering = ['user']
        verbose_name = _('profile')
        verbose_name_plural = _('profiles')

    def __str__(self):
        return str(self.user)

    def is_manager(self, organization=None):
        if not organization:
            return self.user.membership_set.filter(is_manager=True).exists()
        else:
            return self.user.membership_set.filter(organization=organization, is_manager=True).exists()

    def is_treasurer(self, organization=None):
        if not organization:
            return self.user.membership_set.filter(is_treasurer=True).exists()
        else:
            return self.user.membership_set.filter(organization=organization,
                                                   is_treasurer=True).exists()

    def is_planner(self, organization=None):
        if not organization:
            return self.user.membership_set.filter(is_planner=True).exists()
        else:
            return self.user.membership_set.filter(organization=organization, is_planner=True).exists()

    def is_tender(self, organization=None):
        if not organization:
            return self.user.membership_set.filter(is_tender=True).exists()
        else:
            return self.user.membership_set.filter(organization=organization, is_tender=True).exists()

    def has_iva(self):
        try:
            approval_date = self.user.certificate.approved_at
        except AttributeError:
            approval_date = None

        return self.is_iva or approval_date

    def tended_count(self):
        return BartenderAvailability.objects.filter(
            user=self.user,
            event__deleted=False,
            event__ends_at__lte=timezone.now(),
            availability__nature=Availability.ASSIGNED,
        ).count()


class PublicOrganizationManager(models.Manager):
    use_for_related_fields = True

    def get_queryset(self):
        return super(PublicOrganizationManager, self).get_queryset().exclude(is_public=False)


@python_2_unicode_compatible
class Organization(models.Model):
    name = models.CharField(_('name'), max_length=32, unique=True)
    slug = models.SlugField(_('slug'), editable=False, unique=True)
    is_public = models.BooleanField(_('is public'), default=False)
    color = models.CharField(verbose_name=_('color'), blank=True, max_length=6, validators=[validate_color])
    assigns_tenders = models.BooleanField(_('assigns tenders'), default=False)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='Membership',
        verbose_name=_('users'),
    )

    objects = models.Manager()
    public_objects = PublicOrganizationManager()

    class Meta:
        ordering = ['name']
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')

    def __str__(self):
        return self.name

    def save(self, force_insert=False, **kwargs):
        self.slug = slugify(self.__str__())
        super(Organization, self).save()


@python_2_unicode_compatible
class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        verbose_name=_('user'),
    )
    organization = models.ForeignKey(
        Organization,
        models.CASCADE,
        verbose_name=_('organization')
    )
    comments = models.TextField(_('comments'), blank=True)
    is_tender = models.BooleanField(_('may tend on events'), default=False)
    is_planner = models.BooleanField(_('may create and modify events'), default=False)
    is_manager = models.BooleanField(_('may create and modify users'), default=False)
    is_treasurer = models.BooleanField(_('may see and manage finances'), default=False)
    is_active = models.BooleanField(_('is currently active'), default=True)
    onscreen_checkout = models.BooleanField(_('visible in on-screen checkout'), default=True)

    class Meta:
        ordering = ('user', 'organization')
        unique_together = ('user', 'organization')
        verbose_name = _('membership')
        verbose_name_plural = _('memberships')

    def __str__(self):
        return _('%(user)s of %(organization)s') % {
            'user': self.user.get_full_name(),
            'organization': self.organization}

    def get_absolute_url(self):
        return reverse('membership', args=[self.pk])

    def tended(self):
        return BartenderAvailability.objects.select_related('event').filter(
            user=self.user,
            event__deleted=False,
            event__ends_at__lte=timezone.now(),
            availability__nature=Availability.ASSIGNED
        ).order_by('-event__starts_at')


def _get_certificate_path(instance, filename):
    path = "certificates"
    ext = os.path.splitext(filename)[1]
    filename = "user" + str(instance.owner_id)
    return os.path.join(path, filename + ext)


@python_2_unicode_compatible
class Certificate(models.Model):
    file = models.FileField(_('certificate'), upload_to=_get_certificate_path)
    uploaded_at = models.DateField(auto_now_add=True, verbose_name=_('uploaded at'))
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        related_name='approved_certificates',
        null=True,
        verbose_name=_('approved by'),
    )
    approved_at = models.DateField(_('approved at'), null=True)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        verbose_name=_('certificate'),
    )

    def __str__(self):
        return '%s %s' % (
            _('IVA certificate of'),
            self.owner.get_full_name(),
        )

    def approve(self, approver):
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()

    approve.alters_data = True

    def decline(self):
        self.delete()

    decline.alters_data = True


@receiver(pre_delete, sender=Certificate)
def certificate_delete(sender, instance, **kwargs):
    instance.file.delete(False)
