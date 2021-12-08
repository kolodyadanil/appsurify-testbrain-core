# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
from rest_framework import status
from applications.api.common.tests import ApiBaseTestClass

from applications.vcs.models import Area
from applications.testing.models import Test


class ApiAreaTestClass(ApiBaseTestClass):
    def setUp(self):
        self.setup_db()

        file_tree = []
        area_name_factory = self.get_name_factory('Base_area')
        test_name_factory = self.get_name_factory('Base_test')
        file_name_factory = self.get_name_factory('Base_file')
        for i in range(1, 7):
            area = self.create_area_model_object(name=area_name_factory())
            self.create_test_model_object(name=test_name_factory(), area=area)
            file_tree.append({'filename': file_name_factory(), 'children': []})
        self.create_file_trees(file_tree)


class AreaCreateLinksBetweenAreasTestApi(ApiAreaTestClass):
    def test_linking_areas(self):
        post_data = [{'main_area': Area.objects.get(name__iexact='Base_area_1').id,
                      'linked_areas': [
                          Area.objects.get(name__iexact='Base_area_2').id,
                          Area.objects.get(name__iexact='Base_area_3').id,
                        ]},
                     {'main_area': Area.objects.get(name__iexact='Base_area_4').id,
                      'linked_areas': [
                          Area.objects.get(name__iexact='Base_area_5').id,
                          Area.objects.get(name__iexact='Base_area_6').id,
                      ]}
                     ]

        self.client.login(username=self.username, password=self.password)
        response = self.client.post('/api/areas/linked-areas/',
                                    json.dumps(post_data),
                                    content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_area_name_factory = self.get_name_factory('New_area')
        new_test_name_factory = self.get_name_factory('New_area')
        for link_case in post_data:
            main_area = Area.objects.get(id=link_case['main_area'])
            linked_areas = list(Area.objects.filter(id__in=link_case['linked_areas']))
            # Check that 'linked_areas' really were added into 'links' for 'main_area'
            self.assertEqual(list(main_area.links.all()), linked_areas)

            # Check that all tests that have 'main_area' in 'area' field
            # now also have 'linked_areas' in 'associated_ares'
            tests = list(Test.objects.filter(area=main_area))
            for test in tests:
                self.assertEqual(list(test.associated_areas.all()), linked_areas)

            # Check that new test that has 'main_area' in 'area' field have 'linked_areas'
            # in 'associated_areas'
            new_test = self.create_test_model_object(name=new_test_name_factory(), area=main_area)
            self.assertEqual(list(new_test.associated_areas.all()), linked_areas)

            new_area = self.create_area_model_object(name=new_area_name_factory())
            new_test = self.create_test_model_object(name=new_test_name_factory(), area=new_area)
            self.assertNotEqual(list(new_test.associated_areas.all()), linked_areas)
            new_test.area = main_area
            new_test.save()
            self.assertEqual(list(new_test.associated_areas.all()), linked_areas)

            new_area = self.create_area_model_object(name=new_area_name_factory())
            new_test = self.create_test_model_object(name=new_test_name_factory(), area=new_area)
            self.assertNotEqual(list(new_test.associated_areas.all()), linked_areas)
            self.assertEqual(1, Test.objects.filter(id=new_test.id).update(area=main_area))
            self.assertNotEqual(new_test.area.id, main_area.id)
            new_test = Test.objects.get(id=new_test.id)
            self.assertEqual(new_test.area.id, main_area.id)
            self.assertNotEqual(list(new_test.associated_areas.all()), linked_areas)
            new_test.update_associated_areas_by_linked_areas()
            self.assertEqual(list(new_test.associated_areas.all()), linked_areas)
        return


class ApiAreaTestDependencies(ApiAreaTestClass):
    def test_dependent_areas_route(self):
        """
        In this function we test common work '/api/areas/dependent-areas/'
        route.
        """
        post_data = [{'main_area': Area.objects.get(name__iexact='Base_area_1').id,
                      'dependent_areas': [
                          Area.objects.get(name__iexact='Base_area_2').id,
                          Area.objects.get(name__iexact='Base_area_3').id,
                      ]},
                     {'main_area': Area.objects.get(name__iexact='Base_area_4').id,
                      'dependent_areas': [
                          Area.objects.get(name__iexact='Base_area_5').id,
                          Area.objects.get(name__iexact='Base_area_6').id,
                      ]}
                     ]

        self.client.login(username=self.username, password=self.password)
        response = self.client.post('/api/areas/dependent-areas/',
                                    json.dumps(post_data),
                                    content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for dependency_case in post_data:
            main_area = Area.objects.get(id=dependency_case['main_area'])
            dependent_areas = list(Area.objects.filter(id__in=dependency_case['dependent_areas']))
            # Check that 'dependent_areas' really were added into 'dependencies' for 'main_area'
            self.assertEqual(list(main_area.dependencies.all()), dependent_areas)
        return


class ApiAreaTestSearchByNameRoute(ApiAreaTestClass):
    def test_search_by_name_existent_area(self):
        """
        In this function we test common work '/api/areas/by-name/'
        route when searched area exist.
        """
        self.client.login(username=self.username, password=self.password)
        searched_area_name = 'Base_area_1'
        data = {
            'name': searched_area_name,
            'project': self.project.id,
        }
        response = self.client.get('/api/areas/by-name/', data=data)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response_area_data = response.data['area']
        self.assertEqual('Base_area_1', response_area_data['name'])

        area_id = Area.objects.get(name=searched_area_name).id
        self.assertEqual(area_id, response_area_data['id'])
        return

    def test_search_by_name_nonexistent_area(self):
        """
        In this function we test common work '/api/areas/by-name/'
        route when searched area doesn't exist.
        """
        self.client.login(username=self.username, password=self.password)
        data = {
            'name': 'Nonexistent_area',
            'project': self.project.id,
        }
        response = self.client.get('/api/areas/by-name/', data=data)
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(None, response.data['area'])
        return
