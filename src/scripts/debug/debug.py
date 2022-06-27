# -*- coding: utf-8 -*-
import django

django.setup()

import time

import pandas as pd
from django.db.models import F
from applications.ml.models import States, MLModel, create_sequence
from applications.ml.utils.dataset import export_datasets
from applications.ml.network import predict, train_test_model, prepare_dataframe, DEFAULT_PREDICT_ALLOWED_COLUMNS, CatboostClassifierModel
from applications.vcs.models import Commit
from applications.testing.models import Test

organization_id = 73
project_id = 469
test_suite_id = 346
index = 1


# TODO: Test Create sequence
# sequence_queryset = create_sequence(test_suite_id=test_suite_id)
# print(sequence_queryset)


# TODO: Test export dataset to files
# ml_model_queryset = MLModel.objects.filter(test_suite_id=299).select_related("test_suite__project", "test_suite__project__organization").annotate(organization_id=F("test_suite__project__organization_id"), project_id=F("test_suite__project_id")).order_by("organization_id", "project_id", "test_suite_id", "index", "updated")
# for ml_model in ml_model_queryset:
#     print(f"{organization_id} - {project_id} - {test_suite_id} - {ml_model}")
#     export_datasets(
#         organization_id=ml_model.organization_id,
#         project_id=ml_model.project_id,
#         test_suite_id=ml_model.test_suite_id,
#         index=ml_model.index,
#         test_ids=ml_model.tests.values_list("id", flat=True),
#         from_date=ml_model.fr,
#         to_date=ml_model.to
#     )

# TODO: Test train models
# ml_model_queryset = MLModel.objects.filter(test_suite_id=test_suite_id).select_related("test_suite__project", "test_suite__project__organization").annotate(organization_id=F("test_suite__project__organization_id"), project_id=F("test_suite__project_id")).order_by("organization_id", "project_id", "test_suite_id", "index", "updated")

index = 10
ml_model = MLModel.objects.get(test_suite_id=test_suite_id, index=index)

# clf = train_test_model(
#     organization_id=ml_model.test_suite.project.organization_id,
#     project_id=ml_model.test_suite.project_id,
#     test_suite_id=ml_model.test_suite_id,
#     index=ml_model.index,
#     test_ids=ml_model.tests.values_list("id", flat=True)
# )
#
# predict_filepath = "/Users/whenessel/Development/DataShell/appsurify-testbrain-ml/predict/first.json"
# df = pd.read_json(predict_filepath)
#
#
# predicts_df = predict(clf, df)
# print(predicts_df.head())
#
# print(predicts_df["priority"].value_counts())

ccm = CatboostClassifierModel(ml_model=ml_model)
clf = ccm.train()
print(clf.is_fitted)

test_queryset = Test.objects.filter(test_suites=ml_model.test_suite)
commit_queryset = Commit.objects.filter(project_id=ml_model.test_suite.project_id)[:3]

start_time = time.time()
df = ccm.predict(
    tests=test_queryset,
    commits=commit_queryset
)
print("--- %s seconds ---" % (time.time() - start_time))
print(df)

print("##### DICT")
start_time = time.time()
priorities_dict = ccm.predict_by_priority(
    tests=test_queryset,
    commits=commit_queryset
)
print("--- %s seconds ---" % (time.time() - start_time))
for prio, items in priorities_dict.items():
    print(f"\t{prio}: {len(items)}")

print()
start_time = time.time()
priorities_dict = ccm.predict_by_priority(
    tests=test_queryset,
    commits=commit_queryset,
    keyword="404"
)
print("--- %s seconds ---" % (time.time() - start_time))
for prio, items in priorities_dict.items():
    print(f"\t{prio} ('404'): {len(items)}")


print("###### TOP")
start_time = time.time()
items = ccm.predict_by_percent(
    tests=test_queryset,
    commits=commit_queryset
)
print("--- %s seconds ---" % (time.time() - start_time))
print(f"\tTop20: {len(items)}")

print()
start_time = time.time()
items = ccm.predict_by_percent(
    tests=test_queryset,
    commits=commit_queryset,
    keyword="404"
)
print("--- %s seconds ---" % (time.time() - start_time))
print(f"\tTop20 ('404'): {len(items)}")


