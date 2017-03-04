# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict

from django.core.urlresolvers import reverse
from django.shortcuts import redirect

from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter, Route, DynamicDetailRoute
from rest_framework.viewsets import ModelViewSet

from shop import app_settings
from shop.models.product import ProductModel
from shop.rest.money import JSONRenderer
from shop.rest.renderers import DashboardRenderer
from shop.serializers.bases import ProductSerializer


class DashboardRouter(DefaultRouter):
    routes = [
        # List route.
        Route(
            url=r'^{prefix}{trailing_slash}$',
            mapping={
                'get': 'list',
            },
            name='{basename}-list',
            initkwargs={'suffix': 'List'}
        ),
        # Detail route.
        Route(
            url=r'^{prefix}/{lookup}/change{trailing_slash}$',
            mapping={
                'get': 'retrieve',
                'post': 'update',
            },
            name='{basename}-change',
            initkwargs={'suffix': 'Instance'}
        ),
        Route(
            url=r'^{prefix}/add{trailing_slash}$',
            mapping={
                'get': 'new',
                'post': 'create',
            },
            name='{basename}-add',
            initkwargs={'suffix': 'New'}
        ),
        # Dynamically generated detail routes.
        # Generated using @detail_route decorator on methods of the viewset.
        DynamicDetailRoute(
            url=r'^{prefix}/{lookup}/{methodname}{trailing_slash}$',
            name='{basename}-{methodnamehyphen}',
            initkwargs={}
        ),
    ]


class DashboardPaginator(LimitOffsetPagination):
    default_limit = 20


class ProductsDashboard(ModelViewSet):
    renderer_classes = (DashboardRenderer, JSONRenderer, BrowsableAPIRenderer)
    pagination_class = DashboardPaginator
    list_serializer_class = app_settings.PRODUCT_SUMMARY_SERIALIZER
    permission_classes = [IsAuthenticated]
    detail_serializer_classes = {}
    queryset = ProductModel.objects.all()

    def get_serializer_class(self):
        if self.suffix == 'List':
            return self.list_serializer_class
        elif self.suffix == 'Instance':
            instance = self.get_object()
            return self.detail_serializer_classes.get(instance._meta.label_lower, ProductSerializer)
        elif self.suffix == 'New':
            model = self.request.GET.get('model')
            return self.detail_serializer_classes.get(model, ProductSerializer)
        msg = "ViewSet 'ProductsDashboard' is not implemented for action '{}'"
        return self.list_serializer_class  # TODO: use the correct
        raise NotImplementedError(msg.format(self.action))

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        context = self.get_serializer_context()
        kwargs.update(context=context, label='dashboard')
        if kwargs.get('many', False):
            list_fields = ['pk']
            list_fields.extend(self.get_list_display())
            serializer_class.Meta.fields = list_fields  # reorder the fields
        serializer = serializer_class(*args, **kwargs)
        return serializer

    def get_list_display(self):
        if hasattr(self, 'list_display'):
            return self.list_display
        return self.list_serializer_class.Meta.fields

    def get_list_display_links(self):
        if hasattr(self, 'list_display_links'):
            return self.list_display_links
        return self.get_list_display()[:1]

    def get_renderer_context(self):
        template_context = {}
        if self.suffix == 'List':
            list_display_fields = OrderedDict()
            serializer_class = self.list_serializer_class()
            for field_name in self.get_list_display():
                list_display_fields[field_name] = serializer_class.fields[field_name]
            template_context['list_display_fields'] = list_display_fields
            template_context['list_display_links'] = self.get_list_display_links()
            detail_models = {}
            for name, serializer_class in self.detail_serializer_classes.items():
                detail_models[name] = serializer_class.Meta.model._meta.verbose_name
            template_context['detail_models'] = detail_models
            detail_url = reverse('dashboard:product-change', args=(':PK:',))
            template_context['detail_ng_href'] = detail_url.replace(':PK:', '{{ entry.pk }}')

        renderer_context = super(ProductsDashboard, self).get_renderer_context()
        renderer_context['template_context'] = template_context
        return renderer_context

    def new(self, request, *args, **kwargs):
        serializer = self.get_serializer()
        return Response({'serializer': serializer})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return redirect('dashboard:product-list')
        return Response({'serializer': serializer})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'serializer': serializer, 'instance': instance})

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # TODO: handle 'Save', 'Save and continue editing' and 'Cancel'
        # TODO: use request.resolver_match.url_name.split('-') to redirect on list view
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return redirect('dashboard:product-list')

router = DashboardRouter()