# -*- coding: utf-8 -*-
import os
import django
import pickle
import pandas as pd
import numpy as np
# from sklearn.model_selection import GridSearchCV
from catboost import CatBoostClassifier
# from sklearn.ensemble import ExtraTreesClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import cross_val_score

from django.conf import settings
from django.db import connection

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


class DatasetError(RuntimeError):
    pass


class TestPriorityMLModel(object):

    def __init__(self):
        self.test_areas_binarizer = MultiLabelBinarizer()
        self.test_associated_areas_binarizer = MultiLabelBinarizer()
        self.test_associated_files_binarizer = MultiLabelBinarizer()
        self.test_dependent_areas_binarizer = MultiLabelBinarizer()
        self.test_similarnamed_binarizer = MultiLabelBinarizer()
        self.test_area_similarnamed_binarizer = MultiLabelBinarizer()
        self.test_classes_names_binarizer = MultiLabelBinarizer()
        self.test_names_binarizer = MultiLabelBinarizer()
        self.commit_areas_binarizer = MultiLabelBinarizer()
        self.commit_files_binarizer = MultiLabelBinarizer()
        self.defect_caused_by_commits_files_binarizer = MultiLabelBinarizer()
        self.defect_caused_by_commits_areas_binarizer = MultiLabelBinarizer()
        self.defect_caused_by_commits_dependent_areas_binarizer = MultiLabelBinarizer()
        self.defect_closed_by_caused_by_intersection_files_binarizer = MultiLabelBinarizer()
        self.defect_closed_by_caused_by_intersection_areas_binarizer = MultiLabelBinarizer()
        self.defect_caused_by_commits_folders_binarizer = MultiLabelBinarizer()

        self.classifier = None


class MLHolder(object):

    dataset_sql_script_path = os.path.join(os.path.dirname(__file__),
                                           'collect_dataset_from_testsuite_template_grouped.sql')
    predict_sql_script_path = os.path.join(os.path.dirname(__file__), 'collect_prediction_info_template.sql')

    encode_columns = []
    decode_columns = []

    def __init__(self, test_suite_id, auto_save=True, auto_load=True, **kwargs):
        self.auto_save = auto_save
        self.auto_load = auto_load

        test_suite = TestSuite.objects.get(id=test_suite_id)

        self.test_suite_id = test_suite.id
        self.project_id = test_suite.project_id

        self.model_path = kwargs.get('model_path', None)

        self.base_models_dir = os.path.join(settings.STORAGE_ROOT,
                                            'models', 'predict_tests_priorities', str(self.project_id))
        if self.model_path is None:
            self.model_path = os.path.join(self.base_models_dir, '{}.model'.format(self.test_suite_id))


