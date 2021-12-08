# -*- coding: utf-8 -*-
from functools32 import lru_cache
import os
import cPickle
import numpy as np
import pandas as pd

from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from django.conf import settings
from django.db import connection

from applications.testing.models import TestSuite, Test
from .similar_named_files_searchers import SimilarNamesSearcher

import time
import monotonic
from datetime import timedelta
import logging
from pympler import muppy, summary
import sys
import platform
import gc


time.monotonic = monotonic.monotonic

logger = logging.getLogger(__name__)


class BaseDataSetCollector(object):
    def __init__(self, test_suite_id):
        # Just for validation
        _ = TestSuite.objects.get(id=test_suite_id)
        self._test_suite_id = test_suite_id

    # common interface to collect dataset for model
    def collect_dataset(self):
        raise NotImplemented()


class SqlDataSetCollector(BaseDataSetCollector):
    _sql_script_path = os.path.join(os.path.dirname(__file__), 'collect_dataset_from_testsuite_template.sql.depricated')

    def __init__(self, *args, **kwargs):
        super(SqlDataSetCollector, self).__init__(*args, **kwargs)
        self._cursor = None

    def _dict_fetchall(self):
        """
        Return all rows from a cursor as a dict
        """
        columns = [col[0] for col in self._cursor.description]
        return [dict(zip(columns, row)) for row in self._cursor.fetchall()]

    def _find_similar_named_files(self, dataset):
        logger.info('Start _find_similar_named_files')

        logger.info('Start prepare names: areas, tests, test_classes')

        # start_time = time.monotonic()
        areas_names = dataset['test_area'].unique().tolist()
        # end_time = time.monotonic()
        # logger.info('Complete areas_names: {}'.format(timedelta(seconds=end_time - start_time)))

        # start_time = time.monotonic()
        test_names = dataset['test_name'].unique().tolist()
        # end_time = time.monotonic()
        # logger.info('Complete test_names: {}'.format(timedelta(seconds=end_time - start_time)))

        # start_time = time.monotonic()
        test_classes_names = dataset['test_class_name'].unique().tolist()
        # end_time = time.monotonic()
        # logger.info('Complete test_classes_names: {}'.format(timedelta(seconds=end_time - start_time)))

        test_suite = TestSuite.objects.get(id=self._test_suite_id)

        logger.info('Initialize SimilarNamesSearcher')
        searcher = SimilarNamesSearcher(test_suite.project_id)

        logger.info('Call searcher.get_similar_words')
        start_time = time.monotonic()
        grouped_similar_words = searcher.get_similar_words(areas_names + test_classes_names + test_names)
        end_time = time.monotonic()
        logger.info('Complete searcher.get_similar_words: {}'.format(timedelta(seconds=end_time - start_time)))

        for group in dataset.groupby(['test_name', 'test_class_name']):
            test_name, test_class_name = group[0]
            similar_named_files = grouped_similar_words[test_name]
            similar_named_files.update(grouped_similar_words[test_class_name])
            if len(similar_named_files) != 0:
                similar_named_files = ', '.join(similar_named_files)
                dataset.loc[(dataset['test_name'] == test_name) & (dataset['test_class_name'] == test_class_name),
                    'test_similarnamed'
                ] = similar_named_files

        for area_name in areas_names:
            similar_named_files = ', '.join(grouped_similar_words[area_name])
            dataset.loc[dataset['test_area'] == area_name, 'test_area_similarnamed'] = similar_named_files

        return dataset

    def collect_dataset(self):
        with open(self._sql_script_path, 'r') as sql_script_file:
            collect_dataset_script = sql_script_file.read().format(test_suite_id=self._test_suite_id)
        self._cursor = connection.cursor()
        self._cursor.execute(collect_dataset_script)

        dataset = pd.DataFrame(self._dict_fetchall())

        # Drop rows where all columns contain NA values.
        dataset = dataset.dropna(axis=1, how='all')

        self._cursor = None

        logger.info('Call ._find_similar_named_files(dataset)')
        start_time = time.monotonic()
        dataset = self._find_similar_named_files(dataset)
        end_time = time.monotonic()
        logger.info('Complete  ._find_similar_named_files(dataset): {}'.format(timedelta(seconds=end_time - start_time)))
        return dataset


