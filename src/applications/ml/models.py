# -*- coding: utf-8 -*-
import pathlib
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import models, connection
from django.conf import settings


class MLModel(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        PROCESSING = "PROCESSING", "PROCESSING"
        SUCCESS = "SUCCESS", "SUCCESS"
        FAILURE = "FAILURE", "FAILURE"
        UNKNOWN = "UNKNOWN", "UNKNOWN"

    test_suite = models.ForeignKey(
        "testing.TestSuite",
        verbose_name="test_suite",
        related_name="models",
        on_delete=models.CASCADE
    )

    test = models.ForeignKey(
        "testing.Test",
        verbose_name="test",
        related_name="models",
        null=True,
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
        unique_together = ["test_suite", "test"]
        ordering = ["id", "test_suite", "test", ]
        verbose_name = "model"
        verbose_name_plural = "models"

    def __str__(self):
        return f"<Model: {self.id} (TestSuite: {self.test_suite_id})>"

    @property
    def dataset_sql(self):
        sql_template = open(settings.BASE_DIR / "applications" / "ml" / "sql" / "dataset.sql", "r",
                            encoding="utf-8").read()
        sql = sql_template.format(test_suite_id=self.test_suite_id, test_id=self.test_id)
        return sql

    @property
    def dataset_path(self):
        project = self.test_suite.project
        organization = project.organization
        directory = pathlib.PosixPath("/mnt/testbrain-data") / "ml" / "datasets" / \
                    str(organization.id) / str(project.id) / str(self.test_suite_id)
        return directory

    @property
    def dataset_filename(self):
        return f"{self.test_id}.csv"

    @property
    def model_path(self):  # TODO: Refactoring
        directory, _ = self.get_model_filepath(self.test_suite)
        return directory

    @property
    def model_filename(self):  # TODO: Refactoring
        _, filename = self.get_model_filepath(self.test_suite)
        return filename

    @staticmethod
    def get_test_list(test_suite):
        sql_template = open(settings.BASE_DIR / "applications" / "ml" / "sql" / "test.sql", "r",
                            encoding="utf-8").read()
        sql = sql_template.format(test_suite_id=test_suite.id)
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return list([row['test_id'] for row in rows])

    @staticmethod
    def get_dataset_file_list(test_suite):
        files = []
        queryset = MLModel.objects.filter(
            test_suite=test_suite,
            dataset_status=MLModel.Status.SUCCESS
        ).order_by("test_id").only("test")
        for item in queryset:
            filepath = item.dataset_path / item.dataset_filename
            if filepath.exists():
                files.append(filepath)
        return files

    @staticmethod
    def get_model_filepath(test_suite):
        project = test_suite.project
        organization = project.organization
        directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml" / "models" / \
                    str(organization.id) / str(project.id)
        filename = f"{test_suite.id}.model"
        return directory, filename


@receiver(post_save, sender=MLModel)
def create_directories(sender, instance, created, **kwargs):
    try:
        model_path = instance.model_path
        model_path.mkdir(parents=True, exist_ok=True)

        dataset_path = instance.dataset_path
        dataset_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(e)


@receiver(post_delete, sender=MLModel)
def delete_directories(sender, instance, **kwargs):
    try:
        model_path = instance.model_path
        model_path.rmdir()

        dataset_path = instance.dataset_path
        dataset_path.rmdir()
    except Exception as e:
        print(e)
