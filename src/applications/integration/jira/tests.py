# -*- coding: utf-8 -*-

from django.test import TestCase
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model

from applications.integration.jira.models import *
from applications.organization.utils import *
from applications.project.models import *
from applications.testing.models import *
import jira


User = get_user_model()


class TestModel(TestCase):

    def setUp(self):
        site = Site.objects.get(id=1)
        self.user = User.objects.create_user(username='User', email='user@testmail.com', password='')
        self.organization = create_organization(
            self.user, u'Appsurify', slug='appsurify',
            is_active=True, org_defaults={'site': site},
            org_user_defaults={'is_admin': True}
        )

        self.project = Project.objects.create(organization=self.organization, name='Demo', slug='demo')
        self.project.add_user(self.user, is_admin=True)

        self.jira_username = "ar.demidenko@gmail.com"
        self.jira_token = "sYuY0V89IDBboTTFqS2sB4A6"
        self.jira_url = "https://appsurify.atlassian.net"

    def test_00_validate_credentials(self):
        jira_credentials = JiraCredential.objects.create(
            url=self.jira_url, username=self.jira_username,
            token=self.jira_token, organization=self.organization,
            user=self.user
        )

        _fail = 200

        try:
            j = jira.JIRA(server=jira_credentials.url,
                          basic_auth=(jira_credentials.username, jira_credentials.token), max_retries=1)
            j.close()
        except jira.JIRAError as e:
            if e.status_code == 401:
                _fail = 401

        self.assertEqual(_fail, 200, msg='Jira client dont raised exception if credential correct.')

    def test_01_fetch_projects(self):
        jira_credentials = JiraCredential.objects.create(
            url=self.jira_url, username=self.jira_username,
            token=self.jira_token, organization=self.organization,
            user=self.user
        )

        projects = jira_credentials.get_projects()

        self.assertIsInstance(projects, list)
        self.assertIsNotNone(projects)

    def test_02_fetch_types(self):
        jira_credentials = JiraCredential.objects.create(
            url=self.jira_url, username=self.jira_username,
            token=self.jira_token, organization=self.organization,
            user=self.user
        )

        issue_types = jira_credentials.get_issue_types()

        self.assertIsInstance(issue_types, list)
        self.assertIsNotNone(issue_types)

    def test_03_create_jira_project_link(self):
        jira_credentials = JiraCredential.objects.create(
            url=self.jira_url, username=self.jira_username,
            token=self.jira_token, organization=self.organization,
            user=self.user
        )
        jira_projects = jira_credentials.get_projects()
        issue_types = jira_credentials.get_issue_types()

        jira_project = {}
        jira_project = next(filter(lambda x: x['name'] == 'Appsurify', jira_projects).__iter__(), None)
        jira_issue_types = filter(lambda x: x['name'] in ['Bug', 'Epic'], issue_types)

        project = JiraProject(project=self.project, user=self.user, credential=jira_credentials, extra_data={
            "project": {
                "id": jira_project['id'],
                "key": jira_project['key'],
                "name": jira_project['name']
            },
            "issue_types": [issue_type for issue_type in jira_issue_types]
        })
        project.save()

        self.assertDictEqual(project.extra_data, {'project': {'id': u'10000', 'key': u'AP', 'name': u'Appsurify'}, 'issue_types': [{u'id': u'10004', u'name': u'Bug'}, {u'id': u'10000', u'name': u'Epic'}]})

        self.assertEqual(self.project.jira_project, project)

    def test_04_install_webhook(self):
        self.skipTest('Deprecated feature.')

    def test_05_fetch_issues_by_filter(self):
        jira_credentials = JiraCredential.objects.create(
            url=self.jira_url, username=self.jira_username,
            token=self.jira_token, organization=self.organization,
            user=self.user
        )
        jira_projects = jira_credentials.get_projects()
        issue_types = jira_credentials.get_issue_types()

        jira_project = {}
        jira_project = next(filter(lambda x: x['name'] == 'Appsurify', jira_projects).__iter__(), None)
        jira_issue_types = filter(lambda x: x['name'] in ['Bug', 'Epic'], issue_types)

        j_project = JiraProject(project=self.project, user=self.user, credential=jira_credentials, extra_data={
            "project": {
                "id": jira_project['id'],
                "key": jira_project['key'],
                "name": jira_project['name']
            },
            "issue_types": [issue_type for issue_type in jira_issue_types]
        })
        j_project.save()

        issues = j_project.get_issues()

        self.assertEqual(len(issues), 2)

        # Filter exists issues
        issue_ids = map(lambda x: int(x.id), issues)
        exist_issue_ids = list(JiraIssue.objects.filter(jira_project=j_project, issue_id__in=issue_ids).values_list('id', flat=True))
        issues = filter(lambda x: int(x.id) not in exist_issue_ids, issues)

        for issue in issues:
            JiraIssue.pull_issue(j_project, jira_issue_2_extra_data(issue))

        jira_issues_qs = JiraIssue.objects.filter(jira_project=j_project).count()
        self.assertEqual(jira_issues_qs, len(issues))

        defect_qs = Defect.objects.filter(project=j_project.project).count()
        self.assertEqual(defect_qs, len(issues))

    def test_06_fetch_issues_by_project(self):

        jira_credentials = JiraCredential.objects.create(
            url=self.jira_url, username=self.jira_username,
            token=self.jira_token, organization=self.organization,
            user=self.user
        )

        jira_projects = jira_credentials.get_projects()
        issue_types = jira_credentials.get_issue_types()

        jira_project = {}
        jira_project = next(filter(lambda x: x['name'] == 'Appsurify', jira_projects).__iter__(), None)
        jira_issue_types = filter(lambda x: x['name'] in ['Bug', 'Epic'], issue_types)

        j_project = JiraProject(project=self.project, user=self.user, credential=jira_credentials, extra_data={
            "project": {
                "id": jira_project['id'],
                "key": jira_project['key'],
                "name": jira_project['name']
            },
            "issue_types": [issue_type for issue_type in jira_issue_types]
        })
        j_project.save()

        issues = JiraProject.pull_issues(j_project, force_update=True)

        self.assertEqual(issues, True)

        jira_issues_qs = JiraIssue.objects.filter(jira_project=j_project).count()
        self.assertEqual(jira_issues_qs, 7)

        defect_qs = Defect.objects.filter(project=j_project.project).count()
        self.assertEqual(defect_qs, 7)

    def test_07_call_test_credential(self):

        valid_result = JiraCredential.test_connection(
            self.jira_url,
            self.jira_username,
            self.jira_token
        )

        self.assertEqual(valid_result, 200)

        invalid_result = JiraCredential.test_connection(
            self.jira_url,
            self.jira_username,
            self.jira_token + '_invalid'
        )

        self.assertEqual(invalid_result, 401)

    def test_08_push_issue_to_server(self):
        # self.skipTest('Planing scenario.')
        jira_credentials = JiraCredential.objects.create(
            url=self.jira_url, username=self.jira_username,
            token=self.jira_token, organization=self.organization,
            user=self.user
        )

        jira_projects = jira_credentials.get_projects()
        issue_types = jira_credentials.get_issue_types()

        jira_project = {}
        jira_project = next(filter(lambda x: x['name'] == 'Appsurify', jira_projects).__iter__(), None)
        jira_issue_types = filter(lambda x: x['name'] in ['Bug', 'Epic'], issue_types)

        j_project = JiraProject(project=self.project, user=self.user, credential=jira_credentials, extra_data={
            "project": {
                "id": jira_project['id'],
                "key": jira_project['key'],
                "name": jira_project['name']
            },
            "issue_types": [issue_type for issue_type in jira_issue_types]
        })
        j_project.save()

        defect = Defect.objects.create(
            project=self.project,
            name='DefectName2',
            reason='Manualy jira test',
            error='DefectError2',
            found_date=timezone.now(),
            create_type=Defect.CREATE_TYPE_MANUAL,
            severity=Defect.SEVERITY_CRITICAL,
            status=Defect.STATUS_NEW
        )

        issue = JiraIssue.push_issue(j_project, defect)
        self.assertIsNotNone(issue)
