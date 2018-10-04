from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.organization.models import Organization
from apps.scheduling.models import MailTemplate
from utils.mail import mail


class Command(BaseCommand):
    help = 'Send enrollment lapsed mails'

    def handle(self, *args, **options):
        # Filter onganizations with an active enrollment lapsed mail
        organizations = Organization.objects.filter(mailtemplate__name='enrolllapsed', mailtemplate__is_active=True)

        for organization in organizations:
            # Load template and settings
            try:
                mailtemplate = MailTemplate.objects.get(organization=organization, name="enrolllapsed", is_active=True)
            except MailTemplate.DoesNotExist:
                raise CommandError('MailTemplate "enrolllapsed" does not exist for %s' % organization)

            cutoff = timezone.now() + timedelta(minutes=mailtemplate.send_at)
            events = organization.participates.filter(starts_at__gte=timezone.now(),
                                                      starts_at__lte=cutoff,
                                                      is_closed=False).order_by('starts_at', )
            if len(events) == 0:
                continue

            planners = organization.membership_set.filter(is_planner=True, is_active=True)
            for membership in planners:
                user = membership.user
                if not user.email:
                    self.stderr.write('%s heeft geen e-mailadres.\n' % (user,))
                    continue

                mail(settings.EMAIL_FROM, [user], mailtemplate.subject, mailtemplate.template,
                     extraattrs={'events': events})
