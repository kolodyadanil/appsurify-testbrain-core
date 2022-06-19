# -*- coding: utf-8 -*-
import os
import django
import pickle
import dask.dataframe as dd
import pandas as pd
import numpy as np
from catboost import CatBoostClassifier
from scipy.sparse import hstack
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import cross_val_score

from django.conf import settings
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist

from applications.testing.models import TestSuite, Test

import warnings
warnings.filterwarnings("ignore")


def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def load_data(sql):
    cursor = connection.cursor()
    cursor.execute(sql)
    data = dictfetchall(cursor)
    return data


def parse_list_entry(data):
    data2 = data.replace("{", "").replace("}", "").split(",")
    return data2


class DatasetError(RuntimeError):
    pass


class TestPriorityMLModel(object):

    def __init__(self):
        self.areas_binarizer = MultiLabelBinarizer(sparse_output=True)
        self.files_binarizer = MultiLabelBinarizer(sparse_output=True)
        self.failedFiles_binarizer = MultiLabelBinarizer(sparse_output=True)
        #not sure what to do with error and reason as they are large text blocks, any thoughts

        self.classifier = None


class MLHolder(object):

    sql_template = open(settings.BASE_DIR / "applications" / "ml" / "sql" / "predict_flaky.sql", "r", encoding="utf-8").read()

    encode_columns = []
    decode_columns = []

    def __init__(self, test_suite_id, auto_save=True, auto_load=True, **kwargs):
        self.auto_save = auto_save
        self.auto_load = auto_load
        #needs to be changed to defect

        self.test_suite_id = test_suite_id
        self.test_suite = TestSuite.objects.get(id=test_suite_id) 

        try:
            self.test_suite_model = self.test_suite.model 
            # self.model_path, self.model_filename = self.test_suite_model.model_path
            # self.model_path.mkdir(parents=True, exist_ok=True)
        except ObjectDoesNotExist:
            self.test_suite_model = None


class MLTrainer(MLHolder):

    encode_columns = [
        ('areas', 'areas'),
        ('files', 'files'),
        ('error', 'error'),
        ('reason', 'reason'),
        ('failedFiles', 'failedFiles'),
        ('averageRuntimeWhenPass', 'averageRuntimeWhenPass'),
        ('runTime', 'runTime'),
        ('numberOfTests', 'numberOfTests'),
        ('numberOfFoundTestRuns', 'numberOfFoundTestRuns'),
        ('numberOfFoundCommits', 'numberOfFoundCommits'),
        ('numberOfReopenCommits', 'numberOfReopenCommits'),
        ('numberOfReopenTestRuns', 'numberOfReopenTestRuns'),
        ('numberOfCreatedByTests', 'numberOfCreatedByTests'),
        ('numberOfReopenedByTests', 'numberOfReopenedByTests'),
        ('reopenedTestRunsByReopenedTests', 'reopenedTestRunsByReopenedTests'),
        ('createdTestRunsByCreatedTests', 'createdTestRunsByCreatedTests'),
    ]

    def __init__(self, test_suite_id, **kwargs):
        super(MLTrainer, self).__init__(test_suite_id=test_suite_id, **kwargs)
        self.model = None

    def save(self):
        if self.test_suite_model:
            model_path, model_filename = self.test_suite_model.model_path
            outfile = open(f"{model_path / model_filename}", "wb")
            pickle.dump(self.model, outfile)
        else:
            # TODO: needs to be changed, should only run if there are more than 10 flaky failures
            ...

    def train(self):
        #needs to be changed for defects
        if not self.test_suite_model:
            raise DatasetError('ML model not exist for TestSuite id: "{}"'.format(self.test_suite_id))

        dataset_path, dataset_filename = self.test_suite_model.dataset_path
        df = dd.read_csv(f"{dataset_path}/{dataset_filename}")

        df = df.drop([c for c in df.columns if df[c].isna().all().compute()], axis=1)

        if len(df.index) == 0:
            raise DatasetError('Empty dataset for this TestSuite id: "{}"'.format(self.test_suite_id))

        if len(df.columns) < 5:
            raise DatasetError('Small dataset for this TestSuite id: "{}"'.format(self.test_suite_id))

        self.model = TestPriorityMLModel()

        x = None
        for column_name, new_columns_prefix in self.encode_columns:
            df[column_name] = df[column_name].apply(parse_list_entry, meta=(column_name, 'object'))
            binarizer = getattr(self.model, column_name + '_binarizer')
            x_chunk = binarizer.fit_transform(df[column_name])
            if x is None:
                x = x_chunk
            else:
                x = hstack([x, x_chunk])

        y = df['defectType'].compute()

        clf = CatBoostClassifier(auto_class_weights='Balanced', random_state=0, verbose=False)
        clf.fit(x, y)
        self.model.classifier = clf

        if self.auto_save:
            self.save()