# TODO: Need rewrite with normal class inheritance
class SqlPredictionInfoCollector(object):
    _sql_script_path = os.path.join(os.path.dirname(__file__), 'collect_prediction_info_template.sql')

    def __init__(self, project_id):
        self.project_id = project_id
        self._cursor = None

    def _dict_fetchall(self):
        """
        Return all rows from a cursor as a dict
        """
        columns = [col[0] for col in self._cursor.description]
        return [dict(zip(columns, row)) for row in self._cursor.fetchall()]

    def _find_similar_named_files(self, dataset):
        areas_names = dataset['test_area'].unique().tolist()
        test_names = dataset['test_name'].unique().tolist()
        test_classes_names = dataset['test_class_name'].unique().tolist()

        searcher = SimilarNamesSearcher(self.project_id)
        grouped_similar_words = searcher.get_similar_words(areas_names + test_classes_names + test_names)

        for group in dataset.groupby(['test_name', 'test_class_name']):
            test_name, test_class_name = group[0]
            similar_named_files = grouped_similar_words[test_name]
            similar_named_files.update(grouped_similar_words[test_class_name])
            if len(similar_named_files) != 0:
                dataset.loc[
                    (dataset['test_name'] == test_name) &
                    (dataset['test_class_name'] == test_class_name),
                    'test_similarnamed'] = ', '.join(similar_named_files)

        for area_name in areas_names:
            similar_named_files = ', '.join(grouped_similar_words[area_name])
            dataset.loc[dataset['test_area'] == area_name, 'test_area_similarnamed'] = similar_named_files

    def collect_dataset(self, tests, commits):
        # TODO: move calling sql script into separated function
        tests_ids = '(' + ','.join([str(test_id) for test_id in tests.values_list('id', flat=True)]) + ')'
        commits_ids = '(' + ','.join([str(commit_id) for commit_id in commits.values_list('id', flat=True)]) + ')'
        with open(self._sql_script_path, 'r') as sql_script_file:
            collect_dataset_script = sql_script_file.read().format(tests_ids=tests_ids, commits_ids=commits_ids)

        self._cursor = connection.cursor()
        self._cursor.execute(collect_dataset_script)

        dataset = pd.DataFrame(self._dict_fetchall())
        if dataset.empty is True:
            raise RuntimeError('dataset is empty.')

        # Drop rows where all columns contain NA values.
        dataset = dataset.dropna(axis=1, how='all')
        self._cursor = None
        self._find_similar_named_files(dataset)
        return dataset


# TODO: When refactoring will happens create common base class for model holder
class BaseModelHolder(object):
    _models_dir = os.path.join(settings.STORAGE_ROOT, 'models', 'predict_tests_priorities')

    def __init__(self, test_suite_id):
        self._test_suite_id = test_suite_id
        self._model_path = os.path.join(self._models_dir, '%s.model' % self._test_suite_id)

    def save_model(self, model):
        if not os.path.exists(self._models_dir):
            os.makedirs(self._models_dir)

        with open(self._model_path, 'wb') as outfile:
            cPickle.dump(model, outfile)
        return None

    def load_model(self):
        if not os.path.exists(self._model_path):
            return None

        with open(self._model_path, 'rb') as infile:
            model = cPickle.load(infile)
        return model

    def is_model_created(self):
        if os.path.exists(self._model_path):
            return True
        return False


