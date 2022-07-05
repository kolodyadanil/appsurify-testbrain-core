import io
import typing
import pickle
import warnings
import pytz
import pandas as pd
import numpy as np
import catboost as cb
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import train_test_split

from datetime import datetime
from dateutil.relativedelta import relativedelta

from abc import ABC, abstractmethod

from applications.ml.utils.log import logger
from applications.ml.utils.crypt import hash_list_values
from applications.ml.utils.dataset import get_dataset_filelist
from applications.ml.utils.model import (get_model_directory, get_model_filename, predict_sql,
                                         get_riskiness_model_directory, get_riskiness_model_filename)
from applications.ml.utils.text import similarity
from applications.ml.utils.database import native_execute_query


warnings.filterwarnings("ignore")


class TestPrioritizationCBM(object):
    DEFAULT_MLB_COLUMNS = [
        "commit_areas",
        "commit_files",
        "test_names",
        "test_classes_names",
        "test_areas",
        "test_associated_areas",
        "test_associated_files",
        "test_dependent_areas",
        "test_similarnamed",
        "test_area_similarnamed",
        "defect_caused_by_commits_files",
        "defect_caused_by_commits_areas",
        "defect_caused_by_commits_dependent_areas",
        "defect_closed_by_caused_by_intersection_areas",
        "defect_closed_by_caused_by_intersection_files",
        "defect_closed_by_caused_by_intersection_folders",
        "defect_closed_by_caused_by_intersection_dependent_areas",
        "defect_caused_by_commits_folders"
    ]
    DEFAULT_TRAIN_ALLOWED_COLUMNS = [
                                        "test_changed",
                                        "commit_rework",
                                        "commit_riskiness",
                                    ] + DEFAULT_MLB_COLUMNS
    DEFAULT_PREDICT_ALLOWED_COLUMNS = [
                                          "test_id",
                                          "commit_rework",
                                          "commit_riskiness",
                                      ] + DEFAULT_MLB_COLUMNS
    DEFAULT_TRAIN_PARAMS = {
        # "auto_class_weights": "Balanced",
        "iterations": 200,
        "learning_rate": 0.15,
        "loss_function": "Logloss",
        # "eval_metric": "Logloss",
        "custom_loss": ["AUC", "Accuracy"],
        "random_seed": 0,
        "use_best_model": True,
        "verbose": False,
    }

    DEFAULT_REQUIRED_MODEL_COUNT = 5
    DEFAULT_MAX_TRIES_FIT_MODEL = 5

    def __init__(self, ml_model):
        self.ml_model = ml_model
        self.organization_id = ml_model.test_suite.project.organization_id
        self.project_id = ml_model.test_suite.project_id
        self.test_suite_id = ml_model.test_suite_id
        self.index = ml_model.index
        self.test_ids = ml_model.tests.values_list("id", flat=True)

        self.model_directory = get_model_directory(
            organization_id=self.organization_id,
            project_id=self.project_id,
            test_suite_id=self.test_suite_id,
            index=self.index
        )
        self.model_filename = get_model_filename(test_suite_id=self.test_suite_id)
        self.model_filepath = str(self.model_directory / self.model_filename)

        self._clf = None
        self._load_classifier()

    def _load_classifier(self):
        clf = cb.CatBoostClassifier()
        try:
            clf.load_model(self.model_filepath)
            if clf.is_fitted():
                self.clf = clf
        except Exception as exc:
            self.clf = None

    def _read_file(self, file) -> pd.DataFrame:
        """ Clean spec symbols """
        data = open(file, "r").read()
        data = data.replace("\\\\", "\\")
        file = io.StringIO(data)
        df = pd.read_json(file)
        return df

    def _prepare_mlb_classes(self, files: typing.List, mlb_columns: typing.Optional[typing.List[str]]) -> typing.Dict:

        if mlb_columns is None:
            mlb_columns = self.DEFAULT_MLB_COLUMNS

        mlb_classes = {}

        for file in files:
            df = self._read_file(file)

            if df.empty:
                del df
                continue

            for column_name in mlb_columns:
                df[column_name] = df[column_name].replace(np.NaN, None)
                df[column_name] = df[column_name].apply(lambda x: x if x is not None else [])

                df[column_name] = df[column_name].apply(hash_list_values)

                mlb = MultiLabelBinarizer()

                mlb.fit_transform(df.pop(column_name))

                if column_name not in mlb_classes:
                    mlb_classes[column_name] = set()

                mlb_classes[column_name].update(mlb.classes_)

            del df

        return mlb_classes

    def _prepare_dataframe(self, df: pd.DataFrame, allowed_columns: typing.Optional[typing.List[str]] = None,
                          mlb_columns: typing.Optional[typing.List[str]] = None,
                          mlb_classes: typing.Optional[typing.Dict] = None) -> pd.DataFrame:

        if allowed_columns is None:
            allowed_columns = []

        if mlb_columns is None:
            mlb_columns = self.DEFAULT_MLB_COLUMNS

        if mlb_classes is None:
            mlb_classes = {}

        if not df.empty:
            if len(allowed_columns) > 0:
                df = df[allowed_columns]

            for column_name in mlb_columns:
                df[column_name] = df[column_name].replace(np.NaN, None)
                df[column_name] = df[column_name].apply(lambda x: x if x is not None else [])

                df[column_name] = df[column_name].apply(hash_list_values)

                mlb = MultiLabelBinarizer()

                if mlb_classes.get(column_name):
                    mlb.set_params(**{"classes": list(mlb_classes[column_name])})

                df = df.join(
                    pd.DataFrame(
                        mlb.fit_transform(df.pop(column_name)),
                        columns=[f"{column_name}_{i}" for i in mlb.classes_],
                        index=df.index
                    )
                )
            df.fillna(0).astype("int8")
        return df

    def _predict(self, df: pd.DataFrame, keyword: typing.Optional[str] = None) -> pd.DataFrame:
        clf = self.clf
        if not clf.is_fitted():
            raise Exception(f'Model not loaded')

        predict_test_names = df["test_names"].values

        predict_df = self._prepare_dataframe(df, allowed_columns=self.DEFAULT_PREDICT_ALLOWED_COLUMNS)

        predict_y = predict_df["test_id"].values
        predict_X = predict_df.drop(columns=["test_id"], axis=1).values

        predicts = clf.predict(data=predict_X, prediction_type="Probability")
        predicts = predicts[:, 0]
        predicts_df = pd.DataFrame({"test_id": predict_y, "result": predicts, "test_names": predict_test_names})

        if keyword:
            predicts_df["result"] = predicts_df.apply(
                lambda x: 1.0 if similarity(x.loc["test_names"][0], "desktop") >= 0.5 else x.loc["result"], axis=1)

        predicts_df["result"] = predicts_df["result"].round(decimals=2)

        predicts_df["priority"] = pd.cut(predicts_df["result"],
                                         [0, 0.3, 0.7, 0.85, 1.0],
                                         labels=["low", "unassigned", "medium", "high"], precision=2)

        predicts_df.sort_values(by=["test_id", "result"], ignore_index=True, ascending=False, inplace=True)
        predicts_df.drop_duplicates(subset=["test_id"], keep="last", ignore_index=True, inplace=True)
        return predicts_df

    def _fit_model(self, df: pd.DataFrame,
                  test_size: typing.Optional[float] = 0.25,
                  train_params: typing.Optional[typing.Dict] = None,
                  required_model_count: typing.Optional[int] = DEFAULT_REQUIRED_MODEL_COUNT,
                  max_tries_fit_model: typing.Optional[int] = DEFAULT_MAX_TRIES_FIT_MODEL,
                  use_weights: bool = True) -> cb.CatBoostClassifier:

        if train_params is None:
            train_params = self.DEFAULT_TRAIN_PARAMS

        models = []
        avg_model = None

        while len(models) < required_model_count and max_tries_fit_model >= 0:
            max_tries_fit_model -= 1

            train, test = train_test_split(df, test_size=test_size)

            y_train = train["test_changed"].values
            X_train = train.drop(columns=["test_changed"], axis=1).values

            y_eval = test["test_changed"].values
            X_eval = test.drop(columns=["test_changed"], axis=1).values

            train_data = cb.Pool(X_train, y_train)
            eval_data = cb.Pool(X_eval, y_eval)

            clf = cb.CatBoostClassifier(**train_params)
            try:
                clf.fit(train_data, eval_set=eval_data, verbose=False, plot=False)
                models.append(clf)
                bs = clf.get_best_score()
                bi = clf.get_best_iteration()
                logger.debug(f"({len(df.index)}) [{len(models)}/{max_tries_fit_model}] {bs} / {bi}")
            except cb.CatboostError as exc:
                continue

        if len(models) > 0 and use_weights:
            avg_model = cb.sum_models(models, weights=[1.0 / len(models)] * len(models))
        elif len(models) > 0 and not use_weights:
            avg_model = cb.sum_models(models)

        return avg_model

    def _train_test_model(self, organization_id: int, project_id: int, test_suite_id: int, index: int,
                         test_ids: typing.List[int],
                         test_size: typing.Optional[float] = 0.25,
                         train_params: typing.Optional[typing.Dict] = None,
                         required_model_count: typing.Optional[int] = DEFAULT_REQUIRED_MODEL_COUNT,
                         max_tries_fit_model: typing.Optional[int] = DEFAULT_MAX_TRIES_FIT_MODEL,
                         use_weights: bool = True,
                         save_model: typing.Optional[bool] = True) -> cb.CatBoostClassifier:

        model_directory = get_model_directory(
            organization_id=organization_id,
            project_id=project_id,
            test_suite_id=test_suite_id,
            index=index
        )
        model_filename = get_model_filename(test_suite_id=test_suite_id)

        dataset_filelist = get_dataset_filelist(
            organization_id=organization_id,
            project_id=project_id,
            test_suite_id=test_suite_id,
            index=index,
            test_ids=test_ids
        )

        mlb_classes = self._prepare_mlb_classes(dataset_filelist, mlb_columns=self.DEFAULT_MLB_COLUMNS)

        models = []
        avg_model = None

        for filepath in dataset_filelist:
            # file_data = read_file(filepath)
            # df = pd.read_json(file_data)
            df = self._read_file(filepath)

            df = self._prepare_dataframe(
                df, allowed_columns=self.DEFAULT_TRAIN_ALLOWED_COLUMNS,
                mlb_columns=self.DEFAULT_MLB_COLUMNS, mlb_classes=mlb_classes
            )

            if df.empty:
                logger.error(f"{filepath} IS EMPTY")
                continue

            if len(df.index) < 10:
                logger.error(f"{filepath} IS SMALL")
                continue

            try:
                clf = self._fit_model(df, test_size=test_size, train_params=train_params,
                                      required_model_count=required_model_count,
                                      max_tries_fit_model=max_tries_fit_model, use_weights=use_weights)
                if clf is not None:
                    models.append(clf)
            except cb.CatboostError as exc:
                logger.exception(f"catboost error rised with {str(exc)}", exc_info=True)
                continue

        if len(models) > 0 and use_weights:
            avg_model = cb.sum_models(models, weights=[1.0 / len(models)] * len(models))
        elif len(models) > 0 and not use_weights:
            avg_model = cb.sum_models(models)

        if save_model and avg_model is not None:
            avg_model.save_model(str(model_directory / model_filename))

        return avg_model

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

    def predict(self, tests, commits, keyword: typing.Optional[str] = None) -> pd.DataFrame:

        test_ids = list(set(list(tests.values_list("id", flat=True))))
        commit_ids = list(set(list(commits.values_list("id", flat=True))))

        raw_sql = predict_sql(test_ids=test_ids, commit_ids=commit_ids)
        raw_data = native_execute_query(query=raw_sql)
        df = pd.DataFrame(raw_data)

        predicted_df = self._predict(df, keyword=keyword)
        return predicted_df

    def train(self, params: typing.Optional[typing.Dict] = None) -> 'TestPrioritizationCBM':
        if params is None:
            params = {}

        clf = self._train_test_model(
            organization_id=self.organization_id,
            project_id=self.project_id,
            test_suite_id=self.test_suite_id,
            index=self.index,
            test_ids=self.test_ids,
            save_model=True
        )
        self.clf = clf
        return self

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


