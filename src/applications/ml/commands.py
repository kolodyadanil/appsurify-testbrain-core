
from datetime import datetime, timedelta
from applications.testing.models import TestSuite
from applications.project.models import Project
from applications.ml.models import MLModel, MLDataset, DatasetStates, MLStates, create_sequence
from applications.ml.utils.log import logger
from applications.ml.utils.functional import Statistic


def create_and_check_models():
    stats = Statistic()

    queryset = TestSuite.objects.filter(models__isnull=True).distinct().order_by("project_id")
    stats.total = queryset.count()
    logger.info(f"{stats} selected TestSuites for which there are no models")

    for test_suite in queryset:
        stats.increase_current()
        logger.debug(f"{stats} creating model for <TestSuite: {test_suite.id}>")
        try:
            ml_model = create_sequence(test_suite_id=test_suite.id)
            stats.increase_success()

            logger.debug(f"{stats} created models for "
                         f"<TestSuite: '{test_suite.id}'> - total sequence: {ml_model.datasets.count()}")

        except Exception as exc:
            stats.increase_failure()
            logger.exception(f"{stats} error created models for "
                             f"<TestSuite: {test_suite.id}>", exc_info=True)
        finally:
            if stats.progress_percent % 10 == 0:
                logger.info(f"{stats} creating models for TestSuites")

    logger.info(f"{stats} created models for TestSuites")

    stats.reset()

    time_threshold = datetime.now() - timedelta(weeks=2)
    queryset = MLModel.objects.filter(
        created__lt=time_threshold, state__in=MLStates.values).order_by("test_suite_id").distinct("test_suite_id")
    stats.total = queryset.count()

    logger.info(f"{stats} selected models for which you want to add a sequence")

    for ml_model in queryset:
        stats.increase_current()
        logger.debug(f"{stats} creating sequence for {ml_model}")
        try:
            ml_model = create_sequence(test_suite_id=ml_model.test_suite_id)
            stats.increase_success()

            logger.debug(f"{stats} created sequence for "
                         f"{ml_model} - total sequences: {ml_model.datasets.count()}")
        except Exception as exc:
            stats.increase_failure()
            logger.exception(f"{stats} error created sequence for "
                             f"{ml_model}", exc_info=True)
        finally:
            if stats.progress_percent % 10 == 0:
                logger.info(f"{stats} creating sequence for models")

    logger.info(f"{stats} created sequence for models")


def perform_prepare_datasets():
    stats = Statistic()

    queryset = MLDataset.objects.filter(state=DatasetStates.PENDING).order_by("test_suite", "index", "updated")[:30]
    stats.total = queryset.count()
    logger.info(f"{stats} models for preparing datasets are selected")

    for ml_dataset in queryset:
        stats.increase_current()
        logger.debug(f"{stats} preparing for the model {ml_dataset}")
        try:
            result = ml_dataset.prepare()
            stats.increase_success()

            logger.debug(f"{stats} complete preparing for the model {ml_dataset} with result: {result}")

        except Exception as exc:
            stats.increase_failure()
            logger.debug(f"{stats} error preparing for the model {ml_dataset}", exc_info=True)
        finally:
            if stats.progress_percent % 10 == 0:
                logger.info(f"{stats} preparing datasets for models")

    logger.info(f"{stats} prepared datasets for models")


def perform_train_models():
    stats = Statistic()

    queryset = MLModel.objects.filter(
        state=MLStates.PENDING).order_by("updated")[:20]

    for i in queryset:
        print(f"{i.id} {i.updated} {i.state}")

    stats.total = queryset.count()

    logger.info(f"{stats} selected TestSuites to train models")

    for ml_model in queryset:
        stats.increase_current()

        try:
            result = MLModel.train_model(test_suite_id=ml_model.test_suite_id)
            stats.increase_success()

        except Exception as exc:
            stats.increase_failure()
            logger.exception(f"{stats} error training model", exc_info=True)

        finally:
            if stats.progress_percent % 10 == 0:
                logger.info(f"{stats} training models")

    logger.info(f"{stats} trained models")
