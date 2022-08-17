import pytz
import typing
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from applications.ml.utils.dataset import get_dataset_test_ids, export_datasets
from applications.ml.utils.log import logger
from applications.ml.network import TestPrioritizationNLPCBM


class DatasetStates(models.TextChoices):
    PENDING = "PENDING", "PENDING"
    PREPARING = "PREPARING", "PREPARING"
    PREPARED = "PREPARED", "PREPARED"
    ERROR = "ERROR", "ERROR"
    SKIPPED = "SKIPPED", "SKIPPED"


class MLStates(models.TextChoices):
    PENDING = "PENDING", "PENDING"
    TRAINING = "TRAINING", "TRAINING"
    TRAINED = "TRAINED", "TRAINED"
    ERROR = "ERROR", "ERROR"
    SKIPPED = "SKIPPED", "SKIPPED"


class MLDataset(models.Model):
    test_suite = models.ForeignKey(
        "testing.TestSuite",
        related_name="datasets",
        on_delete=models.CASCADE
    )

    tests = models.ManyToManyField(
        "testing.Test",
        blank=True
    )

    state = models.CharField(
        verbose_name="state",
        max_length=128,
        default=DatasetStates.PENDING,
        choices=DatasetStates.choices,
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
        verbose_name = "dataset"
        verbose_name_plural = "datasets"

    def __str__(self):
        return f"MLDataset object ({self.id}) TestSuite ({self.test_suite_id}) [{self.index}]"

    @property
    def tests_for_train(self):
        test_ids = get_dataset_test_ids(test_suite_id=self.test_suite.id,
                                        from_date=self.from_date, to_date=self.to_date)
        return self.test_suite.tests.filter(id__in=test_ids)

    def prepare(self):
        self.state = DatasetStates.PREPARING
        self.save()
        # TODO: RUN function with threads
        # TODO: Update one more time tests
        tests = list(self.tests_for_train)
        self.tests.set(tests)

        try:
            organization_id = int(self.test_suite.project.organization_id)
            project_id = int(self.test_suite.project_id)
            test_suite_id = int(self.test_suite_id)
            index = self.index

            test_ids = list(self.tests.values_list("id", flat=True))
            if len(test_ids) == 0:
                self.state = DatasetStates.SKIPPED
                self.save()
                return

            result = export_datasets(
                organization_id=organization_id,
                project_id=project_id,
                test_suite_id=test_suite_id,
                index=index,
                test_ids=test_ids,
                from_date=self.from_date,
                to_date=self.to_date,
                max_workers=10
            )
            self.state = DatasetStates.PREPARED
        except Exception as exc:
            self.state = DatasetStates.ERROR

        self.save()


class MLModel(models.Model):

    test_suite = models.OneToOneField(
        "testing.TestSuite",
        related_name="models",
        on_delete=models.CASCADE
    )

    datasets = models.ManyToManyField(
        "ml.MLDataset",
        blank=True
    )

    state = models.CharField(
        verbose_name="state",
        max_length=128,
        default=MLStates.PENDING,
        choices=MLStates.choices,
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
        unique_together = ["test_suite", ]
        ordering = ["id", "test_suite", ]
        verbose_name = "model"
        verbose_name_plural = "models"

    def __str__(self):
        return f"MLModel object ({self.id}) TestSuite ({self.test_suite_id})"

    def train(self):
        self.state = MLStates.TRAINING
        self.save()
        # TODO: RUN function with threads
        try:
            tpcbm = TestPrioritizationNLPCBM(ml_model=self)
            clf = tpcbm.train()
            if clf.is_fitted:
                self.state = MLStates.TRAINED
            else:
                self.state = MLStates.SKIPPED
        except Exception as exc:
            self.state = MLStates.PENDING
        self.save()

    @classmethod
    def train_model(cls, test_suite_id):

        ml_model = cls.objects.get(
            test_suite_id=test_suite_id,
            state=MLStates.PENDING
        )

        total_datasets = ml_model.datasets.count()
        skipped_datasets = ml_model.datasets.filter(state=DatasetStates.SKIPPED).count()
        valid_datasets = ml_model.datasets.filter(state=DatasetStates.PREPARED).count()

        if total_datasets == skipped_datasets:
            logger.error(f"Skipped this {ml_model}: all datasets empty.")
            ml_model.state = MLStates.SKIPPED
            ml_model.save()
        elif valid_datasets > 0:
            try:
                result = ml_model.train()
            except Exception as exc:
                raise exc
        else:
            ml_model.state = MLStates.PENDING
            ml_model.save()

    @classmethod
    def load_model(cls, test_suite_id) -> typing.Union[TestPrioritizationNLPCBM, None]:
        # try:
        #     ml_model = cls.objects.get(test_suite_id=test_suite_id)
        #     tpcbm = TestPrioritizationNLPCBM(ml_model=ml_model)
        #     if not tpcbm.is_fitted:
        #         logger.error(f"Classifier not fitted for {ml_model}")
        #         tpcbm = None
        #     else:
        #         tpcbm = None
        # except MLModel.DoesNotExist:
        #     tpcbm = None
        # return tpcbm
        from applications.testing.models import TestSuite
        tpcbm = None
        try:
            test_suite = TestSuite.objects.get(id=test_suite_id)
            project = test_suite.project
            organization = project.organization

            tpcbm = TestPrioritizationNLPCBM(organization_id=organization.id,
                                             project_id=project.id, test_suite_id=test_suite.id)
            if not tpcbm.is_fitted:
                logger.error(f"Classifier not fitted for {test_suite_id}")
                tpcbm = None
        except Exception as exc:
            logger.exception(f"Classifier not load for {test_suite_id}", exc_info=True)
            tpcbm = None
        return tpcbm


def create_sequence(test_suite_id: int) -> MLModel:
    default_months = 1
    current_datetime = datetime.now() + relativedelta(day=1)
    current_datetime = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)

    model, created = MLModel.objects.get_or_create(test_suite_id=test_suite_id, defaults={"state": MLStates.PENDING})

    if created:
        fr_datetime = datetime.now() + relativedelta(months=-12) + relativedelta(day=1)
        to_datetime = fr_datetime + relativedelta(months=default_months) + relativedelta(day=31)

        dataset = MLDataset.objects.create(
            test_suite_id=test_suite_id,
            index=0,
            from_date=fr_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC),
            to_date=to_datetime.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=pytz.UTC),
            state=DatasetStates.PENDING
        )
        tests = list(dataset.tests_for_train)
        dataset.tests.set(tests)
        model.datasets.add(dataset)
        if len(tests) == 0:
            dataset.state = DatasetStates.SKIPPED
            dataset.save()

    dataset = MLDataset.objects.filter(test_suite_id=test_suite_id).last()

    while dataset is not None:
        next_fr = dataset.to_date
        next_to = next_fr + relativedelta(months=default_months) + relativedelta(day=31)

        if current_datetime >= next_to:
            dataset = MLDataset.objects.create(
                test_suite_id=test_suite_id,
                index=dataset.index + 1,
                from_date=next_fr.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC),
                to_date=next_to.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=pytz.UTC),
                state=DatasetStates.PENDING
            )
            tests = list(dataset.tests_for_train)
            dataset.tests.set(tests)
            model.datasets.add(dataset)
            if len(tests) == 0:
                dataset.state = DatasetStates.SKIPPED
                dataset.save()
        else:
            dataset = None

    return MLModel.objects.get(test_suite_id=test_suite_id)


