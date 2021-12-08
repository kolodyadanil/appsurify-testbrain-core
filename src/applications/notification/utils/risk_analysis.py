# -*- coding: utf-8 -*-
import pytz
import datetime

from django.http import HttpRequest
from django.db.models import Max, QuerySet, Q

from rest_framework.request import Request
from applications.notification.models import Notification
from applications.notification.utils.email import send_notification_email
from applications.project.models import Project

from applications.vcs.models import Commit, Area, File, FileChange
from applications.testing.models import Test, TestRun, Defect


# TODO: Cover this module by unit-tests

def percentage(part, whole):
    if part == 0 or whole == 0:
        result = '%.2f' % (0.0)
    else:
        result = '%.2f' % (100.0 * part / whole)
    return result + '%'


def get_associated_areas_with_dependencies(commits_queryset, excluded_areas=None):
    # type: (QuerySet, list) -> list
    """
    Return all areas with their dependencies associated with commits from 'commits_queryset'

    :param commits_queryset:
    :param excluded_areas:
    :return:
    """
    # Get associated with commits areas
    if isinstance(excluded_areas, (list, tuple)) is True and len(excluded_areas) > 0:
        excluded_ids = [area.id for area in excluded_areas]
        areas_to_process = Area.objects.exclude(id__in=excluded_ids).filter(commits__in=commits_queryset).distinct()
        processed_areas_ids = excluded_ids
    else:
        areas_to_process = Area.objects.filter(commits__in=commits_queryset).distinct()
        processed_areas_ids = list()

    result = list()
    # Get dependencies
    while len(areas_to_process) > 0:
        areas_in_process = areas_to_process
        areas_to_process = Area.objects.filter(
            depended_on__in=areas_in_process
        ).exclude(
            id__in=processed_areas_ids
        ).distinct()

        result += list(areas_in_process[:])
        processed_areas_ids += areas_in_process.values_list('id', flat=True)
    return result


def get_time_savings_info(commits_queryset, excluded_areas):
    # type: (QuerySet, list) -> dict
    """
    Calculate potential time saving by testing areas(and their dependencies) that have relations with high and medium risk
    commits from 'commits_queryset'.

    - Calculate percent of areas(and their dependencies) that have relations with HIGH risk commits from 'commits_queryset' to
    ALL areas(and their dependencies) that also have relations with commits from 'commits_queryset'
    - Calculate percent of areas(and their dependencies) that have relations with HIGH or MEDIUM risk commits from 'commits_queryset' to
    ALL areas(and their dependencies) that also have relations with commits from 'commits_queryset'

    :param commits_queryset:
    :param excluded_areas:
    :return:
    """
    all_areas = get_associated_areas_with_dependencies(commits_queryset, excluded_areas)
    # Get only 'high' and 'medium' risk commits
    high_or_medium_commits = commits_queryset.filter(riskiness__gt=0.25)
    high_or_medium_areas = get_associated_areas_with_dependencies(high_or_medium_commits, excluded_areas)
    # Get only 'high' risk commits
    high_commits = high_or_medium_commits.filter(riskiness__gt=0.5)
    high_areas = get_associated_areas_with_dependencies(high_commits, excluded_areas)
    result = {
        'percentage_time_savings_high_risk_areas': percentage(len(high_areas), len(all_areas)),
        'percentage_time_savings_high_and_medium_risk_areas': percentage(len(high_or_medium_areas), len(all_areas))
    }
    return result


def get_risks_of_commits_related_info(commits_queryset, all_changed_areas, project, excluded_areas):
    # type: (QuerySet, QuerySet, Project, list) -> dict
    """
    Collect common information about number of commit for each risk level, founded defects and grouping areas based
    related commits risk level.

    :param commits_queryset:
    :param all_changed_areas:
    :param project:
    :param excluded_areas:
    :return:
    """
    if isinstance(excluded_areas, (list, tuple)) is True and len(excluded_areas) > 0:
        excluded_ids = [area.id for area in excluded_areas]
    else:
        excluded_ids = []

    # get info about risks of commits
    high_risk_commits = commits_queryset.filter(riskiness__gt=0.5)
    medium_risk_commits = commits_queryset.filter(riskiness__gt=0.25, riskiness__lte=0.5)
    low_risk_commits = commits_queryset.filter(riskiness__lte=0.25)

    # get info about areas by risk commits
    all_project_areas_count = Area.objects.exclude(id__in=excluded_ids).filter(project=project).count()
    high_changed_areas = Area.objects.exclude(
        id__in=excluded_ids
    ).filter(
        commits__in=high_risk_commits
    ).values_list('id', flat=True).distinct()

    medium_changed_areas = Area.objects.exclude(
        Q(id__in=excluded_ids) | Q(id__in=high_changed_areas)
    ).filter(
        commits__in=medium_risk_commits
    ).values_list('id', flat=True).distinct()

    low_changed_areas = Area.objects.exclude(
        Q(id__in=excluded_ids) | Q(id__in=high_changed_areas) | Q(id__in=medium_changed_areas)
    ).filter(
        commits__in=low_risk_commits
    ).values_list('id', flat=True).distinct()

    # get info about founded defects
    all_founded_defects = Defect.objects.filter(caused_by_commits__in=commits_queryset).distinct()
    high_founded_defects = Defect.objects.filter(caused_by_commits__in=high_risk_commits).distinct()
    medium_founded_defects = Defect.objects.filter(caused_by_commits__in=medium_risk_commits).distinct()
    low_founded_defects = Defect.objects.filter(caused_by_commits__in=low_risk_commits).distinct()

    result = {
        'high_risk_commits_count': high_risk_commits.count(),
        'medium_risk_commits_count': medium_risk_commits.count(),
        'low_risk_commit_count': low_risk_commits.count(),

        'all_founded_defects_count': all_founded_defects.count(),
        'high_founded_defects_count': high_founded_defects.count(),
        'medium_founded_defects_count': medium_founded_defects.count(),
        'low_founded_defects_count': low_founded_defects.count(),

        'all_changed_areas_percent': percentage(all_changed_areas.count(), all_project_areas_count),
        'high_changed_areas_percent': percentage(high_changed_areas.count(), all_project_areas_count),
        'medium_changed_areas_percent': percentage(medium_changed_areas.count(), all_project_areas_count),
        'low_changed_areas_percent': percentage(low_changed_areas.count(), all_project_areas_count),
    }
    return result


