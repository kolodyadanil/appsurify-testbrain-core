# -*- coding: utf-8 -*-
import django

django.setup()


from applications.ml.network import MLTrainer


mlt = MLTrainer(test_suite_id=346)
mlt.train()
