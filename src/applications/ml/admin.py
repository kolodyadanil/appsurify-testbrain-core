
from django.db import models
from django.contrib import admin
from applications.ml.models import MLModel


class MLModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'test_suite', 'test_count', 'state', 'index', 'from_date', 'to_date', 'created', 'updated')

    def get_queryset(self, request):
        qs = super(MLModelAdmin, self).get_queryset(request)
        return qs.annotate(_test_count=models.Count('tests', distinct=True))

    def test_count(self, obj):
        return obj._test_count

    test_count.short_description = 'tests'
    test_count.admin_order_field = '_test_count'


admin.site.register(MLModel, MLModelAdmin)
