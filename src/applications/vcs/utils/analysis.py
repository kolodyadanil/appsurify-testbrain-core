# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import time
from datetime import datetime, timedelta

import pytz
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Avg, Q

from applications.testing.models import Defect
from applications.vcs.models import Commit
from applications.testing.models import Test
import textdistance

User = get_user_model()


def count_weekday(start_date):
    week = {}
    for i in range((datetime.now(pytz.UTC) - start_date).days):
        day = (start_date + timedelta(days=i + 1)).weekday()
        week[day] = week[day] + 1 if day in week else 1
    return week


def calculate_user_analysis(queryset):
    result_by_hour = {
        'defects': list(),
        'commits': list(),
        'rework': list(),
        'output': list()
    }

    result_by_one_weekday = {
        'commits': list(),
        'output': list()
    }

    result_today = {
        'commits': {'all': 0, 'avg': 0},
        'output': {'all': 0, 'avg': 0},
        'rework': {'all': 0, 'avg': 0},
        'defects': {'all': 0, 'avg': 0}
    }

    result_by_weekday = {
        'defects': list(),
        'commits': list(),
        'rework': list(),
        'output': list()
    }

    result_by_all_day = {
        'defects': list(),
        'commits': list(),
        'rework': list(),
        'output': list()
    }

    all_commits = queryset.order_by('timestamp')
    date_first_commit = all_commits.first().timestamp
    count_week = count_weekday(date_first_commit)

    current_weekday = datetime.now(pytz.UTC).weekday()
    current_day = datetime.now(pytz.UTC).date()
    queryset_defects = queryset.annotate(caused_defects__count=models.Count(
        models.Case(
            models.When(
                models.Q(
                    models.Q(caused_defects__close_type__in=[Defect.CLOSE_TYPE_FIXED,
                                                             Defect.CLOSE_TYPE_WONT_FIX]) | models.Q(
                        caused_defects__close_type__isnull=True)
                ), then=models.F('caused_defects__id')
            )
        )
    ))

    for hour in range(24):
        queryset_by_hour = queryset.filter(timestamp__hour=hour)
        defects = queryset_defects.filter(timestamp__hour=hour)

        result_by_hour['defects'].append(
            avg_per_hour(defects.values('caused_defects__count', 'timestamp'), 'caused_defects__count',
                         date_first_commit))
        current_day_defects = defects.filter(timestamp__contains=current_day)
        result_today['defects']['all'] += sum(
            [x.get('caused_defects__count') for x in list(current_day_defects.values('caused_defects__count'))])

        result_by_hour['commits'].append(
            avg_per_hour(queryset_by_hour.values('id', 'timestamp'), 'commits', date_first_commit))
        commits = queryset_by_hour.filter(timestamp__contains=current_day)
        result_today['commits']['all'] += len(commits)
        commits = queryset_by_hour.filter(timestamp__week_day=current_weekday)
        if count_week.get(current_weekday):
            result_by_one_weekday['commits'].append(len(commits) / count_week.get(current_weekday))
        else:
            result_by_one_weekday['commits'].append(0.0)

        if queryset_by_hour:
            reworks = queryset_by_hour.values('rework', 'timestamp')
            result_by_hour['rework'].append(avg_per_hour(reworks, 'rework', date_first_commit))

            result_by_hour['output'].append(
                avg_per_hour(queryset_by_hour.values('output', 'timestamp'), 'output', date_first_commit))

            output_by_one_weekday = queryset_by_hour.filter(timestamp__week_day=current_weekday).values('output')
            if count_week.get(current_weekday):
                result_by_one_weekday['output'].append(
                    sum([output.get('output') for output in output_by_one_weekday]) / count_week.get(current_weekday))
            else:
                result_by_one_weekday['output'].append(0.0)
        else:
            result_by_hour['rework'].append(0.0)
            result_by_hour['output'].append(0.0)
            result_by_one_weekday['output'].append(0.0)

    try:
        result_today['defects']['all'] = (result_today['defects']['all'] /
                                          queryset_defects.filter(timestamp__contains=current_day).count()) * 100
        if result_today['defects']['all'] > 100:
            result_today['defects']['all'] = 100
    except ZeroDivisionError:
        result_today['defects']['all'] = 0

    result_today['commits']['avg'] = avg_per_hour(queryset.values('timestamp'), 'commits', date_first_commit)

    result_today['output']['all'] = queryset.filter(timestamp__contains=current_day).aggregate(Avg('output')).get(
        'output__avg')

    if result_today['output']['all'] is None:
        result_today['output']['all'] = 0

    result_today['output']['avg'] = avg_per_hour(queryset.values('timestamp', 'output'), 'output', date_first_commit)

    result_today['rework']['all'] = queryset.filter(timestamp__contains=current_day).aggregate(Avg('rework')).get(
        'rework__avg')

    if result_today['rework']['all'] is None:
        result_today['rework']['all'] = 0

    result_today['rework']['avg'] = avg_per_hour(queryset.values('timestamp', 'rework'), 'rework', date_first_commit)

    for weekday in range(7):
        queryset_by_weekday = list(queryset.filter(timestamp__week_day=weekday).values('timestamp', 'rework', 'output'))
        defects = queryset_defects.filter(timestamp__week_day=weekday).values('caused_defects__count', 'timestamp')

        result_by_weekday['defects'].append(avg_per_day(defects, count_week, weekday, 'caused_defects__count'))
        result_by_weekday['commits'].append(avg_per_day(queryset_by_weekday, count_week, weekday, 'commits'))
        result_by_weekday['rework'].append(avg_per_day(queryset_by_weekday, count_week, weekday, 'rework'))
        result_by_weekday['output'].append(avg_per_day(queryset_by_weekday, count_week, weekday, 'output'))

    defect_by_all_day = dict()
    for defect_commit in list(queryset_defects.values('caused_defects__count', 'timestamp')):
        if defect_commit.get('timestamp').date() in defect_by_all_day.keys():
            defect_by_all_day[defect_commit.get('timestamp').date()] += defect_commit.get('caused_defects__count')
        else:
            defect_by_all_day[defect_commit.get('timestamp').date()] = defect_commit.get('caused_defects__count')
    commit_by_all_day = dict()
    output_by_all_day = dict()
    rework_by_all_day = dict()
    for commit in list(queryset.values('id', 'output', 'rework', 'timestamp')):
        if commit.get('timestamp').date() in commit_by_all_day.keys():
            commit_by_all_day[commit.get('timestamp').date()] += 1
            output_by_all_day[commit.get('timestamp').date()] += commit.get('output')
            rework_by_all_day[commit.get('timestamp').date()] += commit.get('rework')
        else:
            commit_by_all_day[commit.get('timestamp').date()] = 1
            output_by_all_day[commit.get('timestamp').date()] = commit.get('output')
            rework_by_all_day[commit.get('timestamp').date()] = commit.get('rework')

    result_by_all_day['commits'] = [{'value': value, 'timestamp': time.mktime(key.timetuple())} for key, value in
                                    commit_by_all_day.items()]
    result_by_all_day['defects'] = [{'value': value, 'timestamp': time.mktime(key.timetuple())} for key, value in
                                    defect_by_all_day.items()]
    result_by_all_day['output'] = [{'value': value, 'timestamp': time.mktime(key.timetuple())} for key, value in
                                   output_by_all_day.items()]
    result_by_all_day['rework'] = [{'value': value / commit_by_all_day[key], 'timestamp': time.mktime(key.timetuple())}
                                   for key, value in rework_by_all_day.items()]

    result = {
        'hour': result_by_hour,
        'one_weekday': result_by_one_weekday,
        'today': result_today,
        'weekday': result_by_weekday,
        'all_day': result_by_all_day,
    }
    return result


