# -*- coding: utf-8 -*-
import os
import pickle

from django.conf import settings


def save_model(model, project_id, model_prefix=''):
    storage_path = settings.STORAGE_ROOT
    directory_path = os.path.join(storage_path, 'models', 'predict_bugs', model_prefix)
    model_name = '{project_id}.model'.format(project_id=project_id)
    model_path = os.path.join(directory_path, model_name)

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    outfile = open(model_path, 'wb')
    pickle.dump(model, outfile, protocol=pickle.HIGHEST_PROTOCOL)
    # pickle.dump(model, outfile, protocol=pickle.HIGHEST_PROTOCOL)

    return model


def load_model(project_id, model_prefix=''):
    storage_path = settings.STORAGE_ROOT
    directory_path = os.path.join(storage_path, 'models', 'predict_bugs', model_prefix)
    model_name = '{project_id}.model'.format(project_id=project_id)
    model_path = os.path.join(directory_path, model_name)
    model = None

    if not os.path.exists(model_path):
        return model

    if os.path.getsize(model_path) > 0:
        try:
            infile = open(model_path, 'rb')
            unpickler = pickle.Unpickler(infile)
            model = unpickler.load()  # TODO if pickle.load not working, try to change pickle.dump protocol
        except Exception as e:
            print(e)
    return model
