import io
import pathlib
import gc
import typing
import pickle
import warnings
import pytz
import pandas as pd
import numpy as np
import catboost as cb
from catboost.utils import get_confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix
from nltk.stem import PorterStemmer
from statsmodels.distributions.empirical_distribution import ECDF

from datetime import datetime
from dateutil.relativedelta import relativedelta

from abc import ABC, abstractmethod

from django.conf import settings

from applications.ml.utils.log import logger
from applications.ml.utils.functional import reduce_mem_usage
from applications.ml.utils.dataset import get_dataset_filelist, get_nlp_dataset_filelist
from applications.ml.utils.model import (get_model_directory, get_model_filename, get_nlp_model_filename, predict_sql,
                                         get_riskiness_model_directory, get_riskiness_model_filename)
from applications.ml.utils.text import similarity, similarity_np
from applications.ml.utils.database import native_execute_query
from applications.ml.utils.text import get_vector_from_list


warnings.filterwarnings("ignore")


class CommitRiskinessRFCM(ABC):
    _analyze_type = None

    DEFAULT_TRAIN_ALLOWED_COLUMNS = []

    DEFAULT_PREDICT_ALLOWED_COLUMNS = []

    DEFAULT_TRAIN_PARAMS = {
        "n_jobs": 1,
        "max_features": "sqrt",
        "n_estimators": 200,
        "oob_score": True
    }

    def __init__(self, project):
        self.project_id = project.id
        self.organization_id = project.organization_id

        self.model_directory = get_riskiness_model_directory(organization_id=self.organization_id,
                                                             project_id=self.project_id)
        self.model_filename = get_riskiness_model_filename(analyze_type=self.analyze_type)
        self.model_filepath = self.model_directory / self.model_filename

        self._clf = None
        self._load_classifier()

    @property
    @abstractmethod
    def analyze_type(self): ...

    @property
    def clf(self) -> RandomForestClassifier:
        return self._clf

    @clf.setter
    def clf(self, obj: RandomForestClassifier):
        self._clf = obj

    def _load_classifier(self):
        try:
            self._load_model()
        except Exception as exc:
            self.clf = None

    def _load_model(self):
        if self.model_filepath.stat().st_size > 0:
            infile = open(self.model_filepath, "rb")
            unpickler = pickle.Unpickler(infile)
            self._clf = unpickler.load()
        else:
            raise Exception(f"Empty file: {self.model_filepath}")

    def _save_model(self):
        try:
            outfile = open(self.model_filepath, 'wb')
            pickle.dump(self._clf, outfile, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:
            raise exc

    def load_train_dataset(self, project_id: int) -> pd.DataFrame:
        from applications.vcs.models import Commit
        from_datetime = datetime.now() + relativedelta(weeks=-4)  # TODO: Change!!!
        from_datetime = from_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)
        commits = Commit.objects.filter(project_id=project_id, timestamp__gte=from_datetime).prefetch_related(
            "caused_defects", "founded_defects", "files", "parents")

        dataset = []

        for commit in commits:
            commit_stats = self.get_commit_stats(commit)
            if commit_stats:
                commit_stats["defect_caused"] = 0
                if commit.caused_defects.count():
                    commit_stats["defect_caused"] = 1
                dataset.append(commit_stats)

        dataframe = pd.DataFrame(data=dataset)
        return dataframe

    def load_predict_dataset(self, project_id: int, commit_sha_list: typing.Optional[typing.List]) -> pd.DataFrame:
        from applications.vcs.models import Commit
        from_datetime = datetime.now() + relativedelta(weeks=-1)  # TODO: Change!!!
        from_datetime = from_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)

        commits = Commit.objects.filter(project_id=project_id)
        if commit_sha_list:
            commits = commits.filter(sha__in=commit_sha_list)
        else:
            commits = commits.filter(timestamp__gte=from_datetime)

        dataset = []
        for commit in commits:
            commit_stats = self.get_commit_stats(commit)
            if commit_stats:
                dataset.append(commit_stats)

        dataframe = pd.DataFrame(data=dataset)
        return dataframe

    @abstractmethod
    def get_commit_stats(self, commit) -> typing.Dict: ...

    def _prepare_dataframe(self, df: pd.DataFrame, allowed_columns: typing.Optional[typing.List[str]] = None):
        if allowed_columns is None:
            allowed_columns = []

        if not df.empty:
            if len(allowed_columns) > 0:
                df = df[allowed_columns]
            df.fillna(0)

        return df

    def _predict(self, df: pd.DataFrame) -> pd.DataFrame:
        clf = self.clf
        if not clf:
            raise Exception(f'Model not loaded')

        predict_df = self._prepare_dataframe(df, allowed_columns=self.DEFAULT_PREDICT_ALLOWED_COLUMNS)
        predict_y = predict_df["sha"].values
        predict_X = predict_df.drop(columns=["sha"], axis=1).values
        predicts = clf.predict_proba(X=predict_X)

        if predicts.shape[1] == 1:
            predicts_df = pd.DataFrame({"sha": predict_y, "result": predicts[:, 0]})
        else:
            predicts_df = pd.DataFrame({"sha": predict_y, "result": predicts[:, 1]})

        predicts_df.sort_values(by=["sha", "result"], ignore_index=True, ascending=False, inplace=True)
        predicts_df.drop_duplicates(subset=["sha"], keep="last", ignore_index=True, inplace=True)
        return predicts_df

    def _fit_model(self, df: pd.DataFrame,
                   train_params: typing.Optional[typing.Dict] = None) -> RandomForestClassifier:

        if train_params is None:
            train_params = self.DEFAULT_TRAIN_PARAMS

        y_train = df["defect_caused"].values
        X_train = df.drop(columns=["defect_caused"], axis=1).values

        clf = RandomForestClassifier(**train_params)
        clf.fit(X_train, y_train)
        return clf

    def _train_test_model(self, project_id: int, train_params: typing.Optional[typing.Dict] = None,
                          save_model: typing.Optional[bool] = True):

        df = self.load_train_dataset(project_id=self.project_id)
        df = self._prepare_dataframe(df, allowed_columns=self.DEFAULT_TRAIN_ALLOWED_COLUMNS)

        if df.empty:
            logger.exception(f"Dataset for project {project_id} is empty", exc_info=True)
            raise Exception(f"Dataset for project {project_id} is empty")

        try:
            self.clf = self._fit_model(df, train_params=train_params)
        except Exception as exc:
            logger.exception(f"Error fit classifier for project {project_id}", exc_info=True)
            raise Exception(f"Error fit classifier for project {project_id}")
        if save_model:
            self._save_model()
        return self.clf

    def train(self, force: typing.Optional[bool] = False):

        if self.clf and not force:
            return self

        clf = self._train_test_model(project_id=self.project_id,
                                     train_params=self.DEFAULT_TRAIN_PARAMS,
                                     save_model=True)
        self.clf = clf
        return self

    def predict(self, commit_sha_list: typing.Optional[typing.List] = None) -> pd.DataFrame:
        df = self.load_predict_dataset(project_id=self.project_id, commit_sha_list=commit_sha_list)
        df = self._prepare_dataframe(df, allowed_columns=self.DEFAULT_PREDICT_ALLOWED_COLUMNS)
        predicted_df = self._predict(df)
        return predicted_df

    def predict_to_riskiness(self, commit_sha_list: typing.Optional[typing.List] = None) -> typing.Dict:
        df = self.predict(commit_sha_list=commit_sha_list)
        return df.set_index("sha")["result"].to_dict()


