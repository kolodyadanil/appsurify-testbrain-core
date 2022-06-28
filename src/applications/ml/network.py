import io
import pathlib
import glob
import hashlib
import typing
import warnings
import pandas as pd
import numpy as np
import catboost as cb
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import train_test_split

from applications.ml.utils.log import logger
from applications.ml.utils.crypt import hash_list_values
from applications.ml.utils.dataset import get_dataset_filelist
from applications.ml.utils.model import get_model_directory, get_model_filename, predict_sql
from applications.ml.utils.text import similarity
from applications.ml.utils.database import native_execute_query


warnings.filterwarnings("ignore")

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


def read_file(file) -> pd.DataFrame:
    """ Clean spec symbols """
    data = open(file, "r").read()
    data = data.replace("\\\\", "\\")
    file = io.StringIO(data)
    df = pd.read_json(file)
    return df


def prepare_mlb_classes(files: typing.List, mlb_columns: typing.Optional[typing.List[str]]) -> typing.Dict:

    if mlb_columns is None:
        mlb_columns = DEFAULT_MLB_COLUMNS

    mlb_classes = {}

    for file in files:
        df = read_file(file)

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


def prepare_dataframe(df: pd.DataFrame, allowed_columns: typing.Optional[typing.List[str]] = None,
                      mlb_columns: typing.Optional[typing.List[str]] = None,
                      mlb_classes: typing.Optional[typing.Dict] = None) -> pd.DataFrame:

    if allowed_columns is None:
        allowed_columns = []

    if mlb_columns is None:
        mlb_columns = DEFAULT_MLB_COLUMNS

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
        df.fillna(0)
    return df


def fit_model(df: pd.DataFrame,
              test_size: typing.Optional[float] = 0.25,
              train_params: typing.Optional[typing.Dict] = None,
              required_model_count: typing.Optional[int] = DEFAULT_REQUIRED_MODEL_COUNT,
              max_tries_fit_model: typing.Optional[int] = DEFAULT_MAX_TRIES_FIT_MODEL,
              use_weights: bool = True) -> cb.CatBoostClassifier:

    if train_params is None:
        train_params = DEFAULT_TRAIN_PARAMS

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


def train_test_model(organization_id: int, project_id: int, test_suite_id: int, index: int, test_ids: typing.List[int],
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

    mlb_classes = prepare_mlb_classes(dataset_filelist, mlb_columns=DEFAULT_MLB_COLUMNS)

    models = []
    avg_model = None

    for filepath in dataset_filelist:
        # file_data = read_file(filepath)
        # df = pd.read_json(file_data)
        df = read_file(filepath)

        df = prepare_dataframe(
            df, allowed_columns=DEFAULT_TRAIN_ALLOWED_COLUMNS,
            mlb_columns=DEFAULT_MLB_COLUMNS, mlb_classes=mlb_classes
        )

        if df.empty:
            logger.error(f"{filepath} IS EMPTY")
            continue

        if len(df.index) < 10:
            logger.error(f"{filepath} IS SMALL")
            continue

        try:
            clf = fit_model(df, test_size=test_size, train_params=train_params,
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


def predict(clf: cb.CatBoostClassifier, df: pd.DataFrame, keyword: typing.Optional[str] = None) -> pd.DataFrame:
    predict_test_names = df["test_names"].values

    predict_df = prepare_dataframe(df, allowed_columns=DEFAULT_PREDICT_ALLOWED_COLUMNS)

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


class CatboostClassifierModel(object):

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

        predicted_df = predict(self.clf, df, keyword=keyword)
        return predicted_df

    def train(self, params: typing.Optional[typing.Dict] = None) -> 'CatboostClassifierModel':
        if params is None:
            params = {}

        clf = train_test_model(
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
        df = self.predict(
            tests=tests,
            commits=commits,
            keyword=keyword
        )
        df = df.sort_values(by="result", ignore_index=True, ascending=False)
        df = df.head(int(len(df) * (percent / 100)))
        return df["test_id"].to_list()