class MlModel(object):
    def __init__(self):

        self.test_area_binarizer = MultiLabelBinarizer()
        self.test_associated_areas_binarizer = MultiLabelBinarizer()
        self.test_associated_files_binarizer = MultiLabelBinarizer()
        self.test_dependent_areas_binarizer = MultiLabelBinarizer()
        self.test_similarnamed_binarizer = MultiLabelBinarizer()
        self.test_area_similarnamed_binarizer = MultiLabelBinarizer()

        self.commit_areas_binarizer = MultiLabelBinarizer()
        self.commit_files_binarizer = MultiLabelBinarizer()

        self.defect_closed_by_caused_by_commits_files_binarizer = MultiLabelBinarizer()
        self.defect_closed_by_caused_by_commits_areas_binarizer = MultiLabelBinarizer()
        self.defect_closed_by_caused_by_commits_dependent_areas_binarizer = MultiLabelBinarizer()
        self.defect_closed_by_caused_by_intersection_files_binarizer = MultiLabelBinarizer()
        self.defect_closed_by_caused_by_intersection_areas_binarizer = MultiLabelBinarizer()

        self.classifier = None


class ModelBuilder(object):
    _variables_list = [
        'test_result_type',
        'test_area',
        'test_associated_areas',
        'test_associated_files',
        'test_dependent_areas',
        'test_similarnamed',
        'test_area_similarnamed',

        'commit_rework',
        'commit_riskiness',
        'commit_areas',
        'commit_files',

        'defect_closed_by_caused_by_commits_files',
        'defect_closed_by_caused_by_commits_areas',
        'defect_closed_by_caused_by_commits_dependent_areas',
        'defect_closed_by_caused_by_intersection_files',
        'defect_closed_by_caused_by_intersection_areas',
    ]

    _params_dict = {'n_estimators': [10, 20, 30]}

    def __init__(self, test_suite_id):
        # Internal info
        self.test_suite_id = test_suite_id
        self.model_holder = BaseModelHolder(test_suite_id)
        self.dataset_collector = SqlDataSetCollector(test_suite_id)

        # Raw data.
        self.df = None

        # Model
        self.ml_model = MlModel()

    @staticmethod
    def _process_list(lst):
        """
        Simplifies list of strings

        :param lst:
        :return:
        """
        lst = list(set(lst))
        nl = []
        for s in lst:
            s = s.strip().lower().replace(' ', '_')
            nl.append(s)
        return nl

    @staticmethod
    def _get_splitted_column_name(name):
        return name + '_splitted'

    def _split_data_frame_column(self, column_name, callbacks_lst, fillna=True):
        if fillna:
            self.df[column_name].fillna(u'0', inplace=True)

        column_data = self.df[column_name]
        # column_data_lowered = column_data.str.lower()
        self.df[column_name] = column_data

        new_column_name = self._get_splitted_column_name(column_name)

        logger.info('Rename column: {} > {}'.format(column_name, new_column_name))
        self.df.rename(columns={column_name: new_column_name}, inplace=True)

        self.df[new_column_name] = self.df[new_column_name].str.split(',', expand=False)

        # TODO: Original
        # self.df[new_column_name] = self.df[column_name].str.split(',', expand=False)
        # self.df.drop(column_name, axis=1, inplace=True)

        if callbacks_lst is not None:
            for callback in callbacks_lst:
                self.df[new_column_name] = self.df[new_column_name].apply(callback)
        return None

    def _parse_raw_data(self):
        # Parse goal variable
        self.df['test_changed'] = 0
        self.df.loc[self.df['test_result_type'] == 'Changed', 'test_changed'] = 1
        self.df.drop('test_result_type', axis=1, inplace=True)

        # Recode riskiness
        self.df['commit_riskiness'] = (self.df['commit_riskiness'].astype(float) * 100).apply(int)

        logger.info('Start parsing test area')

        # Parse test area
        self.df['test_area'] = self.df['test_area'].str.lower()
        self.df['test_area_splitted'] = self.df['test_area'].str.split('.', expand=False)

        self.df.drop('test_area', axis=1, inplace=True)
        logger.info('Complete parsing test area')

        column_names_list = [
            ('test_associated_files', [self._process_list], True),
            ('test_associated_areas', [self._process_list], True),
            ('test_dependent_areas', [self._process_list], True),
            ('test_similarnamed', [self._process_list], True),
            ('test_area_similarnamed', [self._process_list], True),

            ('commit_areas', [self._process_list], False),
            ('commit_files', [self._process_list], False),

            ('defect_closed_by_caused_by_commits_files', None, True),
            ('defect_closed_by_caused_by_commits_areas', None, True),
            ('defect_closed_by_caused_by_commits_dependent_areas', None, True),
            ('defect_closed_by_caused_by_intersection_files', None, True),
            ('defect_closed_by_caused_by_intersection_areas', None, True),

        ]

        logger.info('Start foreach "column_names_list" ...')

        for column_name, callbacks, fillna_flag, in column_names_list:
            logger.info('Call private method _split_data_frame_column(): {} - {}'.format(column_name, fillna_flag))
            start_time = time.monotonic()
            self._split_data_frame_column(column_name, callbacks, fillna_flag)
            end_time = time.monotonic()
            logger.info('Complete private method _split_data_frame_column(): {} - {}'.format(column_name, timedelta(seconds=end_time - start_time)))

        logger.info('Complete foreach "column_names_list" ...')

    def _one_hot_encode_raw_data(self):
        encode_columns = [
                          ('test_area', 'test_area'),
                          ('test_associated_areas', 'test_associated_area'),
                          ('test_associated_files', 'test_associated_file'),
                          ('test_dependent_areas', 'test_dependent_area'),
                          ('test_similarnamed', 'test_similarnamed_file'),
                          ('test_area_similarnamed', 'test_area_similarnamed_file'),

                          ('commit_areas', 'commit_area'),
                          ('commit_files', 'commit_file'),

                          ('defect_closed_by_caused_by_commits_files', 'defect_closed_by_caused_by_commits_file'),
                          ('defect_closed_by_caused_by_commits_areas', 'defect_closed_by_caused_by_commits_area'),
                          ('defect_closed_by_caused_by_commits_dependent_areas', 'defect_closed_by_caused_by_commits_dependent_area'),
                          ('defect_closed_by_caused_by_intersection_files', 'defect_closed_by_caused_by_intersection_file'),
                          ('defect_closed_by_caused_by_intersection_areas', 'defect_closed_by_caused_by_intersection_area'),
        ]
        for column_name, new_columns_prefix in encode_columns:
            binalizer = getattr(self.ml_model, column_name + '_binarizer')
            splitted_column_name = self._get_splitted_column_name(column_name)
            self.df = self.df.join(
                pd.DataFrame(
                    binalizer.fit_transform(self.df.pop(splitted_column_name)),
                    columns=(new_columns_prefix + '_{}'.format(i) for i in binalizer.classes_),
                    index=self.df.index
                )
            )
        return

    def _recode_variables(self):
        """
        Recode local variables in the internal DataFrame for the calculations
        :return: None
        """
        logger.info('Start private method ._recode_variables()')
        logger.info('Call private method ._parse_raw_data()')
        start_time = time.monotonic()
        self._parse_raw_data()
        end_time = time.monotonic()
        logger.info('Complete ._parse_raw_data(): {}'.format(timedelta(seconds=end_time - start_time)))

        logger.info('Call private method ._one_hot_encode_raw_data()')
        start_time = time.monotonic()
        self._one_hot_encode_raw_data()
        end_time = time.monotonic()
        logger.info('Complete ._one_hot_encode_raw_data(): {}'.format(timedelta(seconds=end_time - start_time)))

    def _prepare_model(self):
        """
        Prepares the model from the source data and grid of parameters
        :return: None
        """
        y = self.df['test_changed'].values
        x = self.df.drop('test_changed', axis=1).values
        clf = ExtraTreesClassifier(class_weight='balanced_subsample', max_features=None, random_state=0)
        gscv = GridSearchCV(clf, self._params_dict, scoring='recall_weighted', verbose=3, cv=5)
        gscv.fit(x, y)
        self.ml_model.classifier = gscv.best_estimator_

    def _load_data(self):
        """
        Load internal DataFrame
        :return: None
        """
        logger.info('Start private method .dataset_collector.collect_dataset()')
        data_frame = self.dataset_collector.collect_dataset()
        self.df = data_frame
        self.df = self.df[self._variables_list]
        logger.info('Complete private method .dataset_collector.collect_dataset()')

    def _save_model(self):
        self.model_holder.save_model(self.ml_model)

    def build_model(self):
        # from pympler import muppy, summary
        # all_objects = muppy.get_objects()
        # sum1 = summary.summarize(all_objects)
        # summary.print_(sum1)

        logger.info('Call private method ._load_data()')
        start_time = time.monotonic()
        self._load_data()
        end_time = time.monotonic()
        logger.info('Complete private method ._load_data(): {}'.format(timedelta(seconds=end_time - start_time)))

        logger.info('Call private method ._recode_variables()')
        start_time = time.monotonic()
        self._recode_variables()
        end_time = time.monotonic()
        logger.info('Complete private method ._recode_variables(): {}'.format(timedelta(seconds=end_time - start_time)))

        self._prepare_model()
        self._save_model()