class CommitRiskinessRFCM(ABC):
    _analyze_type = None

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
        "entropy"
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
        "entropy"
    ]

    DEFAULT_TRAIN_PARAMS = {
        "n_jobs": 1,
        "max_features": "sqrt",
        "n_estimators": 200,
        "oob_score": True
    }

    def __init__(self, project_id: int):
        self.project_id = project_id

        self.model_directory = get_riskiness_model_directory(project_id=project_id)
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
        from_datetime = datetime.now() + relativedelta(weeks=-8)  # TODO: Change!!!
        from_datetime = from_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)
        commits = Commit.objects.filter(project_id=project_id, timestamp__gte=from_datetime).prefetch_related(
            "founded_defects", "files", "parents")

        dataset = []

        for commit in commits:
            commit_stats = self.get_commit_stats(commit)
            commit_stats["defect_caused"] = 0
            if commit.caused_defects.count():
                commit_stats["defect_caused"] = 1
            dataset.append(commit_stats)

        dataframe = pd.DataFrame(data=dataset)
        return dataframe

    def load_predict_dataset(self, project_id: int, commit_sha_list: typing.Optional[typing.List]) -> pd.DataFrame:
        from applications.vcs.models import Commit
        from_datetime = datetime.now() + relativedelta(weeks=-4)  # TODO: Change!!!
        from_datetime = from_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)

        commits = Commit.objects.filter(project_id=project_id, timestamp__gte=from_datetime)
        if commit_sha_list:
            commits = commits.filter(sha__in=commit_sha_list)

        dataset = []
        for commit in commits:
            commit_stats = self.get_commit_stats(commit)
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

        clf = self._train_test_model(project_id=self.project_id, train_params=self.DEFAULT_TRAIN_PARAMS,
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

    def get_commit_stats(self, commit):
        commit_stats = commit.stats.get("slow_model")
        if commit_stats:
            commit_stats["sha"] = commit.sha
        return commit_stats