class MLTrainer(MLHolder):

    encode_columns = [
        ('test_areas', 'test_areas'),
        ('test_associated_areas', 'test_associated_area'),
        ('test_associated_files', 'test_associated_file'),
        ('test_dependent_areas', 'test_dependent_area'),
        ('test_similarnamed', 'test_similarnamed_file'),
        ('test_area_similarnamed', 'test_area_similarnamed_file'),
        ('test_classes_names', 'test_classes_name'),
        ('test_names', 'test_name'),
        ('commit_areas', 'commit_area'),
        ('commit_files', 'commit_file'),
        ('defect_caused_by_commits_files', 'defect_caused_by_commits_file'),
        ('defect_caused_by_commits_areas', 'defect_caused_by_commits_area'),
        ('defect_caused_by_commits_dependent_areas', 'defect_caused_by_commits_dependent_area'),
        ('defect_closed_by_caused_by_intersection_files', 'defect_closed_by_caused_by_intersection_file'),
        ('defect_closed_by_caused_by_intersection_areas', 'defect_closed_by_caused_by_intersection_area'),
        ('defect_caused_by_commits_folders', 'defect_caused_by_commits_folders'),
    ]

    def __init__(self, test_suite_id, **kwargs):
        super(MLTrainer, self).__init__(test_suite_id=test_suite_id, **kwargs)
        self.ml_model = None

    def save(self):
        if self.ml_model is None:
            raise RuntimeError('Please call train first')

        if not os.path.exists(self.base_models_dir):
            os.makedirs(self.base_models_dir)

        with open(self.model_path, 'wb') as outfile:
            pickle.dump(self.ml_model, outfile)

    def train(self):
        sql_template = open(self.dataset_sql_script_path, 'r').read()
        sql = sql_template.format(test_suite_id=self.test_suite_id)
        data = load_data(sql)

        df = pd.DataFrame(data)
        # df = pd.read_csv('/mnt/testbrain-datasets/datasets/forbes/469/{}.csv'.format(self.test_suite_id))

        df.dropna(axis=1, how='all', inplace=True)

        if df.empty:
            raise DatasetError('Empty dataset for this TestSuite id: "{}"'.format(self.test_suite_id))

        if df.shape[0] < 5:
            raise DatasetError('Small dataset for this TestSuite id: "{}"'.format(self.test_suite_id))

        self.ml_model = TestPriorityMLModel()

        df_chunks = [df['test_changed']]
        for column_name, new_columns_prefix in self.encode_columns:
            binarizer = getattr(self.ml_model, column_name + '_binarizer')

            df_chunks.append(pd.DataFrame(
                    binarizer.fit_transform(df.pop(column_name)),
                    columns=(new_columns_prefix + u'_{}'.format(i) for i in binarizer.classes_),
                    index=df.index
                ))

        df = pd.concat(df_chunks, axis=1)

        y = df['test_changed'].values
        x = df.drop('test_changed', axis=1).values

        clf = CatBoostClassifier(auto_class_weights='Balanced', random_state=0, verbose=False)
        clf.fit(x, y)
        self.ml_model.classifier = clf

        # clf = ExtraTreesClassifier(class_weight='balanced_subsample', max_features=None, random_state=0)
        # gscv = GridSearchCV(clf, {'n_estimators': [10, 20, 30]}, scoring='recall_weighted', verbose=3, cv=5)
        # gscv.fit(x, y)
        # clf = gscv.best_estimator_
        # self.ml_model.classifier = gscv.best_estimator_

        cv = 10
        print(cross_val_score(clf, x, y, cv=cv, scoring='recall'))
        print(cross_val_score(clf, x, y, cv=cv))

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
        ('test_areas', 'test_areas'),
        ('test_associated_areas', 'test_associated_area'),
        ('test_associated_files', 'test_associated_file'),
        ('test_dependent_areas', 'test_dependent_area'),
        ('test_similarnamed', 'test_similarnamed_file'),
        ('test_area_similarnamed', 'test_area_similarnamed_file'),
        ('test_classes_names', 'test_classes_name'),
        ('test_names', 'test_name'),
        ('commit_areas', 'commit_area'),
        ('commit_files', 'commit_file'),
        ('defect_caused_by_commits_files', 'defect_caused_by_commits_file'),
        ('defect_caused_by_commits_areas', 'defect_caused_by_commits_area'),
        ('defect_caused_by_commits_dependent_areas', 'defect_caused_by_commits_dependent_area'),
        ('defect_closed_by_caused_by_intersection_files', 'defect_closed_by_caused_by_intersection_file'),
        ('defect_closed_by_caused_by_intersection_areas', 'defect_closed_by_caused_by_intersection_area'),
        ('defect_caused_by_commits_folders', 'defect_caused_by_commits_folders'),
    ]

    def __init__(self, test_suite_id, **kwargs):
        super(MLPredictor, self).__init__(test_suite_id=test_suite_id, **kwargs)
        self.ml_model = None
        if self.auto_load:
            self.load()

    def load(self):
        try:
            with open(self.model_path, 'rb') as infile:
                model = pickle.load(infile)
            self.ml_model = model
        except IOError:
            self.ml_model = None

    @property
    def is_loaded(self):
        return self.ml_model is not None

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
        iterables_for_concatenate.append([[row.pop('commit_rework'), row.pop('commit_riskiness')]])

        for column_name, column_name_ml_prefix in self.decode_columns:
            binalizer = getattr(self.ml_model, column_name_ml_prefix + '_binarizer')

            iterables_for_concatenate.append(
                binalizer.transform([row[column_name]])
            )

        x = np.concatenate(iterables_for_concatenate, axis=1)

        if probability:
            result = self.ml_model.classifier.predict_proba(x)[0]
        else:
            result = self.ml_model.classifier.predict(x)[0]
        return result

    def _predict_tests_priority(self, test_queryset, commit_queryset):
        tests_ids_by_priorities = {'h': set(), 'm': set(), 'l': set(), 'u': set()}

        tests_ids = '({})'.format(', '.join(map(str, test_queryset.values_list('id', flat=True))))
        commits_ids = '({})'.format(', '.join(map(str, commit_queryset.values_list('id', flat=True))))

        sql_template = open(self.predict_sql_script_path, 'r').read()
        sql = sql_template.format(tests_ids=tests_ids, commits_ids=commits_ids)

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
        tests_ids_by_priorities = list()

        tests_ids = '({})'.format(', '.join(map(str, test_queryset.values_list('id', flat=True))))
        commits_ids = '({})'.format(', '.join(map(str, commit_queryset.values_list('id', flat=True))))

        sql_template = open(self.predict_sql_script_path, 'r').read()
        sql = sql_template.format(tests_ids=tests_ids, commits_ids=commits_ids)

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

        count_by_percent = (percent * test_count) / 100

        test_from_ml_normal_filtered = filter(lambda x: x[0] > 0.3, test_from_ml)
        test_from_ml_normal_filtered.sort(key=lambda x: x[0])
        test_from_ml_normal_filtered_ids = list(set([x[1] for x in test_from_ml_normal_filtered]))

        test_from_ml_low_filtered = filter(lambda x: x[0] <= 0.3, test_from_ml)
        test_from_ml_low_filtered.sort(key=lambda x: x[0])
        test_from_ml_low_filtered_ids = list(set([x[1] for x in test_from_ml_low_filtered]))

        if len(test_from_ml_normal_filtered_ids) >= count_by_percent:
            test_ids = test_from_ml_normal_filtered_ids[:count_by_percent]
        else:
            test_ids = test_from_ml_ids[:count_by_percent]

        result = Test.objects.filter(id__in=test_ids)

        return result.distinct('name')
