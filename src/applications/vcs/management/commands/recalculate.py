from datetime import timedelta, datetime

import os
import pytz
import re
import subprocess
from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from applications.vcs.models import Commit, File, FileChange


class Command(BaseCommand):

    def handle(self, *args, **options):
        query_set_commits = Commit.objects.all()
        max_lines = 0.0
        rework_lines = 0.0
        output_re = re.compile(
            '^.+ \((?P<author_name>.*) (?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2}) (?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2}) \+(?P<tz>[0-9]{4}).*',
            re.MULTILINE)
        patch_re = re.compile(
            '^@@ -(?P<start_orig>[0-9]+),(?P<end_orig>[0-9]+) \+(?P<start_new>[0-9]+),(?P<end_new>[0-9]+) @@',
            re.MULTILINE)

        query_set_commits = query_set_commits.prefetch_related('files', 'filechange_set', 'founded_defects')

        for commit in query_set_commits:
            total_number_of_changed = 0
            number_of_chunks = 0
            number_of_files = 0
            list_directories = list()
            file_changes_in_commit = list(
                commit.filechange_set.values('file_id', 'additions', 'deletions', 'status', 'patch'))
            files = [file_change.get('file_id') for file_change in file_changes_in_commit]
            files = list(File.objects.filter(id__in=files).values('id', 'full_filename'))
            for file_change_obj in file_changes_in_commit:
                file_obj = \
                    [file_object for file_object in files if
                     file_object.get('id') == file_change_obj.get('file_id')][0]
                patch = file_change_obj.get('patch')
                total_number_of_changed += file_change_obj.get('additions') + file_change_obj.get('deletions')
                number_of_chunks += len(patch_re.findall(patch))
                number_of_files += 1
                list_directories.append('/'.join(file_obj.get('full_filename').split('/')[:-1]))
                if file_change_obj.get('status') != FileChange.STATUS_MODIFIED:
                    continue
                for i in patch_re.finditer(patch):
                    item = i.groupdict()
                    end_new = int(item.get('end_orig')) + int(item.get('start_orig')) - 1
                    if end_new == -1:
                        continue

                    output_git = self.git(['blame', '{}^'.format(commit.sha), '-L',
                                           '{},{}'.format(item.get('start_orig'), str(end_new)),
                                           file_obj.get('full_filename'), '-w'],
                                          commit.project_id, commit.project.organization.id)
                    if output_git:
                        for j in output_re.finditer(output_git):
                            max_lines += 1
                            output_item = j.groupdict()
                            author_name = output_item.get('author_name')
                            if author_name != commit.author.get('name'):
                                continue
                            date = datetime(year=int(output_item.get('year')), month=int(output_item.get('month')),
                                            day=int(output_item.get('day')), hour=int(output_item.get('hour')),
                                            minute=int(output_item.get('minute')),
                                            second=int(output_item.get('second')),
                                            tzinfo=pytz.UTC)
                            date_delta = commit.timestamp - timedelta(days=14)
                            if date > date_delta:
                                rework_lines += 1
            if max_lines:
                commit.rework = int((rework_lines / max_lines) * 100)
            max_lines = 0.0
            rework_lines = 0.0
            number_of_directories = len(set(list_directories))
            output_value = total_number_of_changed * (
                    (number_of_chunks * 0.5) + (number_of_files - 1) + ((number_of_directories - 1) * 2)) * 2
            commit.output = int(output_value)
            # print commit.output, commit.rework
            commit.save()

    def git(self, args, project_id, organization_id):
        args = ['git'] + args
        prev_path = os.getcwd()
        details = ''
        path = '{}/organizations/{}/projects/{}/'.format(settings.STORAGE_ROOT, organization_id, project_id)
        try:
            os.chdir(path)
        except OSError:
            return details

        git_process = subprocess.Popen(args, stdout=subprocess.PIPE)
        details = git_process.stdout.read()
        details = details.decode("utf-8").strip()
        os.chdir(prev_path)
        return details
