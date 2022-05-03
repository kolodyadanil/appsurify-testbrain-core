# -*- coding: utf-8 -*-

from hashlib import sha256

from rest_framework.test import APITestCase

from applications.organization.models import Site, Organization
from applications.project.models import Project
from applications.vcs.models import Area, File
from applications.testing.models import Test, TestSuite, TestRun
from django.contrib.auth import get_user_model


class ApiBaseTestClass(APITestCase):
    def setup_db(self):
        self.username = 'test_user'
        self.email = 'testemail@gmail.com'
        self.password = 'test_password_123'
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username=self.username, email=self.email, password=self.password, is_superuser=True, is_staff=True)

        self.organization = Organization.objects.create(name='test_org', site=Site.objects.get_current())
        self.organization.add_user(self.user, True)

        self.project = Project.objects.create(organization=self.organization, name='test_project')
        self.test_suite = TestSuite.objects.create(name='test_testsuite', project=self.project)
        self.test_run = TestRun.objects.create(test_suite=self.test_suite,
                                               name='testrun',
                                               project=self.project,
                                               meta=[])

    def create_area_model_object(self, name, **kwargs):
        args = {
            'project': self.project,
        }
        args.update(kwargs)
        area = Area.objects.create(name=name, **args)
        self.test_run.areas.add(area)
        return area

    def create_test_model_object(self, name, **kwargs):
        args = {
            'project': self.project,
            'type': Test.TYPE_MANUAL,
            'tags': [],
            'lines': [],
            'parameters': [],
            'meta': []
        }
        args.update(kwargs)
        test = Test.objects.create(name=name, **args)
        self.test_suite.tests.add(test)
        self.test_run.tests.add(test)
        return test

    def create_file_trees(self, file_trees):
        result = []
        for file_root in file_trees:
            parent = self.create_file_model_object(filename=file_root['filename'])
            tree_level = [(file_root['children'], parent)]
            for level in tree_level:
                for child in level[0]:
                    file = self.create_file_model_object(filename=child['filename'], parent=level[1])
                    tree_level.append((child['children'], file))
            result.append(parent)
        return result

    def create_file_model_object(self, filename, **kwargs):
        args = {
            'project': self.project,
            'parent': None,
            'sha': sha256(filename).hexdigest()
        }
        args.update(kwargs)
        return File.objects.create(filename=filename, **args)

    @staticmethod
    def get_name_factory(base_name):
        def get_name_generator():
            i = 1
            while True:
                new_name = base_name + '_%d' % i
                i += 1
                yield new_name

        def nested_function(generator):
            def second_nested_func():
                return generator.next()
            return second_nested_func
        return nested_function(get_name_generator())

