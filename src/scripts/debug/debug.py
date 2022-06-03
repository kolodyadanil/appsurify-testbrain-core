# -*- coding: utf-8 -*-
import os
import sys
import pathlib
import django
from os import walk

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()

from applications.ml.models import MLModel, States
from applications.testing.models import TestSuite
from applications.ml.network import train_model, load_model, MLHolder, MLTrainer


class MockMLModel: ...

ml_model = MockMLModel()

ml_model.test_suite_id = 299
ml_model.index = 1

ml_model.model_path = pathlib.PosixPath('/Users/whenessel/Development/PycharmProjects/appsurify-testbrain-core/var/storage/ml/models/70/426/299')
ml_model.model_filename = '1.m'

# ml_model.dataset_filepaths = [
#     pathlib.PosixPath('/Users/whenessel/Development/PycharmProjects/appsurify-testbrain-core/var/storage/ml/datasets/70/426/299/1/49435.csv'),
#     pathlib.PosixPath('/Users/whenessel/Development/PycharmProjects/appsurify-testbrain-core/var/storage/ml/datasets/70/426/299/1/51318.csv'),
#     pathlib.PosixPath('/Users/whenessel/Development/PycharmProjects/appsurify-testbrain-core/var/storage/ml/datasets/70/426/299/1/48997.csv'),
# ]
ml_model.dataset_filepaths = []
base_dir = pathlib.PosixPath('/Users/whenessel/Development/PycharmProjects/appsurify-testbrain-core/var/storage/ml/datasets/70/426/299/1/')
filenames = next(walk(base_dir), (None, None, []))[2]  # [] if no file
for fn in filenames:
    ml_model.dataset_filepaths.append(base_dir / fn)

ml_trainer = MLTrainer(ml_model=ml_model)
ml_trainer.train()