class FastCommitRiskinessRFCM(CommitRiskinessRFCM):
    analyze_type = "fast"

    DEFAULT_TRAIN_ALLOWED_COLUMNS = [
        "defect_caused",
        "deletions",
        "additions",
        "total_lines_modified",
        "dayofweek",
        "hour",
        "len_message",
        "changed_files",
        "changed_directories",
        "changed_subsystems",
        "age",
        "entropy",
    ]

    DEFAULT_PREDICT_ALLOWED_COLUMNS = [
        "sha",
        "deletions",
        "additions",
        "total_lines_modified",
        "dayofweek",
        "hour",
        "len_message",
        "changed_files",
        "changed_directories",
        "changed_subsystems",
        "age",
        "entropy",
    ]

    def get_commit_stats(self, commit):
        import math
        import time

        files_count = commit.files.count()
        total_string_changed = commit.stats.get('total', 0)

        directories = {}
        subsystems = {}

        for commit_file in commit.files.all():
            path_elements = commit_file.full_filename.split('/')

            if commit_file.sha:
                if len(path_elements) == 1:
                    directories['root'] = 1
                    subsystems['root'] = 1
                else:
                    directories['/'.join(path_elements[0:-1])] = 1
                    subsystems[path_elements[0]] = 1

        ages = 0
        parents = commit.parents.all()

        for parent in parents:
            ages += time.mktime(parent.timestamp.timetuple())

        if parents:
            age = time.mktime(commit.timestamp.timetuple()) - (ages / len(parents))
        else:
            age = 0

        try:
            avg = float(files_count) / total_string_changed
            entropy = avg * math.log(avg, 2)
        except:
            entropy = 0

        commit_stats = {
            'sha': commit.sha,
            'deletions': commit.stats.get('deletions', 0),
            'additions': commit.stats.get('additions', 0),
            'total_lines_modified': commit.stats.get('total', 0),
            'dayofweek': commit.timestamp.weekday(),
            'hour': commit.timestamp.hour,
            'len_message': len(commit.message),
            'changed_files': files_count,
            'changed_directories': len(directories),
            'changed_subsystems': len(subsystems),
            'age': age,
            'entropy': entropy,
        }
        return commit_stats