def calculate_user_analysis_by_range(queryset, timestamp__range):
    timestamp__range = timestamp__range.get('timestamp__range')

    result_range = {
        'output': 0,
        'commits': 0,
        'defects': 0,
        'rework': 0
    }
    queryset_defects = queryset.exclude(caused_defects__isnull=True)
    count_days = (timestamp__range[1] - timestamp__range[0]).days + 1
    result_range['output'] = avg_per_range(queryset.values('output', 'timestamp'), 'output', timestamp__range)
    result_range['commits'] = float(queryset.count()) / count_days
    result_range['defects'] = float(
                        queryset_defects.count()) / queryset.count() * 100 if queryset.count() > 0 else 0
    result_range['rework'] = avg_per_range(queryset.values('rework', 'timestamp'), 'rework', timestamp__range)

    return result_range


def avg(list_item, item_name):
    if item_name == 'output':
        return sum([item.get(item_name) for item in list_item])
    return sum([item.get(item_name) for item in list_item]) / float(len(list_item))


def avg_today(list_items, item_name):
    if len(list_items):
        if item_name == 'commits':
            return len(list_items) / 24.0
        sorted_dict = dict()
        for item in list_items:
            if item['timestamp'].date() not in sorted_dict.keys():
                sorted_dict[item['timestamp'].date()] = []
            sorted_dict[item['timestamp'].date()].append(item)

        avg_dict = {key: avg(values, item_name) for key, values in sorted_dict.items()}
        total_value = sum(avg_dict.values())
        if item_name == 'caused_defects__count':
            total_value *= 100
            if total_value > 100:
                total_value = 100
            return total_value
        avg_value = total_value / 24
    else:
        total_value = 0
        avg_value = total_value / 24
    return avg_value


