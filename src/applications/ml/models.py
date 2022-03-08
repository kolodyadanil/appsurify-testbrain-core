# -*- coding: utf-8 -*-
import pathlib
from django.db import models
from django.conf import settings


class MLDataset(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        STARTED = "STARTED", "STARTED"
        SUCCESS = "SUCCESS", "SUCCESS"
        REJECTED = "REJECTED", "REJECTED"
        FAILURE = "FAILURE", "FAILURE"
        UNKNOWN = "UNKNOWN", "UNKNOWN"

    test_suite = models.OneToOneField(
        "testing.TestSuite",
        verbose_name="test_suite",
        related_name="dataset",
        on_delete=models.CASCADE
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
        ordering = ["id", "test_suite", ]
        verbose_name = "dataset"
        verbose_name_plural = "datasets"

    def __str__(self):
        return f"{self.id}"

    @property
    def path(self):
        project = self.test_suite.project
        organization = project.organization
        dir = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml" / "datasets" / \
              str(organization.id) / str(project.id)
        return dir, f"{self.test_suite_id}.csv"


class MLModel(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        STARTED = "STARTED", "STARTED"
        SUCCESS = "SUCCESS", "SUCCESS"
        FAILURE = "FAILURE", "FAILURE"
        UNKNOWN = "UNKNOWN", "UNKNOWN"

    test_suite = models.OneToOneField(
        "testing.TestSuite",
        verbose_name="test_suite",
        related_name="model",
        on_delete=models.CASCADE
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
        ordering = ["id", "test_suite", ]
        verbose_name = "model"
        verbose_name_plural = "models"

    def __str__(self):
        return f"{self.id}"

    @property
    def path(self):
        project = self.test_suite.project
        organization = project.organization
        dir = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml" / "models" / \
              str(organization.id) / str(project.id)
        return dir, f"{self.test_suite_id}.model"
