from .base import Base
from ptero_workflow.urls import url_for
from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship, backref
import base64
from ptero_common import nicer_logging
import os
import uuid


__all__ = ['Workflow']


LOG = nicer_logging.getLogger(__name__)



def _generate_uuid():
    return base64.urlsafe_b64encode(uuid.uuid4().bytes)[:-2]


class Workflow(Base):
    __tablename__ = 'workflow'

    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False, index=True)

    net_key = Column(Text, unique=True,
            index=True,
            default=_generate_uuid)

    root_task_id = Column(Integer, ForeignKey('task.id', ondelete='CASCADE',
        use_alter=True))


    root_task = relationship('Task', post_update=True,
            foreign_keys=[root_task_id], lazy='joined', single_parent=True)

    parent_execution_id = Column(Integer, ForeignKey('execution.id',
            ondelete='CASCADE'), nullable=True, index=True)
    parent_execution = relationship('MethodExecution',
            backref=backref('child_workflows',
            passive_deletes='all'),
            foreign_keys=[parent_execution_id])

    start_place_name = 'workflow-start-place'

    # This is the convention of the Petri service that the first token has
    # color 0 and parent_color None
    color = 0
    parent_color = None

    @property
    def links(self):
        results = []

        for name,task in self.tasks.iteritems():
            results.extend(task.input_links)

        return sorted(results,
                key=lambda l: l.source_task.name\
                    + l.destination_task.name)
        return results

    @property
    def tasks(self):
        return self.root_task.method_list[0].children

    @property
    def status(self):
        return self.root_task.method_list[0].status(color=self.color)

    @property
    def executions(self):
        return self.root_task.method_list[0].executions


    @property
    def is_canceled(self):
        return self.root_task.is_canceled

    def cancel(self):
        if self.is_canceled:
            return
        else:
            LOG.info("Canceling workflow ID:NAME (%s:%s)",
                self.id, self.name, extra={'workflowName':self.name})
            for task in self.all_tasks:
                task.cancel()

    def issue_job_delete_requests(self):
        LOG.info("Issueing job delete requests for workflow ID:NAME (%s:%s)",
            self.id, self.name, extra={'workflowName':self.name})
        for task in self.all_tasks:
            task.issue_job_delete_requests()

    @property
    def url(self):
        return url_for('workflow-detail', workflow_id=self.id)

    def get_webhooks(self, *args, **kwargs):
        return self.root_task.method_list[0].get_webhooks(*args, **kwargs)

    def as_dict(self, detailed):
        tasks = {name: task.as_dict(detailed=detailed)
            for name,task in self.tasks.iteritems()
                if name not in ['input connector', 'output connector']}

        result = {
            'tasks': tasks,
            'links': [l.as_dict(detailed=detailed) for l in self.links],
            'inputs': self.root_task.get_inputs(colors=[0], begins=[0]),
            'status': self.status,
            'name': self.name,
        }
        webhooks = self.get_webhooks()
        if webhooks:
            result['webhooks'] = webhooks

        return result

        if detailed:
            result['executions'] = {
                    color: execution.as_dict(detailed=detailed)
                    for color, execution in self.executions.iteritems()}

        return result

    def as_dict_for_summary(self):
        sorted_tasks = sorted(self.tasks.values(),
                key=lambda x: x.topological_index)
        tasks_list = [t.as_dict_for_summary() for t in sorted_tasks
                if t.name not in ['input connector', 'output connector']]

        result = {
            'tasks': tasks_list,
            'status': self.status,
            'name': self.name,
        }
        return result

    def as_skeleton_dict(self):
        tasks = {name: task.as_skeleton_dict()
            for name,task in self.tasks.iteritems()
                if name not in ['input connector', 'output connector']}

        result = {
            'id': self.id,
            'rootTaskId': self.root_task_id,
            'name': self.name,
            'status': self.status,
            'tasks': tasks,
        }
        return result

    def attach_expire_transition(self, transitions, pn, ttl):
        transitions.append({
                'inputs': [pn],
                'action': {
                    'type': 'expire',
                    'ttl_seconds': ttl
                }
            })

    def get_petri_transitions(self):
        transitions = []
        success_place, failure_place = self.root_task.attach_transitions(
                transitions, self.start_place_name)

        success_ttl = os.environ.get('PTERO_WORKFLOW_SUCCEEDED_EXPIRE_SECONDS')
        if success_ttl is not None:
            self.attach_expire_transition(transitions, success_place,
                    int(success_ttl))

        failure_ttl = os.environ.get('PTERO_WORKFLOW_FAILED_EXPIRE_SECONDS')
        if failure_ttl is not None:
            self.attach_expire_transition(transitions, failure_place,
                    int(failure_ttl))

        return transitions

    def get_outputs(self):
        return self.root_task.get_outputs(0)

    def build_petri_net(self):
        return {
            'initialMarking': [self.start_place_name],
            'transitions': self.get_petri_transitions(),
        }
