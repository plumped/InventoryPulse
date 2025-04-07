from rest_framework.response import Response

def generate_related_action(model, serializer_class, filter_field='product', ordering=None):
    def view_func(self, request, pk=None):
        instance = self.get_object()
        filter_kwargs = {filter_field: instance}
        queryset = model.objects.filter(**filter_kwargs)
        if ordering:
            queryset = queryset.order_by(*ordering)
        serializer = serializer_class(queryset, many=True)
        return Response(serializer.data)
    return view_func