@receiver(post_save, sender=MLDataset)
def create_directories(sender, instance, created, **kwargs):
    from applications.ml.utils.dataset import get_dataset_directory
    from applications.ml.utils.model import get_model_directory
    try:
        organization_id = instance.test_suite.project.organization_id
        project_id = instance.test_suite.project_id
        test_suite_id = instance.test_suite_id
        index = instance.index

        model_directory = get_model_directory(organization_id=organization_id, project_id=project_id,
                                              test_suite_id=test_suite_id)
        model_directory.mkdir(parents=True, exist_ok=True)

        dataset_directory = get_dataset_directory(organization_id=organization_id, project_id=project_id,
                                                  test_suite_id=test_suite_id, index=index)
        dataset_directory.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.exception(f"Unknown error on create directories for "
                         f"<MLDataset: '{instance.id}' [{instance.test_suite_id}]>", exc_info=True)


@receiver(post_delete, sender=MLDataset)
def delete_directories(sender, instance, **kwargs):
    from applications.ml.utils.dataset import get_dataset_directory
    from applications.ml.utils.model import get_model_directory
    try:
        organization_id = instance.test_suite.project.organization_id
        project_id = instance.test_suite.project_id
        test_suite_id = instance.test_suite_id
        index = instance.index

        model_directory = get_model_directory(organization_id=organization_id, project_id=project_id,
                                              test_suite_id=test_suite_id)
        model_directory.rmdir()

        dataset_directory = get_dataset_directory(organization_id=organization_id, project_id=project_id,
                                                  test_suite_id=test_suite_id, index=index)
        dataset_directory.rmdir()

    except Exception as exc:
        logger.exception(f"Unknown error on create directories for "
                         f"<MLDataset: '{instance.id}' [{instance.test_suite_id}]>", exc_info=True)
