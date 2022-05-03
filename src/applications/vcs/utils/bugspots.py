#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set expandtab tabstop=4 shiftwidth=4 textwidth=79
"""
Bugspots is a Python implementation of the bug prediction algorithm used at
Google and it embed a command-line interface.

"""
from __future__ import division, unicode_literals

import subprocess
import itertools
import collections
import os
import math
import operator
import time
from applications.vcs.models import File as ProjectFile


DEFAULT_REGEX = r'^.*([b|B]ug)s?|([p|P]roblem)s?|([i|I]ssue)s?|([d|D]efect)s?|[w|W]rong|[f|F]ix(es|ed|ing)?|[c|C]lose(s|d)?|([r|R]epair)s?|([e|E]rror)s?|([r|R]ectify)s?|([c|C]orrect)(s|ing)?|([b|B]roke)s?|([s|S]olv)(ed|ing)?.*$'
# DEFAULT_REGEX = r'(?i)(fix(e[sd])?|close[sd]?) #[1-9][0-9]*'


class Bunch(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Hotspot(Bunch):
    """
    Class representing a hot spot.

    This class must be called with the following keyword arguments:

    :py:attr:`filename`: Filename.
    :py:attr:`score`: Score returned by :py:meth:`Bugspots._get_score`.

    """
    pass


class File(Bunch):
    """
    Class representing a file.

    This class must be called with the following keyword arguments:

    :py:attr:`name`: Filename.
    :py:attr:`commit_dates`: List of timestamps.

    """
    pass


class Bugspots(object):
    """Implementation of the bug prediction algorithm used at Google."""

    def __init__(self, project, queryset, grep=DEFAULT_REGEX):
        """
        Constructor.

        :param string path: Path to the Git repository.
        :param integer depth: Depth of the log crawl.
        :param string grep: Case insensitive regular expression used to match
                            commits.

        """
        self._grep = grep

        self._project = project
        self._commits = queryset.order_by('-timestamp')
        self._commits_matched = queryset.filter(message__iregex=grep).order_by('-timestamp')

        self._get_files_cache = None
        self._get_hotspots_cache = None

    @property
    def _get_red_slice(self):
        _count_hotspots = len(self._get_files())
        if _count_hotspots >= 10:
            _count_red_hotspots = 10 * _count_hotspots / 100
        else:
            _count_red_hotspots = 1
        return int(_count_red_hotspots)

    @property
    def _get_orange_slice(self):
        _count_hotspots = len(self._get_files())
        if _count_hotspots >= 10:
            _count_orange_hotspots = 20 * _count_hotspots / 100
        else:
            _count_orange_hotspots = 2
        return int(_count_orange_hotspots)

    @property
    def _get_green_slice(self):
        raise NotImplemented('Don\'t needed value. Use <list>[self._get_red_slice+self._get_orange_slice:]')

    def _get_files(self):
        """
        Return a list of matching files.

        :rtype: list of :py:obj:`File` objects

        """

        if self._get_files_cache is not None:
            return self._get_files_cache

        # project_ids = set(list(self._commits.values_list('project_id', flat=True)))
        # head_filenames = set(ProjectFile.objects.filter(
        #     project_id__in=project_ids).values_list('full_filename', flat=True))
        head_filenames = set(ProjectFile.objects.filter(project=self._project).values_list('full_filename', flat=True))

        files = collections.defaultdict(list)

        for commit in self._commits_matched.values_list('timestamp', 'files__full_filename'):
            data = commit

            commit_date, filenames = int(time.mktime(data[0].timetuple())), set(data[1:])

            for filename in filter(lambda s: s in head_filenames, filenames):
                files[filename].append(int(commit_date))
                # print 'COMMIT: {} \t{}'.format(commit_date, filename)

        self._get_files_cache = [File(name=k, commit_dates=v) for k, v in files.items()]
        return self._get_files_cache

    def _get_score(self, f, repo_start, repo_age):
        """
        Return the score of a given file.

        :param :py:obj:`File` f: A :py:obj:`File` object.
        :param integer repo_start: Timestamp of the first matching commit.
        :param integer repo_age: Timespan of the matching commits in seconds.

        :rtype: float

        """

        def normalize_timestamp(timestamp):
            return (timestamp - repo_start) / repo_age

        return sum(1 / (1 + math.exp(-12 * normalize_timestamp(t) + 12)) for t in f.commit_dates)

    def get_hotspots(self):
        """
        Return the top 10% hot spots.

        :rtype: list of :py:obj:`Hotspot` objects

        """

        if self._get_hotspots_cache is not None:
            return self._get_hotspots_cache

        results = list()

        commits = self._commits

        if commits:
            repo_start = int(time.mktime(commits.first().timestamp.timetuple()) or -1)
            repo_end = int(time.mktime(commits.last().timestamp.timetuple()) or -1)

            repo_age = repo_end - repo_start

            if repo_age == 0:
                repo_age = 1

            files = self._get_files()

            results = sorted([Hotspot(filename=f.name, score=self._get_score(f, repo_start, repo_age)) for f in files], key=operator.attrgetter("score"), reverse=True)  # [:len(files) // 10]

        self._get_hotspots_cache = results

        return self._get_hotspots_cache

    def get_red_hotspots(self):
        return self.get_hotspots()[:self._get_red_slice]

    def get_orange_hotspots(self):
        return self.get_hotspots()[self._get_red_slice:self._get_red_slice+self._get_orange_slice]

    def get_green_hotspots(self):
        return self.get_hotspots()[self._get_red_slice+self._get_orange_slice:]
