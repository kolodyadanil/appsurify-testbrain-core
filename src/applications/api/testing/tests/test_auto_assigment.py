# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from rest_framework import status
from django.urls import reverse

from applications.api.common.tests import ApiBaseTestClass
from applications.vcs.models import Area, File
from applications.api.testing.stop_words import stop_words


class GetPredictedAreasTestApi(ApiBaseTestClass):
    def setUp(self):
        self.setup_db()

    def test_matched_areas(self):
        matched_area_name = 'test_name_1'
        matched_class_name_area_name = 'test_class_name_1'
        self.create_area_model_object(name=matched_area_name)
        self.create_area_model_object(name=matched_class_name_area_name)
        test = self.create_test_model_object(name=matched_area_name, class_name=matched_class_name_area_name)

        self.client.login(username=self.username, password=self.password)
        response = self.client.get('/api/tests/',
                                   data={'test_suite': self.test_suite.id, 'project': self.project.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        result = response.data['results'][0]
        self.assertEqual(result['id'], test.id)

        predicted_areas = set([x['name'] for x in result['predicted_areas']])
        expected_areas = {test.area.name, matched_area_name, matched_class_name_area_name}
        self.assertEqual(predicted_areas, expected_areas)

    def test_matched_and_associated_areas(self):
        matched_area_name = 'test_matched_area_name'
        associated_area_name = 'test_associated_area_name'
        self.create_area_model_object(name=matched_area_name)
        associated_area = self.create_area_model_object(name=associated_area_name)

        test_name = '.'.join([associated_area_name, matched_area_name])
        test = self.create_test_model_object(name=test_name)
        test.associated_areas.add(associated_area)

        self.client.login(username=self.username, password=self.password)
        response = self.client.get('/api/tests/',
                                   data={'test_suite': self.test_suite.id, 'project': self.project.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        result = response.data['results'][0]
        self.assertEqual(result['id'], test.id)

        predicted_areas = set([x['name'] for x in result['predicted_areas']])
        expected_areas = {test.area.name, matched_area_name, associated_area_name}
        self.assertEqual(predicted_areas, expected_areas)

    def test_match_words_normalization(self):
        assertions_msgs = []
        words_pairs = [('123', '123'),
                       ('fox', 'foxes'),
                       ('foxes', 'fox'),
                       ('test', 'tests'),
                       ('tests', 'test'),
                       ('x', 'x'),
                       ('?', '?'),
                       ('@', '@'),
                       ('woman', 'women'),
                       ('women', 'woman'),
                       ('es', 'es'),
                       ('ses', 'ses'),
                       ('ies', 'ies'),
                       ]
        for test_name, matched_area_name in words_pairs:
            if test_name == '' or matched_area_name == '':
                continue

            self.create_area_model_object(name=matched_area_name)
            test = self.create_test_model_object(name=test_name)

            self.client.login(username=self.username, password=self.password)
            response = self.client.get('/api/tests/',
                                       data={'test_suite': self.test_suite.id, 'project': self.project.id})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            result = [x for x in response.data['results'] if x['id'] == test.id]
            if len(result) != 1:
                while response.data['next'] is not None and len(result) != 1:
                    response = self.client.get(response.data['next'])
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    result = [x for x in response.data['results'] if x['id'] == test.id]
            self.assertEqual(len(result), 1)
            result = result[0]

            matched_areas = [x['name'] for x in result['predicted_areas'] if x['name'] in [matched_area_name]]
            if len(matched_areas) == 0:
                assertions_msgs.append("\n'test_name: %s | 'expected_area_name': %s" % (test_name, matched_area_name))

        assert_flag = True if len(assertions_msgs) > 0 else False
        self.assertFalse(assert_flag, ''.join(assertions_msgs))

    def test_ignoring_stop_words(self):
        assertions_msgs = []
        for stop_word in stop_words:
            matched_area_name = test_name = stop_word
            self.create_area_model_object(name=matched_area_name)
            test = self.create_test_model_object(name=test_name)

            self.client.login(username=self.username, password=self.password)
            response = self.client.get('/api/tests/',
                                       data={'test_suite': self.test_suite.id, 'project': self.project.id})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            result = [x for x in response.data['results'] if x['id'] == test.id]
            if len(result) != 1:
                while response.data['next'] is not None and len(result) != 1:
                    response = self.client.get(response.data['next'])
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    result = [x for x in response.data['results'] if x['id'] == test.id]
            self.assertEqual(len(result), 1)
            result = result[0]

            matched_areas = [x['name'] for x in result['predicted_areas'] if x['name'] in [matched_area_name]]
            if len(matched_areas) != 0:
                assertions_msgs.append("\n'stop_word': %s | 'matched_areas': %s" % (stop_word, matched_areas))

        assert_flag = True if len(assertions_msgs) > 0 else False
        self.assertFalse(assert_flag, ''.join(assertions_msgs))


class GetPredictedFilesTestApi(ApiBaseTestClass):
    def setUp(self):
        self.setup_db()

    def test_matched_files(self):
        test_matched_file = 'test_name_1'
        test_matched_folder = 'test_folder_name_1'
        file_tree = [{'filename': 'root',
                      'children': [{'filename': 'file_1',
                                    'children': []
                                    },
                                   {'filename': test_matched_folder,
                                    'children': [
                                        {'filename': test_matched_file,
                                         'children': []
                                         }]}]}]
        self.create_file_trees(file_tree)
        test_name = ' '.join([test_matched_folder, test_matched_file])
        test = self.create_test_model_object(name=test_name)

        self.client.login(username=self.username, password=self.password)
        response = self.client.get('/api/tests/',
                                   data={'test_suite': self.test_suite.id, 'project': self.project.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        result = response.data['results'][0]
        self.assertEqual(result['id'], test.id)

        predicted_files = set([x['filename'] for x in result['predicted_files']])
        expected_file_names = {test_matched_file, test_matched_folder}
        self.assertEqual(predicted_files, expected_file_names)

    def test_matched_and_associated_files(self):
        matched_file_name = 'test_file_name_1'
        associated_file_name = 'test_file_name_2'
        test_name = 'test'
        file_tree = [{'filename': 'root',
                      'children': [{'filename': associated_file_name,
                                    'children': []
                                    },
                                   {'filename': 'folder_1',
                                    'children': [
                                        {'filename': matched_file_name,
                                         'children': []
                                         }]}]}]
        self.create_file_trees(file_tree)
        associated_file = File.objects.get(filename=associated_file_name, level=1)
        test = self.create_test_model_object(name=test_name)
        test.associated_files.add(associated_file)

        self.client.login(username=self.username, password=self.password)
        response = self.client.get('/api/tests/',
                                   data={'test_suite': self.test_suite.id, 'project': self.project.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        result = response.data['results'][0]
        self.assertEqual(result['id'], test.id)

        predicted_files = set([x['filename'] for x in result['predicted_files']])
        expected_file_names = {matched_file_name, associated_file_name}
        self.assertEqual(predicted_files, expected_file_names)

    def test_match_words_normalization(self):
        assertions_msgs = []
        words_pairs = [('123', '123'),
                       ('fox', 'foxes'),
                       ('foxes', 'fox'),
                       ('test', 'tests'),
                       ('tests', 'test'),
                       ('x', 'x'),
                       ('?', '?'),
                       ('@', '@'),
                       ('woman', 'women'),
                       ('women', 'woman'),
                       ('es', 'es'),
                       ('ses', 'ses'),
                       ('ies', 'ies'),
                       ]
        for test_name, matched_filename in words_pairs:
            if test_name == '' or matched_filename == '':
                continue

            file_tree = [{'filename': 'root',
                          'children': [{'filename': matched_filename,
                                        'children': []}]}]
            self.create_file_trees(file_tree)
            test = self.create_test_model_object(name=test_name)

            self.client.login(username=self.username, password=self.password)
            response = self.client.get('/api/tests/',
                                       data={'test_suite': self.test_suite.id, 'project': self.project.id})
            result = [x for x in response.data['results'] if x['id'] == test.id]
            if len(result) != 1:
                while response.data['next'] is not None and len(result) != 1:
                    response = self.client.get(response.data['next'])
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    result = [x for x in response.data['results'] if x['id'] == test.id]
            self.assertEqual(len(result), 1)
            result = result[0]

            matched_areas = [x['filename'] for x in result['predicted_files'] if x['filename'] in [matched_filename]]
            if len(matched_areas) == 0:
                assertions_msgs.append("\n'test_name: %s | 'expected_filename': %s" % (test_name, matched_filename))

        assert_flag = True if len(assertions_msgs) > 0 else False
        self.assertFalse(assert_flag, ''.join(assertions_msgs))

    def test_ignoring_stop_words(self):
        assertions_msgs = []
        for stop_word in stop_words:
            file_tree = [{'filename': 'root',
                          'children': [{'filename': stop_word,
                                        'children': []}]}]
            self.create_file_trees(file_tree)
            test = self.create_test_model_object(name=stop_word)

            self.client.login(username=self.username, password=self.password)
            response = self.client.get('/api/tests/',
                                       data={'test_suite': self.test_suite.id, 'project': self.project.id})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            result = [x for x in response.data['results'] if x['id'] == test.id]
            if len(result) != 1:
                while response.data['next'] is not None and len(result) != 1:
                    response = self.client.get(response.data['next'])
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    result = [x for x in response.data['results'] if x['id'] == test.id]
            self.assertEqual(len(result), 1)
            result = result[0]

            matched_files = [x['filename'] for x in result['predicted_files'] if x['filename'] in [stop_word]]
            if len(matched_files) != 0:
                assertions_msgs.append("\n'stop_word: %s | 'matched_files': %s" % (stop_word, matched_files))

        assert_flag = True if len(assertions_msgs) > 0 else False
        self.assertFalse(assert_flag, ''.join(assertions_msgs))


class TestAutoAssignApi(ApiBaseTestClass):
    def setUp(self):
        self.setup_db()

    def test_auto_assign_areas(self):
        matched_area_name = 'test_name_1'
        area = self.create_area_model_object(name=matched_area_name)

        test_name = matched_area_name
        test = self.create_test_model_object(name=test_name)

        self.client.force_login(self.user)
        response = self.client.post(reverse('test-auto-associate-tests'),
                                    json.dumps({'tests': [test.id]}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)

        expected_associated_areas = {area.id, test.area.id}
        associated_areas = set(test.associated_areas.all().values_list('id', flat=True))
        self.assertEqual(associated_areas, expected_associated_areas)

    def test_auto_assign_files_root_node_var(self):
        file_names = {'root': 'test_folder_name_1',
                      'file_1': 'test_filename_1',
                      'file_2': 'test_filename_2',
                      'folder_1': 'test_folder_1'}

        file_tree = [{'filename': file_names['root'],  # <= matched by name
                      'children': [{'filename': file_names['file_1'],
                                    'children': []
                                    },
                                   {'filename': file_names['folder_1'],
                                    'children': [
                                        {'filename': file_names['file_2'],
                                         'children': []
                                         }]}]}]
        self.create_file_trees(file_tree)
        test_name = file_names['root']
        test = self.create_test_model_object(name=test_name)

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse('test-auto-associate-tests'),
                                    json.dumps({'tests': [test.id]}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)

        associated_files_names = set(test.associated_files.all().values_list('filename', flat=True))
        expected_file_names = set(file_names.values())
        self.assertEqual(associated_files_names, expected_file_names, str(associated_files_names))

    def test_auto_assign_files_leaf_node_var(self):
        test_matched_file = 'test_name_1'
        file_tree = [{'filename': 'root',
                      'children': [{'filename': 'file_1',
                                    'children': []
                                    },
                                   {'filename': 'test_folder_1',
                                    'children': [
                                        {'filename': test_matched_file,  # <= matched by name
                                         'children': []
                                         }]}]}]
        self.create_file_trees(file_tree)
        test_name = ' '.join([test_matched_file])
        test = self.create_test_model_object(name=test_name)

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse('test-auto-associate-tests'),
                                    json.dumps({'tests': [test.id]}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        associated_files = set(test.associated_files.all().values_list('filename', flat=True))
        expected_file_names = {test_matched_file}
        self.assertEqual(associated_files, expected_file_names, str(associated_files))

    def test_auto_assign_files_middle_node_var(self):
        file_names = {'root': 'test_folder_name_1',
                      'file_1': 'test_filename_1',
                      'file_2': 'test_filename_2',
                      'folder_1': 'test_folder_1'}

        file_tree = [{'filename': file_names['root'],
                      'children': [{'filename': file_names['file_1'],
                                    'children': []
                                    },
                                   {'filename': file_names['folder_1'],  # <= matched by name
                                    'children': [
                                        {'filename': file_names['file_2'],
                                         'children': []
                                         }]}]}]
        self.create_file_trees(file_tree)
        test_name = file_names['folder_1']
        test = self.create_test_model_object(name=test_name)

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse('test-auto-associate-tests'),
                                    json.dumps({'tests': [test.id]}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        associated_files = set(test.associated_files.all().values_list('filename', flat=True))
        expected_file_names = {file_names['folder_1'], file_names['file_2']}
        self.assertEqual(associated_files, expected_file_names, str(associated_files))

    def test_auto_assign_files_assigned_files_in_matched_tree(self):
        file_names = {'root': 'test_folder_name_1',
                      'file_1': 'test_filename_1',
                      'file_2': 'test_filename_2',
                      'folder_1': 'test_folder_1'}

        file_tree = [{'filename': file_names['root'],  # <= matched by name
                      'children': [{'filename': file_names['file_1'],
                                    'children': []
                                    },
                                   {'filename': file_names['folder_1'],
                                    'children': [
                                        {'filename': file_names['file_2'],  # <= assigned file
                                         'children': []
                                         }]}]}]
        self.create_file_trees(file_tree)
        test_name = file_names['root']
        test = self.create_test_model_object(name=test_name)
        test.associated_files.add(File.objects.get(filename=file_names['file_2']))

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse('test-auto-associate-tests'),
                                    json.dumps({'tests': [test.id]}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)

        associated_files_names = set(test.associated_files.all().values_list('filename', flat=True))
        expected_file_names = set(file_names.values())
        self.assertEqual(associated_files_names, expected_file_names, str(associated_files_names))

    def test_auto_assign_files_multiple_match_in_one_tree_var(self):
        file_names = {'root': 'test_folder_name_1',
                      'file_1': 'test_filename_1',
                      'file_2': 'test_filename_2',
                      'file_3': 'test_filename_3',
                      'folder_1': 'test_folder_1'}

        file_tree = [{'filename': file_names['root'],  # <= matched by name
                      'children': [{'filename': file_names['file_1'],
                                    'children': []
                                    },
                                   {'filename': file_names['folder_1'],  # <= matched by name
                                    'children': [
                                        {'filename': file_names['file_2'],  # <= matched by name
                                         'children': []
                                         },

                                        {'filename': file_names['file_3'],  # <= assigned and matched
                                         'children': []
                                         },

                                    ]},

                                   ]}]
        self.create_file_trees(file_tree)
        test_name = ' '.join(file_names.values())
        test = self.create_test_model_object(name=test_name)
        test.associated_files.add(File.objects.get(filename=file_names['file_3']))

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse('test-auto-associate-tests'),
                                    json.dumps({'tests': [test.id]}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)

        associated_files_names = set(test.associated_files.all().values_list('filename', flat=True))
        expected_file_names = set(file_names.values())
        self.assertEqual(associated_files_names, expected_file_names, str(associated_files_names))

