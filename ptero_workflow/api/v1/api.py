from flask.ext.restful import Api
from flask.ext.restful.representations import json as flask_json
from . import views


__all__ = ['api']


api = Api(default_mediatype='application/json')
flask_json.settings['indent'] = 4
flask_json.settings['sort_keys'] = True

api.add_resource(views.WorkflowListView, '/workflows', endpoint='workflow-list')

api.add_resource(views.WorkflowDetailView,
    '/workflows/<int:workflow_id>', endpoint='workflow-detail')

api.add_resource(views.ExecutionDetailView,
    '/executions/<int:execution_id>', endpoint='execution-detail')


api.add_resource(views.TaskCallback,
    '/callbacks/tasks/<int:task_id>/callbacks/<string:callback_type>',
    endpoint='task-callback')

api.add_resource(views.MethodCallback,
    '/callbacks/methods/<int:method_id>/callbacks/<string:callback_type>',
    endpoint='method-callback')

api.add_resource(views.ReportDetailView, '/reports/<string:report_type>',
        endpoint='report')