class SlowCommitRiskinessRFCM(CommitRiskinessRFCM):
    analyze_type = "slow"

    DEFAULT_TRAIN_ALLOWED_COLUMNS = [
        "defect_caused",
        "additions",
        "deletions",
        "total_lines_modified",
        "lines_code_before_commit",
        "changed_subsystems",
        "changed_directories",
        "changed_files",
        "developers",
        "files_unique_changes",
        "author_changes",
        "experience_weight",
        "author_changes_subsystem",
        "entropy",
        "age",
    ]

    DEFAULT_PREDICT_ALLOWED_COLUMNS = [
        "sha",
        "additions",
        "deletions",
        "total_lines_modified",
        "lines_code_before_commit",
        "changed_subsystems",
        "changed_directories",
        "changed_files",
        "developers",
        "files_unique_changes",
        "author_changes",
        "experience_weight",
        "author_changes_subsystem",
        "entropy",
        "age",
    ]

    def get_commit_stats(self, commit):
        commit_stats = commit.stats.get("slow_model")
        if commit_stats:
            commit_stats["sha"] = commit.sha
        return commit_stats


class TestPrioritizationNLPCBM(object):
    DEFAULT_TRAIN_PARAMS = {
        "auto_class_weights": "Balanced",
        "iterations": 100,
        "depth": 10
    }

    DEFAULT_TRAIN_GGRR_PARAMS = {
        "iterations": [100, 150, 200],
        "learning_rate": [0.03, 0.1],
        "depth": [2, 4, 6, 8],
        "l2_leaf_reg": [0.2, 0.5, 1, 3]
    }

    DEFAULT_LIST_OF_FEATURES = [
        "test_names_to_commit_files",
        "test_names_to_commit_folders",
        "test_names_to_commit_dependent_areas",
        "test_class_to_commit_areas",
        "test_class_to_commit_files",
        "test_class_to_commit_dependent_areas",
        "test_areas_to_commit_dependent_areas",
    ]

    DEFAULT_TRAIN_COLUMNS = [
        "test_names",
        "test_classes_names",
        "test_areas",
        "defect_closed_by_caused_by_intersection_areas",
        "defect_closed_by_caused_by_intersection_files",
        "defect_closed_by_caused_by_intersection_folders",
        "defect_closed_by_caused_by_intersection_dependent_areas"
    ]

    DEFAULT_TRAIN_TARGET_COLUMN = "test_changed"

    DEFAULT_PREDICT_COLUMNS = [
        "test_names",
        "test_classes_names",
        "test_areas",
        "defect_closed_by_caused_by_intersection_areas",
        "defect_closed_by_caused_by_intersection_files",
        "defect_closed_by_caused_by_intersection_folders",
        "defect_closed_by_caused_by_intersection_dependent_areas"
    ]

    DEFAULT_PREDICT_TARGET_COLUMN = "test_id"

    def _init_ml_model(self, ml_model):
        self.ml_model = ml_model
        self.organization_id = ml_model.test_suite.project.organization_id
        self.project_id = ml_model.test_suite.project_id
        self.test_suite_id = ml_model.test_suite_id

        self.model_directory = get_model_directory(
            organization_id=self.organization_id,
            project_id=self.project_id,
            test_suite_id=self.test_suite_id
        )

        self.model_filename = get_nlp_model_filename(test_suite_id=self.test_suite_id)
        self.model_filepath = str(self.model_directory / self.model_filename)

    def _init_params(self, organization_id, project_id, test_suite_id):
        self.ml_model = None
        self.organization_id = organization_id
        self.project_id = project_id
        self.test_suite_id = test_suite_id

        self.model_directory = get_model_directory(
            organization_id=self.organization_id,
            project_id=self.project_id,
            test_suite_id=self.test_suite_id
        )

        self.model_filename = get_nlp_model_filename(test_suite_id=self.test_suite_id)
        self.model_filepath = str(self.model_directory / self.model_filename)

    def __init__(self, ml_model=None, organization_id=None, project_id=None, test_suite_id=None):
        if ml_model is not None:
            self._init_ml_model(ml_model=ml_model)
        else:
            self._init_params(organization_id=organization_id, project_id=project_id, test_suite_id=test_suite_id)

        self._clf = None
        self._load_model()

    def _load_model(self):
        self.clf = None
        clf = cb.CatBoostClassifier()
        try:
            clf.load_model(self.model_filepath)
            if clf.is_fitted():
                self.clf = clf
        except Exception as exc:
            self.clf = None

    @property
    def clf(self) -> cb.CatBoostClassifier:
        return self._clf

    @clf.setter
    def clf(self, obj: cb.CatBoostClassifier):
        self._clf = obj

    @property
    def is_fitted(self):
        if self._clf is not None:
            return self._clf.is_fitted()
        else:
            return False

    def _read_file(self, filepath) -> pd.DataFrame:
        """ Clean spec symbols """
        file = open(filepath, "r")
        data = file.read()
        if data:
            data = data.replace("\\\\", "\\")
            file_content = io.StringIO(data)
            df = pd.read_json(file_content)
        else:
            df = pd.DataFrame()
        file.close()
        return df

    def _prepare_dataframe(self, df: pd.DataFrame,
                           target_column: typing.AnyStr,
                           target_columns: typing.List[str],
                           list_of_features: typing.List[str]) -> pd.DataFrame:

        prepared_df = pd.DataFrame()

        import tensorflow_hub as hub

        try:
            embed = hub.load(str(pathlib.PosixPath(settings.STORAGE_ROOT) / "universal-sentence-encoder_4"))
        except OSError:
            embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")
        except Exception as exc:
            raise Exception("Error load embed from hub")

        if not df.empty:

            for column_name in target_columns:
                df[column_name] = df[column_name].replace(np.NaN, None)
                df[column_name] = df[column_name].apply(lambda x: x if x is not None else ["Null"])

            new_features = {i: [] for i in list_of_features + [target_column]}

            # Generate features
            for idx, row in df.iterrows():

                test_names = [row.test_names]
                test_classes_names = [row.test_classes_names]
                test_areas = [row.test_areas]
                defect_closed_by_caused_by_intersection_areas = [row.defect_closed_by_caused_by_intersection_areas]
                defect_closed_by_caused_by_intersection_files = [row.defect_closed_by_caused_by_intersection_files]
                defect_closed_by_caused_by_intersection_folders = [row.defect_closed_by_caused_by_intersection_folders]
                defect_closed_by_caused_by_intersection_dependent_areas = [row.defect_closed_by_caused_by_intersection_dependent_areas]

                test_names_vector = get_vector_from_list(test_names, embed=embed)
                test_classes_names_vector = get_vector_from_list(test_classes_names, embed=embed)
                test_areas_vector = get_vector_from_list(test_areas, embed=embed)

                commits_area_vector = get_vector_from_list(defect_closed_by_caused_by_intersection_areas, embed=embed)
                commits_file_vector = get_vector_from_list(defect_closed_by_caused_by_intersection_files, embed=embed)
                commits_folder_vector = get_vector_from_list(defect_closed_by_caused_by_intersection_folders, embed=embed)
                commits_dependent_vector = get_vector_from_list(defect_closed_by_caused_by_intersection_dependent_areas, embed=embed)

                test_names_to_commit_files = similarity_np(test_names_vector, commits_file_vector)
                test_names_to_commit_folders = similarity_np(test_names_vector, commits_folder_vector)
                test_names_to_commit_dependent_areas = similarity_np(test_names_vector, commits_dependent_vector)

                test_class_to_commit_areas = similarity_np(test_classes_names_vector, commits_area_vector)
                test_class_to_commit_files = similarity_np(test_classes_names_vector, commits_file_vector)
                test_class_to_commit_dependent_areas = similarity_np(test_classes_names_vector, commits_dependent_vector)

                test_areas_to_commit_dependent_areas = similarity_np(test_areas_vector, commits_dependent_vector)

                new_features["test_names_to_commit_files"].append(test_names_to_commit_files)
                new_features["test_names_to_commit_folders"].append(test_names_to_commit_folders)
                new_features["test_names_to_commit_dependent_areas"].append(test_names_to_commit_dependent_areas)
                new_features["test_class_to_commit_areas"].append(test_class_to_commit_areas)
                new_features["test_class_to_commit_files"].append(test_class_to_commit_files)
                new_features["test_class_to_commit_dependent_areas"].append(test_class_to_commit_dependent_areas)
                new_features["test_areas_to_commit_dependent_areas"].append(test_areas_to_commit_dependent_areas)

                new_features[target_column].append(row[target_column])

            prepared_df = pd.DataFrame(new_features)
            prepared_df = prepared_df[list_of_features + [target_column]]

        del embed
        del df
        gc.collect()
        return prepared_df

    def _fit_model(self, df: pd.DataFrame, test_size: typing.Optional[float] = 0.5,
                   random_state: int = 0, stratify: typing.Optional[pd.Series] = None,
                   train_params: typing.Optional[typing.Dict] = None) -> cb.CatBoostClassifier:

        if stratify is None:
            stratify = df['test_changed']

        if train_params is None:
            train_params = self.DEFAULT_TRAIN_PARAMS

        train, test = train_test_split(df, test_size=test_size, random_state=random_state, stratify=stratify)

        y_train = train["test_changed"].values
        X_train = train.drop(columns=["test_changed"], axis=1).values

        y_eval = test["test_changed"].values
        X_eval = test.drop(columns=["test_changed"], axis=1).values

        train_data = cb.Pool(X_train, y_train)
        eval_data = cb.Pool(X_eval, y_eval)

        clf = cb.CatBoostClassifier(**train_params)
        clf.fit(train_data, eval_set=eval_data, verbose=False, plot=False)

        imp_f = list(zip(train.drop(columns=["test_changed"], axis=1).columns, clf.get_feature_importance()))
        logger.debug(f"{imp_f}")

        y_pred = clf.predict(X_eval, prediction_type='Class')
        y_pred_proba = clf.predict_proba(X_eval)

        ecdf_0 = ECDF(y_pred_proba[:, 0])
        ecdf_1 = ECDF(y_pred_proba[:, 1])
        score = clf.score(eval_data)

        conf_matrix = confusion_matrix(y_eval, y_pred)
        klass_report = classification_report(y_eval, y_pred, zero_division=True)
        conf_matrix2 = get_confusion_matrix(clf, eval_data, thread_count=-1)

        logger.debug(f"ConfusingMatrix: {conf_matrix}")
        logger.debug(f"ClassReport: {klass_report}")
        logger.debug(f"ConfusingMatrix2: {conf_matrix2}")
        logger.debug(f"Score: {score}")

        return clf

    def _train_test_model(self, organization_id: int, project_id: int, test_suite_id: int,
                         test_size: typing.Optional[float] = 0.5,
                         random_state: int = 0, stratify: typing.Optional[pd.Series] = None,
                         train_params: typing.Optional[typing.Dict] = None,
                         save_model: typing.Optional[bool] = True) -> cb.CatBoostClassifier:

        model = None

        model_directory = get_model_directory(
            organization_id=organization_id,
            project_id=project_id,
            test_suite_id=test_suite_id,

        )
        model_filename = get_nlp_model_filename(test_suite_id=test_suite_id)

        dataset_filelist = get_nlp_dataset_filelist(
            organization_id=organization_id,
            project_id=project_id,
            test_suite_id=test_suite_id
        )

        # total = len(dataset_filelist)
        # current = 0

        dfs = []

        for filepath in dataset_filelist:

            # current += 1
            # print(f"{current} of {total}")

            df_part = self._read_file(filepath)
            try:
                df_part = self._prepare_dataframe(df_part, target_column=self.DEFAULT_TRAIN_TARGET_COLUMN,
                                                  target_columns=self.DEFAULT_TRAIN_COLUMNS,
                                                  list_of_features=self.DEFAULT_LIST_OF_FEATURES)
                df_part = reduce_mem_usage(df=df_part)
                dfs.append(df_part)
                del df_part
                gc.collect()
            except Exception as exc:
                logger.exception(f"Trouble with file: {filepath}", exc_info=True)
                continue

        if not dfs:
            return cb.CatBoostClassifier()

        df = pd.concat(dfs)
        del dfs

        try:
            clf = self._fit_model(df, test_size=test_size,
                                  random_state=random_state,
                                  stratify=df["test_changed"],
                                  train_params=train_params)
            if clf is not None:
                model = clf
        except cb.CatboostError as exc:
            logger.exception(f"catboost error raised with {str(exc)}", exc_info=True)

        if save_model and model is not None:
            model.save_model(str(model_directory / model_filename))

        return model

    def train(self, params: typing.Optional[typing.Dict] = None) -> 'TestPrioritizationNLPCBM':

        if params is None:
            params = {}

        clf = self._train_test_model(
            organization_id=self.organization_id,
            project_id=self.project_id,
            test_suite_id=self.test_suite_id,
            save_model=True
        )
        self.clf = clf
        return self

    def _predict(self, df: pd.DataFrame, keyword: typing.Optional[str] = None) -> pd.DataFrame:

        clf = self.clf

        if not clf.is_fitted():
            raise Exception(f'Model not loaded')

        predict_test_names = df["test_names"].values

        predict_df = self._prepare_dataframe(df, target_column=self.DEFAULT_PREDICT_TARGET_COLUMN,
                                             target_columns=self.DEFAULT_PREDICT_COLUMNS,
                                             list_of_features=self.DEFAULT_LIST_OF_FEATURES)

        predict_y = predict_df["test_id"].values
        predict_X = predict_df.drop(columns=["test_id"], axis=1).values

        try:
            # predicts = clf.predict(predict_X)
            predicts = clf.predict_proba(predict_X)
            predicts = predicts[:, 1]
        except cb.CatboostError as exc:
            logger.exception(f"Predict have error {exc}", exc_info=True)
            predicts = np.full(int(predict_y.shape[0]), 0.0, dtype=float)

        predicts_df = pd.DataFrame({"test_id": predict_y, "result": predicts, "test_names": predict_test_names})
        predicts_df["test_names_str"] = [
            ",".join(map(str, l)) for l in predicts_df["test_names"]]

        # if keyword:
        #     predicts_df["result"] = predicts_df.apply(
        #         lambda x: 1 if x.loc["test_names_str"].str.contains(keyword) else x.loc["result"], axis=1)
        if keyword:
            predicts_df["result"] = predicts_df.apply(
                lambda x: 1.0 if similarity(x.loc["test_names"][0], keyword) >= 0.5 else x.loc["result"], axis=1)

        predicts_df["result"] = predicts_df["result"].round(decimals=3)

        predicts_df["priority"] = pd.cut(predicts_df["result"],
                                         [0, 0.3, 0.69, 0.85, 1.0],
                                         labels=["low", "unassigned", "medium", "high"], precision=3)

        predicts_df.sort_values(by=["result"], ignore_index=True, ascending=False, inplace=True)
        predicts_df.drop_duplicates(subset=["test_id"], keep="last", ignore_index=True, inplace=True)
        return predicts_df

    def predict(self, tests, commits, keyword: typing.Optional[str] = None) -> pd.DataFrame:

        test_ids = list(set(list(tests.values_list("id", flat=True))))
        commit_ids = list(set(list(commits.values_list("id", flat=True))))

        raw_sql = predict_sql(test_ids=test_ids, commit_ids=commit_ids)

        raw_data = native_execute_query(query=raw_sql)

        df = pd.DataFrame(raw_data)

        predicted_df = self._predict(df, keyword=keyword)

        return predicted_df

    def predict_by_priority(self, tests, commits, keyword: typing.Optional[str] = None) -> typing.Dict:
        df = self.predict(
            tests=tests,
            commits=commits,
            keyword=keyword
        )
        df = df.groupby("priority")["test_id"].apply(list)
        return df.to_dict()

    def predict_by_percent(self, tests, commits, percent: typing.Optional[int] = 20,
                           keyword: typing.Optional[str] = None) -> typing.List:
        df = self.predict(tests=tests, commits=commits, keyword=keyword)
        df = df.sort_values(by="result", ignore_index=True, ascending=False)
        df = df.head(int(len(df) * (percent / 100)))
        return df["test_id"].to_list()
