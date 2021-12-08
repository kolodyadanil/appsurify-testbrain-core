# -*- coding: utf-8 -*-
from django.db.models.fields import Field
from django.db.models.lookups import In


@Field.register_lookup
class NotIn(In):
    lookup_name = 'not_in'

    def get_rhs_op(self, connection, rhs):
        return 'NOT IN %s' % rhs