class MLPredictor(MLHolder):

    HIGH_FLAG = 'h'
    MEDIUM_FLAG = 'm'
    LOW_FLAG = 'l'
    UNASSIGNED_FLAG = 'u'

    PRIORITY_FLAGS_TO_INTERVALS_MAP = {
        HIGH_FLAG:       (0.86, 1.0),
        MEDIUM_FLAG:     (0.71, 0.85),
        UNASSIGNED_FLAG: (0.31, 0.7),
        LOW_FLAG:        (0.0, 0.3),
    }

    decode_columns = [
        ('areas', 'areas'),
        ('files', 'files'),
        ('error', 'error'),
        ('reason', 'reason'),
        ('failedFiles', 'failedFiles'),
        ('averageRuntimeWhenPass', 'averageRuntimeWhenPass'),
        ('runTime', 'runTime'),
        ('numberOfTests', 'numberOfTests'),
        ('numberOfFoundTestRuns', 'numberOfFoundTestRuns'),
        ('numberOfFoundCommits', 'numberOfFoundCommits'),
        ('numberOfReopenCommits', 'numberOfReopenCommits'),
        ('numberOfReopenTestRuns', 'numberOfReopenTestRuns'),
        ('numberOfCreatedByTests', 'numberOfCreatedByTests'),
        ('numberOfReopenedByTests', 'numberOfReopenedByTests'),
        ('reopenedTestRunsByReopenedTests', 'reopenedTestRunsByReopenedTests'),
        ('createdTestRunsByCreatedTests', 'createdTestRunsByCreatedTests'),
    ]

    def __init__(self, test_suite_id, **kwargs):
        super(MLPredictor, self).__init__(test_suite_id=test_suite_id, **kwargs)
        #needs to be changed to defects
        self.model = None
        if self.auto_load:
            self.load()

    def load(self):
        #changed to defects
        self.model = None
        if self.test_suite_model:
            model_path, model_filename = self.test_suite_model.model_path
            try:
                if os.path.getsize(model_path / model_filename) > 0:
                    infile = open(f"{model_path / model_filename}", "rb")
                    unpickler = pickle.Unpickler(infile)
                    self.model = unpickler.load()
            except IOError:
                self.model = None
            except Exception as exc:
                self.model = None

    @property
    def is_loaded(self):
        return self.model is not None

    def _get_flag_from_prediction_num(self, prediction):
        for item in self.PRIORITY_FLAGS_TO_INTERVALS_MAP.items():
            flag = item[0]
            bottom_border, top_border = self.PRIORITY_FLAGS_TO_INTERVALS_MAP[flag]
            if bottom_border <= prediction <= top_border:
                return flag

    def _is_prediction_in_interval(self, prediction, interval):
        bottom_border, top_border = self.PRIORITY_FLAGS_TO_INTERVALS_MAP[interval]
        return True if bottom_border <= prediction <= top_border else False

    def _is_test_high(self, prediction):
        return self._is_prediction_in_interval(prediction, self.HIGH_FLAG)

    def _is_test_medium(self, prediction):
        return self._is_prediction_in_interval(prediction, self.MEDIUM_FLAG)

    def _is_test_low(self, prediction):
        return self._is_prediction_in_interval(prediction, self.LOW_FLAG)

    def _is_test_unassigned(self, prediction):
        return self._is_prediction_in_interval(prediction, self.UNASSIGNED_FLAG)

    def _predict(self, row, probability=False):
        iterables_for_concatenate = list()


        iterables_for_concatenate.append([[row.pop('averageRuntimeWhenPass'), row.pop('runTime'), row.pop('numberOfTests'), row.pop('numberOfFoundTestRuns'), row.pop('numberOfFoundCommits'), row.pop('numberOfReopenCommits')
            , row.pop('numberOfReopenTestRuns'), row.pop('numberOfCreatedByTests'), row.pop('reopenedTestRunsByReopenedTests'), row.pop('createdTestRunsByCreatedTests')]])

        for column_name, column_name_ml_prefix in self.decode_columns:

            binarizer = getattr(self.model, column_name_ml_prefix + '_binarizer')

            iterables_for_concatenate.append(
                binarizer.transform([row[column_name]])
            )

        x = np.concatenate(iterables_for_concatenate, axis=1)

        if probability:
            result = self.model.classifier.predict_proba(x)[0]
        else:
            result = self.model.classifier.predict(x)[0]
        return result

    def _predict_tests_priority(self, test_queryset, commit_queryset):
        tests_ids_by_priorities = {'h': set(), 'm': set(), 'l': set(), 'u': set()}

        tests_ids = '({})'.format(', '.join(map(str, test_queryset.values_list('id', flat=True))))
        commits_ids = '({})'.format(', '.join(map(str, commit_queryset.values_list('id', flat=True))))

        sql = self.sql_template.format(tests_ids=tests_ids, commits_ids=commits_ids)

        data = load_data(sql)
        df = pd.DataFrame(data)

        if df.empty is True:
            tests_ids_by_priorities['u'] = test_queryset
            return tests_ids_by_priorities

        df.dropna(axis=1, how='all', inplace=True)

        for test_id in df['test_id'].unique():

            max_prediction = 0

            for _, row in df[df['test_id'] == test_id].iterrows():

                test_on_commit_prediction = self._predict(row)

                if test_on_commit_prediction > max_prediction:
                    max_prediction = test_on_commit_prediction

                    if self._is_test_high(max_prediction) is True:
                        break

                tests_ids_by_priorities[self._get_flag_from_prediction_num(max_prediction)].add(test_id)

        return tests_ids_by_priorities

    def get_test_prioritization(self, test_queryset, commit_queryset):
        tests_by_priority = self._predict_tests_priority(test_queryset, commit_queryset)
        result = {flag: Test.objects.filter(id__in=tests_ids) for flag, tests_ids in tests_by_priority.items()}
        return result

    def _predict_tests_priority_top_by_percent(self, test_queryset, commit_queryset):
        # will be a single defect and will be only defects
        tests_ids_by_priorities = list()

        tests_ids = '({})'.format(', '.join(map(str, test_queryset.values_list('id', flat=True))))
        commits_ids = '({})'.format(', '.join(map(str, commit_queryset.values_list('id', flat=True))))

        sql = self.sql_template.format(tests_ids=tests_ids, commits_ids=commits_ids)

        data = load_data(sql)
        df = pd.DataFrame(data)

        if df.empty is True:
            for test_id in list(test_queryset.values_list('id', flat=True)):
                tests_ids_by_priorities.append((0.0, test_id))
            return tests_ids_by_priorities

        df.dropna(axis=1, how='all', inplace=True)

        for test_id in df['test_id'].unique():
            max_prediction = 0
            for _, row in df[df['test_id'] == test_id].iterrows():
                test_on_commit_prediction = self._predict(row)
                if test_on_commit_prediction > max_prediction:
                    max_prediction = test_on_commit_prediction
                    if self._is_test_high(max_prediction) is True:
                        break
                tests_ids_by_priorities.append((test_on_commit_prediction, test_id))

        return tests_ids_by_priorities

    def get_test_prioritization_top_by_percent(self, test_queryset, commit_queryset, percent):
        result = Test.objects.none()

        test_from_ml = self._predict_tests_priority_top_by_percent(test_queryset, commit_queryset)
        test_from_ml.sort(key=lambda x: x[0])
        test_from_ml_ids = list(set([x[1] for x in test_from_ml]))

        if len(test_from_ml) == 0:
            return result

        test_count = test_queryset.distinct('id').count()
        if test_count < 10:
            test_count = test_count * 10

        count_by_percent = int((percent * test_count) / 100)

        test_from_ml_normal_filtered = list(filter(lambda x: x[0] > 0.3, test_from_ml))
        test_from_ml_normal_filtered.sort(key=lambda x: x[0])
        test_from_ml_normal_filtered_ids = list(set([x[1] for x in test_from_ml_normal_filtered]))

        test_from_ml_low_filtered = list(filter(lambda x: x[0] <= 0.3, test_from_ml))
        test_from_ml_low_filtered.sort(key=lambda x: x[0])
        test_from_ml_low_filtered_ids = list(set([x[1] for x in test_from_ml_low_filtered]))

        if len(test_from_ml_normal_filtered_ids) >= count_by_percent:
            test_ids = test_from_ml_normal_filtered_ids[:count_by_percent]
        else:
            test_ids = test_from_ml_ids[:count_by_percent]

        result = Test.objects.filter(id__in=test_ids)

        return result.distinct('name')

    @staticmethod
    def _predict_defect_flakiness(defect):
        return 0.0
