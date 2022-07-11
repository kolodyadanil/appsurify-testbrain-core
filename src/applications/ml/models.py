import pytz
import typing
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from applications.ml.utils.dataset import get_dataset_test_ids, export_datasets
from applications.ml.utils.log import logger
from applications.ml.network import TestPrioritizationCBM


class States(models.TextChoices):
    PENDING = "PENDING", "PENDING"
    PREPARING = "PREPARING", "PREPARING"
    PREPARED = "PREPARED", "PREPARED"
    TRAINING = "TRAINING", "TRAINING"
    TRAINED = "TRAINED", "TRAINED"
    ERROR = "ERROR", "ERROR"
    SKIPPED = "SKIPPED", "SKIPPED"


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

    from_date = models.DateTimeField(
        verbose_name="from datetime",
        null=True
    )

    to_date = models.DateTimeField(
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
        return f"MLModel object ({self.id}) TestSuite ({self.test_suite_id}) [{self.index}]"

    @property
    def tests_for_train(self):
        test_ids = get_dataset_test_ids(test_suite_id=self.test_suite.id,
                                        from_date=self.from_date, to_date=self.to_date)
        return self.test_suite.tests.filter(id__in=test_ids)

    def prepare(self):
        self.state = States.PREPARING
        self.save()
        # TODO: RUN function with threads
        try:
            organization_id = int(self.test_suite.project.organization_id)
            project_id = int(self.test_suite.project_id)
            test_suite_id = int(self.test_suite_id)
            index = self.index
            test_ids = list(self.tests.values_list("id", flat=True))
            result = export_datasets(
                organization_id=organization_id,
                project_id=project_id,
                test_suite_id=test_suite_id,
                index=index,
                test_ids=test_ids,
                from_date=self.from_date,
                to_date=self.to_date
            )
            self.state = States.PREPARED
        except Exception as exc:
            self.state = States.PENDING
        self.save()

    def train(self):
        self.state = States.TRAINING
        self.save()
        # TODO: RUN function with threads
        try:
            tpcbm = TestPrioritizationCBM(ml_model=self)
            clf = tpcbm.train()
            if clf.is_fitted:
                self.state = States.TRAINED
            else:
                self.state = States.SKIPPED
        except Exception as exc:
            self.state = States.PREPARED
        self.save()

    @classmethod
    def train_model(cls, test_suite_id):
        queryset = cls.objects.filter(
            test_suite_id=test_suite_id,
            state=States.PREPARED
        ).order_by("test_suite", "index")

        for ml_model in queryset:
            if ml_model.tests.count() == 0:
                ml_model.state = States.SKIPPED
                ml_model.save()
                continue

            ml_model.save()
            try:
                prev_ml_model = cls.objects.order_by("test_suite", "index").filter(
                    test_suite_id=test_suite_id, index=ml_model.index - 1).last()
                if prev_ml_model is None:
                    result = ml_model.train()
                else:
                    if prev_ml_model.state in (States.TRAINED, States.SKIPPED):
                        result = ml_model.train()
                    else:
                        logger.error(f"Skipped this {ml_model}: previous model not trained")
            except Exception as exc:
                raise exc

    @classmethod
    def load_model(cls, test_suite_id) -> TestPrioritizationCBM:
        ml_model = cls.objects.filter(test_suite_id=test_suite_id, state=States.TRAINED).order_by("index").last()
        if ml_model is not None:
            tpcbm = TestPrioritizationCBM(ml_model=ml_model)
            if not tpcbm.is_fitted:
                logger.error(f"Classifier not fitted for {ml_model}")
                tpcbm = None
        else:
            tpcbm = None
        return tpcbm


def create_sequence(test_suite_id: int) -> typing.Union[models.QuerySet, typing.List[MLModel]]:
    default_months = 1
    current_datetime = datetime.now() + relativedelta(day=1)
    current_datetime = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)

    model = MLModel.objects.filter(test_suite_id=test_suite_id).last()

    if model is None:
        fr_datetime = datetime.now() + relativedelta(months=-12) + relativedelta(day=1)
        to_datetime = fr_datetime + relativedelta(months=default_months) + relativedelta(day=31)

        model = MLModel.objects.create(
            test_suite_id=test_suite_id,
            index=0,
            from_date=fr_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC),
            to_date=to_datetime.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=pytz.UTC),
            state=States.PENDING
        )
        tests = list(model.tests_for_train)
        model.tests.set(tests)
        if len(tests) == 0:
            model.state = States.SKIPPED
            model.save()

    while model is not None:
        next_fr = model.to_date
        next_to = next_fr + relativedelta(months=default_months) + relativedelta(day=31)

        if current_datetime >= next_to:
            model = MLModel.objects.create(
                test_suite_id=test_suite_id,
                index=model.index + 1,
                from_date=next_fr.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC),
                to_date=next_to.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=pytz.UTC),
                state=States.PENDING
            )
            tests = list(model.tests_for_train)
            model.tests.set(tests)
            if len(tests) == 0:
                model.state = States.SKIPPED
                model.save()
        else:
            model = None

    return MLModel.objects.filter(test_suite_id=test_suite_id)


@receiver(post_save, sender=MLModel)
def create_directories(sender, instance, created, **kwargs):
    from applications.ml.utils.dataset import get_dataset_directory
    from applications.ml.utils.model import get_model_directory
    try:
        organization_id = instance.test_suite.project.organization_id
        project_id = instance.test_suite.project_id
        test_suite_id = instance.test_suite_id
        index = instance.index

        model_directory = get_model_directory(organization_id=organization_id, project_id=project_id,
                                              test_suite_id=test_suite_id, index=index)
        model_directory.mkdir(parents=True, exist_ok=True)

        dataset_directory = get_dataset_directory(organization_id=organization_id, project_id=project_id,
                                                  test_suite_id=test_suite_id, index=index)
        dataset_directory.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.exception(f"Unknown error on create directories for "
                         f"<MLModel: '{instance.id}' [{instance.test_suite_id}]>", exc_info=True)


@receiver(post_delete, sender=MLModel)
def delete_directories(sender, instance, **kwargs):
    from applications.ml.utils.dataset import get_dataset_directory
    from applications.ml.utils.model import get_model_directory
    try:
        organization_id = instance.test_suite.project.organization_id
        project_id = instance.test_suite.project_id
        test_suite_id = instance.test_suite_id
        index = instance.index

        model_directory = get_model_directory(organization_id=organization_id, project_id=project_id,
                                              test_suite_id=test_suite_id, index=index)
        model_directory.rmdir()

        dataset_directory = get_dataset_directory(organization_id=organization_id, project_id=project_id,
                                                  test_suite_id=test_suite_id, index=index)
        dataset_directory.rmdir()

    except Exception as exc:
        logger.exception(f"Unknown error on create directories for "
                         f"<MLModel: '{instance.id}' [{instance.test_suite_id}]>", exc_info=True)