def perform_analysis_per_each_area(commits_queryset, changed_areas):
    # type: (QuerySet, list) -> list
    """
    Collect information about riskiness per each area

    For each area in 'changed_areas' list we collect next information:
        - name of area;
        - number of high risk commits from 'commits_queryset' that have relation with current area;
        - number of medium risk commits from 'commits_queryset' that have relation with current area;
        - percent of area that was changed on 'commits_queryset'(
            percent_changes_in_area =
                all_files_that_associated_with_area_and_were_changed_on_'commits_queryset' /
                (all_files_associated_with_area * 100)
        )

    :param commits_queryset:
    :param changed_areas:
    :return:
    """
    testruns_prioritization_info = list()
    # TODO: optimize through annotation.
    for area in changed_areas:
        all_files_associated_with_area = area.files.all().count()
        num_files_changed = area.files.filter(commit__in=commits_queryset).distinct().count()
        high_risk_commits_count = commits_queryset.filter(areas=area, riskiness__gt=0.5).count()
        medium_risk_commits_count = commits_queryset.filter(areas=area, riskiness__gt=0.25, riskiness__lte=0.5).count()

        area_info = {
            'name': area.name,
            'high': high_risk_commits_count,
            'medium': medium_risk_commits_count,
            'changes_percentage': percentage(num_files_changed, all_files_associated_with_area),
        }
        testruns_prioritization_info.append(area_info)
    return testruns_prioritization_info


def get_risk_analysis_info(notify, date_range=None):
    # type: (Notification, tuple) -> dict
    """
    Performs risk analysis

    At the first we get our commits queryset based on notification object.
    After that we collect information about potential time savings(see doc. 'get_time_savings_info').
    Next step is collecting statistic about commits riskiness and founded
        defects(see doc. 'get_risks_of_commits_related_info').
    At the end we collect information about riskiness per each area(see doc. 'perform_analysis_per_each_area').

    :param notify:
    :param date_range:
    :return risk_analysis_info:
    """
    risk_analysis_info = dict()

    if not date_range:
        previous_send_datetime = notify.previous_send_datetime.replace(tzinfo=pytz.timezone('UTC'))
        commits_queryset = Commit.objects.filter(created__gt=previous_send_datetime, project=notify.project)
    else:
        if date_range == (None, None):
            raise ValueError("Argument 'date_range' shouldn't have value '%s'" % str(date_range))
        commits_queryset = Commit.objects.filter(created__date__range=date_range, project=notify.project)

    default_area = Area.objects.get(project=notify.project, name='Default Area')
    risk_analysis_info.update(get_time_savings_info(commits_queryset, [default_area]))

    all_changed_areas = Area.objects.exclude(id=default_area.id).filter(commits__in=commits_queryset).distinct()
    risk_analysis_info.update(get_risks_of_commits_related_info(commits_queryset,
                                                                all_changed_areas,
                                                                notify.project,
                                                                [default_area]))
    # get info about prioritization
    risk_analysis_info['prioritization_info'] = perform_analysis_per_each_area(commits_queryset, all_changed_areas)
    return risk_analysis_info


def check_updates(notify, date_range=None):
    # type: (Notification, tuple) -> None
    """
    Check updates for notification

    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return:
    """
    try:
        if notify.period in [Notification.PERIOD_IMMEDIATELY]:
            raise RuntimeError('This function not allowed for notification with this period.')

        email_context = get_risk_analysis_info(notify, date_range)
        email_context['project_name'] = notify.project.name
        email_context['period'] = notify.get_period_display()
        emails = notify.emails.split(',')
        for email in emails:
            email_context['email'] = email
            send_notification_email(notify, context=email_context)

        if not notify.period == Notification.PERIOD_ONE_OFF:
            schedule_last_send = notify.current_datetime.replace(tzinfo=pytz.timezone('UTC'))
            notify.schedule_last_send = schedule_last_send
            notify.save()

    except Exception as e:
        print(e)


def check_risks_analysis_one_off(notify, date_range):
    # type: (Notification, tuple) -> None
    """
        Check updates for risk_analysis notification with one off period
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects
    :return:
    """
    check_updates(notify, date_range)


def check_risks_analysis_immediately(notify):
    # type: (Notification) -> None
    """
        Check updates for risk_analysis notification with immediately period
    :param notify: Notification instance
    :return:
    """
    raise NotImplementedError('This type not allowed for "Risk Analysis" notification')


def check_risks_analysis_daily(notify):
    # type: (Notification) -> None
    """
        Check updates for risk_analysis notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_risks_analysis_weekly(notify):
    # type: (Notification) -> None
    """
        Check updates for risk_analysis notification with weekly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_risks_analysis_fortnightly(notify):
    # type: (Notification) -> None
    """
        Check updates for risk_analysis notification with fortnightly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)
