# -*- coding: utf-8 -*-
from typing import List, Tuple, Optional, Union, AnyStr
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.defaultfilters import slugify
from .exceptions import ProjectOwnershipRequired


USER_MODEL = get_user_model()


class Project(models.Model):
    """
    Default Project model.
    """
    organization = models.ForeignKey(
        "customers.Organization",
        verbose_name="organization",
        related_name="projects",
        on_delete=models.CASCADE
    )

    name = models.CharField(
        verbose_name="name",
        max_length=255,
        blank=False,
        null=False,
        unique=True
    )

    slug = models.SlugField(
        max_length=253,
        blank=False,
        null=False,
        unique=True,
        help_text="Auto-generated field"
    )

    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)

    members = models.ManyToManyField(
        USER_MODEL,
        verbose_name="members",
        through="ProjectMember",
        related_name="projects"
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = ["name", ]
        verbose_name = "project"
        verbose_name_plural = "projects"

    def __str__(self):
        return f"{self.name}"

    @property
    def members_count(self) -> int:
        """ Return project members count. """
        members_count = ProjectMember.objects.filter(project=self).count()
        return members_count

    def save(self, force_insert: bool = False, force_update: bool = False,
             using: Optional = None, update_fields: Optional[List] = None) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(force_insert=force_insert, force_update=force_update,
                            using=using, update_fields=update_fields)

    def add_member(self, user: USER_MODEL, is_admin: bool = False, is_owner: bool = False) -> "ProjectMember":
        """ Add user to project and set user owner if members_count == 0. """
        if self.members_count == 0:
            is_admin = True
            is_owner = True

        project_user = ProjectMember.objects.create(project=self, user=user, is_admin=is_admin, is_owner=is_owner)
        return project_user

    def remove_member(self, user: USER_MODEL) -> None:
        project_user = ProjectMember.objects.get(user=user)
        project_user.delete()

    def is_admin(self, user: USER_MODEL) -> bool:
        """
        Returns True is user is an admin in the project, otherwise false
        """
        return True if self.project_members.filter(user=user, is_admin=True) else False

    def is_owner(self, user: USER_MODEL) -> bool:
        """
        Returns True is user is the project's owner, otherwise false
        """
        return True if self.project_members.filter(user=user, is_owner=True) else False


class ProjectMember(models.Model):
    """
    Default ProjectUser model.
    """
    project = models.ForeignKey("Project", related_name="project_members", on_delete=models.CASCADE)
    user = models.ForeignKey(USER_MODEL, related_name="project_members", on_delete=models.CASCADE)

    is_admin = models.BooleanField(default=False)
    is_owner = models.BooleanField(default=False)

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = ["project", "user"]
        verbose_name = "project user"
        verbose_name_plural = "project users"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "is_owner"],
                condition=models.Q(is_owner=True),
                name="unique_project_owner"
            ),
            models.UniqueConstraint(
                fields=["project", "user"],
                name="unique_project_user"
            ),
        ]

    def __str__(self):
        return f"{self.project} - {self.user}"

    def delete(self, using: Optional = None, keep_parents: bool = False) -> None:
        if self.is_owner:
            raise ProjectOwnershipRequired("Cannot delete project owner "
                                           "before project or change ownership.")
        super().delete(using=using, keep_parents=keep_parents)


class TestReport(models.Model):
    pass


class TestSuite(models.Model):
    project = models.ForeignKey(
        "Project",
        verbose_name="project",
        related_name="test_suites",
        on_delete=models.CASCADE
    )

    name = models.CharField(
        verbose_name="name",
        max_length=1000,
        blank=False,
        null=False
    )

    description = models.TextField(
        verbose_name="description",
        max_length=4000,
        blank=True,
        null=True
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = ["name", ]
        verbose_name = "test suite"
        verbose_name_plural = "test suites"

    def __str__(self):
        return f"{self.name}"


class TestRun(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        STARTED = "STARTED", "STARTED"
        SUCCESS = "SUCCESS", "SUCCESS"
        UNKNOWN = "UNKNOWN", "UNKNOWN"

    project = models.ForeignKey(
        "Project",
        verbose_name="project",
        related_name="test_runs",
        on_delete=models.CASCADE
    )

    test_suite = models.ForeignKey(
        "TestSuite",
        verbose_name="testsuite",
        related_name="test_runs",
        blank=False,
        null=False,
        on_delete=models.CASCADE
    )

    name = models.CharField(
        verbose_name="name",
        max_length=1000,
        blank=False,
        null=False
    )

    description = models.TextField(
        verbose_name="description",
        max_length=4000,
        blank=True,
        null=True
    )

    meta = models.JSONField(
        verbose_name="meta",
        default=tuple,
        blank=True,
        null=False
    )

    data = models.JSONField(
        verbose_name="data",
        default=tuple,
        blank=True,
        null=False
    )

    status = models.CharField(
        verbose_name="status",
        max_length=128,
        default=Status.PENDING,
        choices=Status.choices,
        blank=False,
        null=False
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = ["name", ]
        verbose_name = "test run"
        verbose_name_plural = "test runs"

    def __str__(self):
        return f"{self.name}"


class Test(models.Model):
    pass
