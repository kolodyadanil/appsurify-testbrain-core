# -*- coding: utf-8 -*-
from django.test import TestCase
from applications.projects.models import Project
from applications.customers.models import User, Organization
from applications.projects.exceptions import ProjectOwnershipRequired


class ProjectModelCase(TestCase):
    fixtures = ["customers", "projects"]

    def setUp(self) -> None:
        pass

    def test_01_load_fixtures(self):
        project = Project.objects.get(name="Demo")
        self.assertEqual(project.slug, "demo")

    def test_02_create_project(self):
        organization = Organization.objects.get(domain="appsurify-inc")
        project = Project.objects.create(organization=organization, name="Demo 2")
        self.assertEqual(project.slug, "demo-2")

    def test_03_add_or_create_project_members(self):
        organization = Organization.objects.get(domain="appsurify-inc")
        project = Project.objects.get(organization=organization, slug="demo")

        user = User.objects.get(email="user@localhost.localdomain")
        project.add_member(user=user)
        self.assertEqual(project.members_count, 1)

        new_user = User.objects.create_user(email="new@localhost.localdomain", password="TestP@ssw0RD")
        project.add_member(user=new_user)
        self.assertEqual(project.members_count, 2)

    def test_04_remove_project_member(self):
        organization = Organization.objects.get(domain="appsurify-inc")
        project = Project.objects.get(organization=organization, slug="demo")

        user = User.objects.get(email="user@localhost.localdomain")
        project.add_member(user=user)

        new_user = User.objects.create_user(email="new@localhost.localdomain", password="TestP@ssw0RD")
        project.add_member(user=new_user)

        with self.assertRaises(ProjectOwnershipRequired):
            project.remove_member(user=user)

        project.remove_member(user=new_user)
        self.assertEqual(project.members_count, 1)
