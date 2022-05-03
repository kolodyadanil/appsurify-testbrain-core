# -*- coding: utf-8 -*-


class MultiSerializerViewSetMixin(object):

    def get_serializer_class(self):
        """
        Look for serializer class in self.serializer_action_classes, which
        should be a dict mapping action name (key) to serializer class (value),
        i.e.:

        class MyViewSet(MultiSerializerViewSetMixin, ViewSet):
            serializer_class = MyDefaultSerializer
            serializer_action_classes = {
               'list': MyListSerializer,
               'my_action': MyActionSerializer,
            }

            @action
            def my_action:
                ...

        If there's no entry for that action then just fallback to the regular
        get_serializer_class lookup: self.serializer_class, DefaultSerializer.

        """
        try:
            return self.serializer_action_classes[self.action]
        except (KeyError, AttributeError):
            return super(MultiSerializerViewSetMixin, self).get_serializer_class()

    def get_queryset(self):
        try:
            return self.queryset_action[self.action]
        except (KeyError, AttributeError):
            return super(MultiSerializerViewSetMixin, self).get_queryset()

    def filter_queryset(self, queryset, default=False):
        """
        Given a queryset, filter it with whichever filter backend is in use.

        You are unlikely to want to override this method, although you may need
        to call it either from a list view, or from a custom `get_object`
        method if you want to apply the configured filtering backend to the
        default queryset.
        """
        for backend in list(self.filter_backends):
            try:
                queryset = backend().filter_queryset(self.request, queryset, self, default=default)
            except TypeError:
                queryset = backend().filter_queryset(self.request, queryset, self)
            # except AssertionError:
            #     pass

        return queryset