def avg_per_range(list_items, item_name, date_range):
    count_days = (date_range[1] - date_range[0]).days + 1

    if len(list_items):
        if item_name == 'commits':
            return len(list_items) / float(count_days)
        sorted_dict = dict()
        for item in list_items:
            if item['timestamp'].date() not in sorted_dict.keys():
                sorted_dict[item['timestamp'].date()] = []
            sorted_dict[item['timestamp'].date()].append(item)

        avg_dict = {key: avg(values, item_name) for key, values in sorted_dict.items()}
        total_value = sum(avg_dict.values())
        if item_name == 'caused_defects__count' or item_name == 'rework':
            if item_name == 'caused_defects__count':
                total_value *= 100
            if total_value > 100:
                total_value = 100
            return total_value
        avg_value = total_value / count_days
    else:
        total_value = 0
        avg_value = total_value / count_days
    return avg_value


def avg_per_hour(list_items, item_name, date_first_commit):
    count_days = (datetime.now(pytz.UTC) - date_first_commit).days + 1

    if len(list_items):
        if item_name == 'commits':
            return len(list_items) / float(count_days)
        sorted_dict = dict()
        for item in list_items:
            if item['timestamp'].hour not in sorted_dict.keys():
                sorted_dict[item['timestamp'].hour] = []
            sorted_dict[item['timestamp'].hour].append(item)

        avg_dict = {key: avg(values, item_name) for key, values in sorted_dict.items()}
        total_value = sum(avg_dict.values())
        if item_name == 'caused_defects__count':
            total_value *= 100
            if total_value > 100:
                total_value = 100
            return total_value
        avg_value = total_value / count_days
    else:
        total_value = 0
        avg_value = total_value / count_days
    return avg_value


def avg_per_day(list_items, count_day, day_of_week, item_name):
    if len(list_items):
        if item_name == 'commits':
            return len(list_items) / float(count_day.get(day_of_week))

        sorted_dict = dict()
        for item in list_items:
            if item['timestamp'].hour not in sorted_dict.keys():
                sorted_dict[item['timestamp'].hour] = []
            sorted_dict[item['timestamp'].hour].append(item)

        avg_dict = {key: avg(values, item_name) for key, values in sorted_dict.items()}
        total_value = sum(avg_dict.values())
        if item_name == 'caused_defects__count':
            total_value *= 100
            if total_value > 100:
                total_value = 100
            return total_value
        avg_value = total_value / count_day.get(day_of_week)
    else:
        total_value = 0
        avg_value = total_value / count_day.get(day_of_week)
    return avg_value


def calculate_similar_by_commit(queryset, commit_id, percent=0):
    result = {
        'similar_areas': [],
        'similar_folders': [],
        'similar_files': [],
        'tests': [],
    }

    calculate_similars = {
        'key': 'value'
    }

    commit = Commit.objects.get(pk=commit_id)
    result['similar_areas'] = commit.areas.filter(~Q(name='Default Area')).values_list('name', flat=True)[:5]
    files = commit.files.all()[:5]

    for file in files:
        result['similar_files'].append(file.full_filename)
        full_folder = file.full_filename.replace('/' + file.filename, '')
        array_foder = full_folder.split('/')
        result['similar_folders'].append(array_foder[len(array_foder) - 1])

    for area in result['similar_areas']:
        tests = Test.objects.filter(area__name=area, project__pk=commit.project.id)
        if len(tests) > 0:
            for test in tests:
                value = similarity(test.name, area)
                if value >= 0.7:
                    calculate_similars[test.id] = value

    result['tests'] = sorted(calculate_similars, key=calculate_similars.get, reverse=True)[:6][1:]

    return result


def similarity(value1, value2):
    value1 = value1.lower()
    value2 = value2.lower()

    return textdistance.damerau_levenshtein.normalized_similarity(value1, value2) +\
        textdistance.sorensen_dice.normalized_similarity(value1, value2) +\
        textdistance.lcsseq.normalized_similarity(value1, value2)
