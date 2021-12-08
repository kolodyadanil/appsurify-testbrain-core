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
from applications.vcs.models import File as ProjectFile
# from applications.vcs.models import Commit
import time


DEFAULT_REGEX = r'^.*([b|B]ug)s?|([f|F]ix)(es|ed)?|[c|C]lose(s|d)?|([r|R]epair)(s|ed)?|([e|E]rror)s?|([i|I]ssue)s?|([r|R]ectify)s?|([c|C]orrect)(s|ed)?|([b|B]roke)(s|d)?.*$ '
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

    def __init__(self, queryset, grep=DEFAULT_REGEX):
        """
        Constructor.

        :param string path: Path to the Git repository.
        :param integer depth: Depth of the log crawl.
        :param string grep: Case insensitive regular expression used to match
                            commits.

        """
        self._grep = grep
        self._commits = queryset.order_by('timestamp')
        self._matched_commits = queryset.filter(message__iregex=grep).order_by('timestamp')

    def _get_files(self):
        """
        Return a list of matching files.

        :rtype: list of :py:obj:`File` objects

        """

        project_ids = set(list(self._commits.values_list('project_id', flat=True)))
        head_filenames = set(ProjectFile.objects.filter(project_id__in=project_ids).values_list('full_filename', flat=True))

        # print '=' * 50
        # for head_file in head_filenames:
        #     print head_file
        #
        # print '=' * 50

        files = collections.defaultdict(list)

        # print '*' * 50
        # from applications.vcs.models import Commit
        # for commit in Commit.objects.filter(project_id=81).order_by('timestamp'):
        #     print '#: {0}\t{1}'.format(commit.display_id, repr(commit.message))
        # print '*' * 50
        #
        # for commit in Commit.objects.filter(project_id=81).filter(message__iregex=DEFAULT_REGEX).order_by('timestamp'):
        #     print '$: {0}\t{1}'.format(commit.display_id, repr(commit.message))
        # print '*' * 50

        for commit in self._matched_commits.values_list('timestamp', 'files__full_filename'):
            data = commit
            commit_date, filenames = int(time.mktime(data[0].timetuple())), set(data[1:])
            for filename in itertools.ifilter(lambda s: s in head_filenames, filenames):
                files[filename].append(int(commit_date))
                # if filename not in files:
                #     files[filename] = {'timestamp': list(), 'display_id': list()}
                #
                # files[filename]['timestamp'].append(int(commit_date))
                # files[filename]['display_id'].append(commit_display_id)
                #print '{0}\t{1}\t{2}'.format(filename, int(commit_date), commit_display_id)

        return [File(name=k, commit_dates=v) for k, v in files.iteritems()]

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

        # commits = self._commits.order_by('timestamp')
        #
        # if commits:
        #     repo_end = int(time.mktime(commits.last().timestamp.timetuple()) or -1)
        #     repo_start = int(time.mktime(commits.first().timestamp.timetuple()) or -1)
        #     repo_age = repo_end - repo_start
        #
        #     if repo_age == 0:
        #         repo_age = 1
        #
        #     files = self._get_files()
        #
        #     print '#' * 50
        #     for file in files:
        #         print '# {0}\t{1}\t{2}'.format(file.commit_display_ids, file.name, self._get_score(file, repo_start, repo_age))
        #
        #
        #     return sorted([Hotspot(display_id=f.commit_display_ids, filename=f.name, score=self._get_score(f, repo_start, repo_age)) for f in files], key=operator.attrgetter('score'), reverse=True)  #[:len(files) // 10]

        commits = self._matched_commits.order_by('timestamp')
        repo_end = int(time.mktime(commits.last().timestamp.timetuple()) or -1)
        repo_start = int(time.mktime(commits.first().timestamp.timetuple()) or -1)
        repo_age = repo_end - repo_start

        if repo_age == 0:
            repo_age = 1

        files = self._get_files()


        print('#' * 50)
        # for file in files:
        #     print '# {0}\t{1}'.format(file.name, self._get_score(file, repo_start, repo_age))

        for hp in sorted([Hotspot(filename=f.name, score=self._get_score(f, repo_start, repo_age)) for f in files],
                      key=operator.attrgetter("score"),
                      reverse=True):  # [:len(files) // 10]:
            print('%s\t%6.6f' % (hp.filename, hp.score))

        return sorted([Hotspot(filename=f.name, score=self._get_score(f, repo_start, repo_age)) for f in files],
                      key=operator.attrgetter("score"),
                      reverse=True)[:len(files) // 10]
