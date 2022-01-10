# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import JSONField
from django.utils.translation import ugettext_lazy as _
from applications.testing.models import Defect

import sys
import jira

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

# Building module urlparse deprecated in Python 3.x


User = get_user_model()

severity_mapping = {
    Defect.SEVERITY_TRIVIAL: 'Low',
    Defect.SEVERITY_MINOR: 'Medium',
    Defect.SEVERITY_MAJOR: 'High',
    Defect.SEVERITY_CRITICAL: 'Highest',
}

priority_mapping = {
    'Low': Defect.SEVERITY_TRIVIAL,
    'Medium': Defect.SEVERITY_MINOR,
    'High': Defect.SEVERITY_MAJOR,
    'Highest': Defect.SEVERITY_CRITICAL,
}


def jira_issue_2_extra_data(issue):

    extra_data = {
        'id': issue.id,
        'key': issue.key,
        'summary': issue.fields.summary,
        'description': issue.fields.description,
        'created': issue.fields.created
    }

    if issue.fields.issuetype:
        extra_data['issuetype'] = {
            'id': issue.fields.issuetype.id,
            'name': issue.fields.issuetype.name,
            'description': issue.fields.issuetype.description,
        }

    if issue.fields.status:
        extra_data['status'] = {
            'id': issue.fields.status.id,
            'name': issue.fields.status.name,
            'description': issue.fields.status.description,
        }

    if issue.fields.priority:
        extra_data['priority'] = {
            'id': issue.fields.priority.id,
            'name': issue.fields.priority.name,
        }

    if issue.fields.creator:
        extra_data['creator'] = {
            'key': issue.fields.creator.key,
            'name': issue.fields.creator.name,
            'accountId': issue.fields.creator.accountId,
            'displayName': issue.fields.creator.displayName,
            'active': issue.fields.creator.active,
        }

        if 'emailAddress' in issue.fields.creator.__dict__:
            extra_data['creator']['emailAddress'] = issue.fields.creator.emailAddress

    if issue.fields.assignee:
        extra_data['assignee'] = {
            'key': issue.fields.assignee.key,
            'name': issue.fields.assignee.name,
            'accountId': issue.fields.assignee.accountId,
            'displayName': issue.fields.assignee.displayName,
            'active': issue.fields.assignee.active,
        }

        if 'emailAddress' in issue.fields.assignee.__dict__:
            extra_data['assignee']['emailAddress'] = issue.fields.assignee.emailAddress

    return extra_data


class JiraCredential(models.Model):
    """
    Model for storing personal user credential for access to Jira server.

    """
    organization = models.ForeignKey('organization.Organization', related_name='jira_credentials', blank=False,
                                     null=False, on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='jira_credentials', null=False, on_delete=models.CASCADE)

    url = models.URLField(blank=False, null=False, help_text='Jira server url')
    username = models.CharField(max_length=255, blank=False, null=False, help_text='Jira username')
    token = models.CharField(max_length=255, blank=False, null=False, help_text='Jira personal token')

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        unique_together = ['organization', 'user', 'url', ]
        ordering = ['id', ]
        verbose_name = _('Jira Credential')
        verbose_name_plural = _('Jira Credentials')

    @property
    def domain(self):
        url_fragments = urlparse(self.url)
        return url_fragments.netloc

    @staticmethod
    def test_connection(url, username, token):
        """

        :param url: Jira server url
        :param username: username or email
        :param token: personal api token
        :return: HTTP status code
        """
        ret_code = 200
        try:
            jira_client = jira.JIRA(url, basic_auth=(username, token), max_retries=2)
            jira_client.close()
        except jira.JIRAError as e:
            ret_code = e.status_code
        return ret_code

    def get_projects(self):
        """
        Instance method for get a list of projects to which the user has access.
        :return:
        """
        projects = []
        jira_client = jira.JIRA(self.url, basic_auth=(self.username, self.token))
        projects = map(lambda project: {'id': project.id, 'key': project.key, 'name': project.name},
                       jira_client.projects())
        jira_client.close()
        return projects

    def get_issue_types(self):
        """
        Instance method for get a list of issue_types to which the user has access.
        :return:
        """
        issue_types = []
        jira_client = jira.JIRA(self.url, basic_auth=(self.username, self.token))
        issue_types = map(lambda issue_type: {'id': issue_type.id, 'name': issue_type.name}, jira_client.issue_types())
        jira_client.close()
        return issue_types


