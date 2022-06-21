# -*- coding: utf-8 -*-
import pathlib
import pytz
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import models, connection
from django.utils import timezone
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from django.conf import settings
from applications.ml.database import prepare_dataset_to_file
from applications.ml.network import train_model, load_model
from applications.ml.utils import logger


class States(models.TextChoices):
    PENDING = "PENDING", "PENDING"
    PREPARING = "PREPARING", "PREPARING"
    PREPARED = "PREPARED", "PREPARED"
    TRAINING = "TRAINING", "TRAINING"
    TRAINED = "TRAINED", "TRAINED"
    ERROR = "ERROR", "ERROR"


class MLModel(models.Model):

    test_suite = models.ForeignKey(
        "testing.TestSuite",
        related_name="models",
        on_delete=models.CASCADE
    )

    tests = models.ManyToManyField(
        "testing.Test",
        blank=True
    )

    state = models.CharField(
        verbose_name="state",
        max_length=128,
        default=States.PENDING,
        choices=States.choices,
        blank=False,
        null=False
    )

    index = models.IntegerField(default=0)

    fr = models.DateTimeField(
        verbose_name="from datetime",
        null=True
    )

    to = models.DateTimeField(
        verbose_name="to datetime",
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
        unique_together = ["test_suite", "index", ]
        ordering = ["id", "test_suite", "index", ]
        verbose_name = "model"
        verbose_name_plural = "models"

    def __str__(self):
        return f"<MLModel: {self.id}> for <TestSuite: {self.test_suite_id}> [{self.index}] [{self.state}]"

    def dataset_sql(self, test):
        sql_template_filepath = settings.BASE_DIR / "applications" / "ml" / "sql" / "dataset.sql"
        sql_template = open(sql_template_filepath, "r", encoding="utf-8").read()

        min_date = self.fr
        max_date = self.to

        sql = sql_template.format(
            test_suite_id=self.test_suite_id,
            test_id=test.id,
            min_date=min_date,
            max_date=max_date
        )
        return sql

    @property
    def dataset_filename(self):
        return "{test_id}.json"

    @property
    def dataset_path(self):
        project = self.test_suite.project
        organization = project.organization
        directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml" / "datasets" / \
                    str(organization.id) / str(project.id) / str(self.test_suite_id) / str(self.index)
        return directory

    @property
    def dataset_filepaths(self):
        files = []
        test_ids = list(self.tests.all().values_list('id', flat=True))
        for test_id in test_ids:
            dataset_filename = self.dataset_filename.format(test_id=test_id)
            dataset_path = self.dataset_path
            dataset_filepath = dataset_path / dataset_filename
            if dataset_filepath.exists():
                files.append(dataset_filepath)
        return files

    @property
    def model_filename(self):
        return f"{self.index}.m"

    @property
    def model_path(self) -> pathlib.PosixPath:
        project = self.test_suite.project
        organization = project.organization
        directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml" / "models" / \
                    str(organization.id) / str(project.id) / str(self.test_suite.id)
        return directory

    @property
    def tests_for_train(self):
        sql_template_filepath = settings.BASE_DIR / "applications" / "ml" / "sql" / "test.sql"
        sql_template = open(sql_template_filepath, "r", encoding="utf-8").read()

        min_date = self.fr
        max_date = self.to

        sql = sql_template.format(test_suite_id=self.test_suite_id, min_date=min_date, max_date=max_date)
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        test_ids = list([row['test_id'] for row in rows])
        return self.test_suite.tests.filter(id__in=test_ids)

    def prepare(self):
        self.state = States.PREPARING
        self.save()
        # TODO: RUN function with threads
        result = prepare_dataset_to_file(ml_model=self)
        self.state = States.PREPARED
        self.save()
        return result

    def train(self):
        self.state = States.TRAINING
        self.save()
        # TODO: RUN function with threads
        result = None
        try:
            result = train_model(ml_model=self)
            self.state = States.TRAINED
        except Exception as exc:
            self.state = States.PREPARED
        self.save()
        return result

    @classmethod
    def train_model(cls, test_suite_id):
        queryset = cls.objects.filter(
            test_suite_id=test_suite_id,
            state=States.PREPARED
        ).order_by("test_suite", "index")

        for ml_model in queryset:
            ml_model.save()
            try:
                prev_ml_model = cls.objects.filter(test_suite_id=test_suite_id, index=ml_model.index - 1).last()
                if prev_ml_model is None:
                    result = ml_model.train()
                else:
                    if prev_ml_model.state == States.TRAINED:
                        result = ml_model.train()
                    else:
                        logger.error(f"Skipped this {ml_model}: previous model not trained")
            except Exception as exc:
                raise exc

    @classmethod
    def open_model(cls, test_suite_id):
        ml_model = cls.objects.filter(test_suite_id=test_suite_id, state=States.TRAINED).order_by("index").last()
        if ml_model is not None:
            model = load_model(ml_model)
        else:
            model = None
        return model

    @classmethod
    def create_sequence(cls, test_suite_id):

        default_months = 1

        current_datetime = datetime.now() + relativedelta(day=1)
        current_datetime = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)

        model = cls.objects.filter(test_suite_id=test_suite_id).last()

        if model is None:
            fr_datetime = datetime.now() + relativedelta(months=-12) + relativedelta(day=1)
            to_datetime = fr_datetime + relativedelta(months=default_months) + relativedelta(day=31)

            model = MLModel.objects.create(
                test_suite_id=test_suite_id,
                index=0,
                fr=fr_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC),
                to=to_datetime.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=pytz.UTC),
                state=States.PENDING
            )
            tests = list(model.tests_for_train)
            model.tests.set(tests)

        while model is not None:
            next_fr = model.to
            next_to = next_fr + relativedelta(months=default_months) + relativedelta(day=31)

            if current_datetime >= next_to:
                model = MLModel.objects.create(
                    test_suite_id=test_suite_id,
                    index=model.index + 1,
                    fr=next_fr.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC),
                    to=next_to.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=pytz.UTC),
                    state=States.PENDING
                )
                tests = list(model.tests_for_train)
                model.tests.set(tests)
            else:
                model = None

        return cls.objects.filter(test_suite_id=test_suite_id)



@receiver(post_save, sender=MLModel)
def create_directories(sender, instance, created, **kwargs):
    try:
        model_path = instance.model_path
        model_path.mkdir(parents=True, exist_ok=True)

        dataset_path = instance.dataset_path
        dataset_path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.exception(f"Unknown error on create directories for "
                         f"<MLModel: '{instance.id}' [{instance.test_suite_id}]>", exc_info=True)


@receiver(post_delete, sender=MLModel)
def delete_directories(sender, instance, **kwargs):
    try:
        model_path = instance.model_path
        model_path.rmdir()

        dataset_path = instance.dataset_path
        dataset_path.rmdir()
    except Exception as exc:
        logger.exception(f"Unknown error on create directories for "
                         f"<MLModel: '{instance.id}' [{instance.test_suite_id}]>", exc_info=True)
