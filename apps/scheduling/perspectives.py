import datetime
import json

from django.db.models.query import Prefetch
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.organization.models import Location, Membership
from utils.auth.decorators import tender_required, planner_required

from .models import Availability, BartenderAvailability, Event


@tender_required
def bartender(request):
    events = Event.objects.filter(ends_at__gte=timezone.now(),
                                  deleted=False,
                                  bartender_availabilities__availability__nature=Availability.ASSIGNED,
                                  bartender_availabilities__user=request.user).order_by('starts_at')

    return render(request, 'scheduling/overview_bartender.html', locals())


@planner_required
def matrix(request):
    events = Event.objects \
        .select_related() \
        .prefetch_related(
            Prefetch('bartender_availabilities',
                     queryset=BartenderAvailability.objects.select_related('user', 'event', 'availability'))
        ) \
        .filter(ends_at__gte=timezone.now(),
                participants=request.organization,
                deleted=False) \
        .order_by('starts_at')

    tenders_list = Membership.objects \
        .select_related('user') \
        .filter(organization=request.organization,
                is_tender=True,
                is_active=True) \
        .order_by("user__first_name")

    year_ago = timezone.now() - datetime.timedelta(days=365)
    tenders = []
    for tender in tenders_list:
        tender_availabilities_comments = [
            next(((a.availability, a.comment) for a in e.bartender_availabilities.all() if a.user == tender.user), (None, None)) for e in
            events]
        tender_events = [{'event': event, 'availability': availability, 'comment': comment} for event, availability, comment in
                         zip(events, *zip(*tender_availabilities_comments))]
        tended = [a.event for a in tender.tended()]
        tended_year = len([e for e in tended if e.starts_at >= year_ago])
        tenders.append({
            'tender': tender,
            'tended': len(tended),
            'tended_year': tended_year,
            'last_tended': tended[0] if tended else None,
            'events': tender_events
        })

    return render(request, 'scheduling/overview_matrix.html', locals())


def calendar(request):
    is_planner = request.user.is_authenticated() and request.organization and request.user.profile.is_planner(
        request.organization)
    return render(request, 'scheduling/overview_calendar.html', locals())


def calendar_fetch(request):
    if not request.is_ajax():
        return redirect(calendar)

    tz = timezone.get_current_timezone()
    from_time = datetime.datetime.fromtimestamp(float(request.GET.get('start')))
    till_time = datetime.datetime.fromtimestamp(float(request.GET.get('end')))
    data = []

    for event in Event.objects.filter(ends_at__gte=from_time,
                                      starts_at__lte=till_time).prefetch_related('location'):
        # Default color
        color = '#888888'

        try:
            location = event.location.get()
            if location.color:
                color = '#{}'.format(location.color)
        except Location.DoesNotExist:
            # No location, use default color
            pass
        except Location.MultipleObjectsReturned:
            # Multiple locations, use default color
            pass

        data.append({
            'id': event.pk,
            'title': event.name,
            'start': event.starts_at.astimezone(tz).isoformat(),
            'end': event.ends_at.astimezone(tz).isoformat(),
            'color': color,
            'organizers': ', '.join(map(lambda x: x.name,
                                        event.participants.all())),
            'location': ', '.join(map(lambda x: x.name, event.location.all())),
            'tenders': ', '.join(map(lambda x: x.first_name,
                                     event.get_assigned_bartenders())) or '<i>geen</i>',
            'canEdit': request.user.profile.is_planner(event.organizer) if hasattr(request.user, 'profile') else False,
            'editUrl': event.get_absolute_url()
        })

    return HttpResponse(json.dumps(data), content_type='application/json')