class JiraProject(models.Model):
    user = models.ForeignKey(User, related_name='jira_projects', null=False, on_delete=models.CASCADE)

    project = models.OneToOneField('project.Project', related_name='jira_project', null=False,
                                   on_delete=models.CASCADE)

    credential = models.ForeignKey(JiraCredential, related_name='jira_projects', null=False,
                                   on_delete=models.CASCADE)
    extra_data = JSONField(blank=False, null=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        ordering = ['id', ]
        verbose_name = _('Jira Project')
        verbose_name_plural = _('Jira Projects')

    def get_issues(self, *args, **kwargs):
        """
        Search and fetch issue objects from jira server.
        Default criteria from project.extra_data['issue_types']
        :param args:
        :param kwargs:
        :return: issue list
        """

        issues = []

        jira_client = jira.JIRA(
            server=self.credential.url,
            basic_auth=(self.credential.username, self.credential.token)
        )

        issue_filter = 'project = %s' % self.extra_data['project']['name']

        if len(self.extra_data['issue_types']) == 1:
            issue_filter += ' AND type == %s' % self.extra_data['issue_types'][0]['name']

        elif len(self.extra_data['issue_types']) > 1:
            issue_filter += ' AND type IN (%s)' % ','.join([issue['id'] for issue in self.extra_data['issue_types']])

        issues = jira_client.search_issues(issue_filter)
        return issues

    @staticmethod
    def pull_issues(project, force_update=False):
        """
        Fetch all issues and save to database (create defects).
        Default save only new issues. For save all issues set foce_update=True.
        :param project: JiraProject instance
        :param force_update: True/False
        :return:
        """

        issues = []
        new_issues = []
        update_issues = []

        issues = project.get_issues()

        issue_ids = map(lambda x: int(x.id), issues)
        exist_issue_ids = list(project.jira_issues.filter(issue_id__in=issue_ids).values_list('id', flat=True))

        new_issues = filter(lambda x: int(x.id) not in exist_issue_ids, issues)
        for issue in new_issues:
            extra_data = jira_issue_2_extra_data(issue)
            JiraIssue.pull_issue(project, extra_data, force_update=force_update)

        if force_update:
            update_issues = filter(lambda x: int(x.id) in exist_issue_ids, issues)
            for issue in update_issues:
                extra_data = jira_issue_2_extra_data(issue)
                JiraIssue.pull_issue(project, extra_data, force_update=force_update)

        return True

    @staticmethod
    def push_issues(project, force_update=False):
        """

        :param project: JiraProject instance
        :param force_update: True/False
        :return:
        """

        new_defects = project.project.defects.filter(jira_issue__isnull=True)

        for defect in new_defects:
            JiraIssue.push_issue(project, defect)

        if force_update:
            update_defects = project.project.defects.filter(jira_issue__isnull=False)
            for defect in update_defects:
                JiraIssue.push_issue(project, defect)

        return True


class JiraIssue(models.Model):
    defect = models.OneToOneField('testing.Defect', related_name='jira_issue', null=False, on_delete=models.CASCADE)

    jira_project = models.ForeignKey(JiraProject, related_name='jira_issues', null=False, on_delete=models.CASCADE)
    issue_id = models.PositiveIntegerField(blank=False, null=False)

    extra_data = JSONField(blank=False, null=False)

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        verbose_name = _('Jira issue')
        verbose_name_plural = _('Jira issues')
        indexes = [
            models.Index(fields=['-issue_id']),
        ]

    @classmethod
    def pull_issue(cls, jira_project, extra_data, defect=None, force_update=False):
        """
        Populate JiraIssue data and create Defect.

        :param force_update: update defect info if already exist
        :param defect: Optional Defect instance
        :param jira_project: JiraProject instance
        :param extra_data: converted issue to extra_data
        :return: JiraIssue instance
        """

        jira_client = jira.JIRA(
            server=jira_project.credential.url,
            basic_auth=(jira_project.credential.username, jira_project.credential.token)
        )

        try:
            jira_issue = jira_client.issue(extra_data['id'])
        except jira.JIRAError as e:
            if u'Issue does not exist or you do not have permission to see it.' in e.response.json()['errorMessages']:
                jira_issue = jira_client.create_issue(fields=extra_data)
            else:
                jira_issue = None

        extra_data = jira_issue_2_extra_data(jira_issue)
        severity = priority_mapping.get(extra_data['priority']['name'], Defect.SEVERITY_TRIVIAL)

        if defect is None:
            defect, created = Defect.objects.get_or_create(project=jira_project.project, name=extra_data['summary'], defaults={
                'reason': 'Create by Jira',
                'error': extra_data['description'],
                'found_date': extra_data['created'],
                'create_type': Defect.CREATE_TYPE_AUTOMATIC,
                'severity': severity
            })

        if force_update:
            defect.name = extra_data['summary']
            defect.error = extra_data['description']
            defect.found_date = extra_data['created']
            defect.severity = severity
            defect.save()

        try:
            jira_issue = cls.objects.get(defect=defect)
            jira_issue.defect = defect
            jira_issue.jira_project = jira_project
            jira_issue.issue_id = int(extra_data['id'])
            jira_issue.extra_data = extra_data
        except cls.DoesNotExist:
            jira_issue, created = cls.objects.get_or_create(
                defect=defect, jira_project=jira_project, issue_id=int(extra_data['id']), defaults={'extra_data': extra_data})

        return jira_issue

    @classmethod
    def push_issue(cls, jira_project, defect):
        """
        Create or update issue info from defect.
        :param jira_project: JiraProject instance
        :param defect: Defect instance
        :return: issue object
        """

        issue = None

        project_dict = {
            'id': jira_project.extra_data['project']['id']
        }

        issue_type_dict = {
            'name': 'Bug'
        }

        issue_priority_dict = {
            'name': severity_mapping.get(defect.severity)
        }

        issue_dict = {
            'project': project_dict,
            'summary': defect.name,
            'description': defect.error,
            'issuetype': issue_type_dict,
            'priority': issue_priority_dict
        }

        jira_client = jira.JIRA(
            server=jira_project.credential.url,
            basic_auth=(jira_project.credential.username, jira_project.credential.token)
        )

        try:
            issue = cls.objects.get(defect=defect)
            jira_issue = jira_client.issue(issue.issue_id)
            jira_issue.update(fields=issue_dict)
        except cls.DoesNotExist:
            jira_issue = jira_client.create_issue(fields=issue_dict)
            extra_data = jira_issue_2_extra_data(jira_issue)
            # issue = cls.pull_issue(jira_project=jira_project, extra_data=extra_data, defect=defect)
            issue = cls.objects.create(
                defect=defect, jira_project=jira_project, issue_id=int(extra_data['id']), extra_data=extra_data)
        except jira.JIRAError as e:
            if u'Issue does not exist or you do not have permission to see it.' in e.response.json()['errorMessages']:
                jira_issue = jira_client.create_issue(fields=issue_dict)
                extra_data = jira_issue_2_extra_data(jira_issue)
                issue, created = cls.objects.get_or_create(
                    defect=defect, jira_project=jira_project, issue_id=int(extra_data['id']),
                    defaults={'extra_data': extra_data})
            else:
                issue = None

        return issue
