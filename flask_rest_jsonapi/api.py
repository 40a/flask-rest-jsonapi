# -*- coding: utf-8 -*-

import inspect
from functools import wraps

from flask_rest_jsonapi.resource import ResourceList


class Api(object):

    def __init__(self, app=None, blueprint=None):
        self.app = app
        self.blueprint = blueprint
        self.resources = []
        self.resource_registry = []

    def init_app(self, app=None, blueprint=None):
        """Update flask application with our api

        :param Application app: a flask application
        """
        if app is not None:
            self.app = app

        if blueprint is not None:
            self.blueprint = blueprint

        for resource in self.resources:
            self.route(resource['resource'],
                       resource['view'],
                       *resource['urls'],
                       url_rule_options=resource['url_rule_options'])

        if self.blueprint is not None:
            self.app.register_blueprint(self.blueprint)

    def route(self, resource, view, *urls, **kwargs):
        """Create an api view.

        :param Resource resource: a resource class inherited from flask_rest_jsonapi.resource.Resource
        :param str view: the view name
        :param list urls: the urls of the view
        :param dict kwargs: additional options of the route
        """
        resource.view = view
        view_func = resource.as_view(view)
        url_rule_options = kwargs.get('url_rule_options') or dict()

        if self.blueprint is not None:
            resource.view = '.'.join([self.blueprint.name, resource.view])
            for url in urls:
                self.blueprint.add_url_rule(url, view_func=view_func, **url_rule_options)
        elif self.app is not None:
            for url in urls:
                self.app.add_url_rule(url, view_func=view_func, **url_rule_options)
        else:
            self.resources.append({'resource': resource,
                                   'view': view,
                                   'urls': urls,
                                   'url_rule_options': url_rule_options})

        self.resource_registry.append(resource)

    def oauth_manager(self, oauth_manager):
        """Use the oauth manager to enable oauth for API

        :param oauth_manager: the oauth manager
        """
        for resource in self.resource_registry:
            if getattr(resource, 'disable_oauth', None) is not True:
                for method in getattr(resource, 'methods', ('GET', 'POST', 'PATCH', 'DELETE')):
                    scope = self.get_scope(resource, method)
                    setattr(resource,
                            method.lower(),
                            oauth_manager.require_oauth(scope)(getattr(resource, method.lower())))

    def scope_setter(self, func):
        """Plug oauth scope setter function to the API

        :param callable func: the callable to use a scope getter
        """
        self.get_scope = func

    @staticmethod
    def get_scope(resource, method):
        """Compute the name of the scope for oauth

        :param Resource resource: the resource manager
        :param str method: an http method
        :return str: the name of the scope
        """
        if ResourceList in inspect.getmro(resource) and method == 'GET':
            prefix = 'list'
        else:
            method_to_prefix = {'GET': 'get',
                                'POST': 'create',
                                'PATCH': 'update',
                                'DELETE': 'delete'}
            prefix = method_to_prefix[method]

        return '_'.join([prefix, resource.schema.opts.type_])

    def permission_manager(self, permission_manager):
        """Use permission manager to enable permission for API

        :param callable permission_manager: the permission manager
        """
        self.check_permissions = permission_manager

        for resource in self.resource_registry:
            if getattr(resource, 'disable_permission', None) is not True:
                for method in getattr(resource, 'methods', ('GET', 'POST', 'PATCH', 'DELETE')):
                    setattr(resource,
                            method.lower(),
                            self.has_permission()(getattr(resource, method.lower())))

    def has_permission(self, *args, **kwargs):
        """Decorator used to check permissions before to call resource manager method
        """
        def wrapper(view):
            @wraps(view)
            def decorated(*view_args, **view_kwargs):
                self.check_permissions(view, view_args, view_kwargs, *args, **kwargs)
                return view(*view_args, **view_kwargs)
            return decorated
        return wrapper

    @staticmethod
    def check_permissions(view, view_args, view_kwargs, *args, **kwargs):
        """The function use to check permissions

        :param callable view: the view
        :param list view_args: view args
        :param dict view_kwargs: view kwargs
        :param list args: decorator args
        :param dict kwargs: decorator kwargs
        """
        raise NotImplementedError