class ModelRunner(object):

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

    def __init__(self, test_suite_id):
        """
        Initialization with the saved model filename
        """

        self._model_holder = BaseModelHolder(test_suite_id)
        if not self._model_holder.is_model_created():
            raise Exception('File with model not found')
        self._ml_model = self._model_holder.load_model()

    @staticmethod
    def _parse_test_area(test_area):
        """
        Parse test area for the further processing
        :param test_area: Test area (string)
        :return: List of strings splitted by dot
        """
        return test_area.lower().split('.')

    @staticmethod
    def _parse_comma_separated_area(cs_area):
        """
        Parse comma separated area for the further processing
        :param cs_area: Comma separated area (string) or None
        :return: List of strings splitted by comma or '0' string array
        """
        if cs_area is not None or cs_area == '':
            return list(set(cs_area.lower().split(',')))
        else:
            return ['0']

    # TODO: rename, because it is used for processing files too
    @staticmethod
    def _parse_commit_areas(commit_areas):
        """
        Parse list of commit areas for the further processing
        :param commit_areas: List of commit areas (list of strings)
        :return: List of parsed strings
        """
        lst = ModelRunner._parse_comma_separated_area(commit_areas)
        nl = []
        for s in lst:
            s = s.strip().lower().replace(' ', '_')
            nl.append(s)
        return nl

    @lru_cache(maxsize=100000)
    def _predict(self,
                 test_area,
                 test_associated_areas,
                 test_associated_files,
                 test_dependent_areas,
                 test_similarnamed,
                 test_area_similarnamed,
                 commit_rework,
                 commit_riskiness,
                 commit_areas,
                 commit_files,
                 defect_closed_by_caused_by_commits_files,
                 defect_closed_by_caused_by_commits_areas,
                 defect_closed_by_caused_by_commits_dependent_areas,
                 defect_closed_by_caused_by_intersection_files,
                 defect_closed_by_caused_by_intersection_areas,
                 probability=False):
        # TODO: add new params in docstrings
        """
        Make a prediction of commit fail
        :param commit_rework: int
        :param commit_areas: list of strings
        :param test_area: string
        :param commit_riskiness: float as string
        :param defect_caused_by_commits_dependent_areas: list of strings
        :param defect_closed_by_commits_dependent_areas: list of strings
        :param defect_closed_by_caused_by_union_dependent_areas: list of strings
        :param defect_caused_by_commits_files: list of strings
        :param probability: Calculate fail probability pair (0-1) instead of fail prediction?
        :return: 1 if commit will fail, otherwise 0. Probability pair (0-1)
        """
        iterables_for_concatenate = list()
        iterables_for_concatenate.append([[commit_rework, int(float(commit_riskiness) * 100)]])
        args_for_binarizers = (
            ('test_area', self._parse_test_area),
            ('test_associated_areas', self._parse_comma_separated_area),
            ('test_associated_files', self._parse_comma_separated_area),
            ('test_dependent_areas', self._parse_comma_separated_area),
            ('test_similarnamed', self._parse_comma_separated_area),
            ('test_area_similarnamed', self._parse_comma_separated_area),
            ('commit_areas', self._parse_commit_areas),
            ('commit_files', self._parse_comma_separated_area),
            ('defect_closed_by_caused_by_commits_files', self._parse_comma_separated_area),
            ('defect_closed_by_caused_by_commits_areas', self._parse_comma_separated_area),
            ('defect_closed_by_caused_by_commits_dependent_areas', self._parse_comma_separated_area),
            ('defect_closed_by_caused_by_intersection_files', self._parse_comma_separated_area),
            ('defect_closed_by_caused_by_intersection_areas', self._parse_comma_separated_area),
        )
        loc_variables = locals()
        for arg, parsing_function in args_for_binarizers:
                binalizer = getattr(self._ml_model, arg + '_binarizer')
                parsed_arg = parsing_function(loc_variables[arg])
                iterables_for_concatenate.append(binalizer.transform([parsed_arg]))
        x = np.concatenate(iterables_for_concatenate, axis=1)
        if probability:
            return self._ml_model.classifier.predict_proba(x)[0]
        else:
            return self._ml_model.classifier.predict(x)[0]

    def _predict_tests_priority(self, tests_queryset, commits_queryset, project_id):
        info_collector = SqlPredictionInfoCollector(project_id)
        try:
            info_for_prediction = info_collector.collect_dataset(tests_queryset, commits_queryset)
        except RuntimeError:
            return {'h': set(), 'm': set(), 'l': set(), 'u': tests_queryset}
        tests_ids_by_priorities = {'h': set(), 'm': set(), 'l': set(), 'u': set()}
        for test_id in info_for_prediction['test_id'].unique():
            max_prediction = 0
            for _, row in info_for_prediction[info_for_prediction['test_id'] == test_id].iterrows():
                test_on_commit_prediction = self._predict(
                    row['test_area'],
                    row['test_associated_areas'],
                    row['test_associated_files'],
                    row['test_dependent_areas'],
                    row['test_similarnamed'],
                    row['test_area_similarnamed'],
                    row['commit_rework'],
                    row['commit_riskiness'],
                    row['commit_areas'],
                    row['commit_files'],
                    row['defect_closed_by_caused_by_commits_files'],
                    row['defect_closed_by_caused_by_commits_areas'],
                    row['defect_closed_by_caused_by_commits_dependent_areas'],
                    row['defect_closed_by_caused_by_intersection_files'],
                    row['defect_closed_by_caused_by_intersection_areas'],
                )
                if test_on_commit_prediction > max_prediction:
                    max_prediction = test_on_commit_prediction
                    # We get highest test prioritization level on all commits,
                    # so if we already has high level there is no need to continue
                    if self._is_test_high(max_prediction) is True:
                        break
                tests_ids_by_priorities[self._get_flag_from_prediction_num(max_prediction)].add(test_id)
        return tests_ids_by_priorities

    def get_test_prioritization(self, tests_queryset, commits_queryset, project_id):
        tests_by_priority = self._predict_tests_priority(tests_queryset, commits_queryset, project_id)
        return {flag: Test.objects.filter(id__in=tests_ids) for flag, tests_ids in tests_by_priority.items()}


