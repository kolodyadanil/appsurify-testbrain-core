# -*- coding: utf-8 -*-
import pathlib
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import models
from django.conf import settings


class MLModel(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        PROCESSING = "PROCESSING", "PROCESSING"
        SUCCESS = "SUCCESS", "SUCCESS"
        FAILURE = "FAILURE", "FAILURE"
        UNKNOWN = "UNKNOWN", "UNKNOWN"

    test_suite = models.OneToOneField(
        "testing.TestSuite",
        verbose_name="test_suite",
        related_name="model",
        on_delete=models.CASCADE
    )

    dataset_status = models.CharField(
        verbose_name="dataset status",
        max_length=128,
        default=Status.UNKNOWN,
        choices=Status.choices,
        blank=False,
        null=False
    )

    model_status = models.CharField(
        verbose_name="model status",
        max_length=128,
        default=Status.UNKNOWN,
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
        return f"<Model: {self.id} (TestSuite: {self.test_suite_id})>"

    @property
    def dataset_sql(self):
        sql_template = open(settings.BASE_DIR / "applications" / "ml" / "sql" / "dataset.sql", "r",
                            encoding="utf-8").read()
        sql = sql_template.format(test_suite_id=self.test_suite_id)
        return sql

    @property
    def dataset_path(self):
        project = self.test_suite.project
        organization = project.organization
        dir = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml" / "datasets" / \
              str(organization.id) / str(project.id)
        return dir, f"{self.test_suite_id}.csv"

    @property
    def model_path(self):
        project = self.test_suite.project
        organization = project.organization
        dir = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml" / "models" / \
              str(organization.id) / str(project.id)
        return dir, f"{self.test_suite_id}.model"


@receiver(post_save, sender=MLModel)
def create_directories(sender, instance, created, **kwargs):
    try:
        model_path, model_filename = instance.model_path
        model_path.mkdir(parents=True, exist_ok=True)

        dataset_path, dataset_filename = instance.dataset_path
        dataset_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(e)


@receiver(post_delete, sender=MLModel)
def delete_directories(sender, instance, **kwargs):
    try:
        model_path, model_filename = instance.model_path
        model_path.rmdir()

        dataset_path, dataset_filename = instance.dataset_path
        dataset_path.rmdir()
    except Exception as e:
        print(e)
