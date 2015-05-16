from __future__ import with_statement

import logging
try:
    import simplejson as json
except ImportError:
    import json

logger = logging.getLogger('main.dispatcher.webservice.TaskController')

from tornado.web import HTTPError
from octopus.core.framework import ResourceNotFoundError, BaseResource, queue
from octopus.core.enums.node import *
from octopus.dispatcher.model import TaskGroup, Task
from octopus.dispatcher.webservice import DispatcherBaseResource

ALLOWED_STATUS_VALUES = (NODE_DONE, NODE_CANCELED)


class BadStatusValueResponse(HTTPError):

    error_message = u'Status value not allowed (must be one of %s)' % (u", ".join([unicode(val) for val in ALLOWED_STATUS_VALUES]))

    def __init__(self):
        super(BadStatusValueResponse, self).__init__(400, self.error_message)


class TaskNotFoundError(ResourceNotFoundError):
    '''Raised when a requested task does not exist'''


class TasksResource(DispatcherBaseResource):
    #@queue
    def get(self):
        tasks = self.getDispatchTree().tasks
        tasks = [task.to_json() for task in tasks.values()]
        data = {'tasks': tasks}
        body = json.dumps(data)
        self.set_header('Content-Type', 'application/json')
        self.writeCallback(body)


class DeleteTasksResource(DispatcherBaseResource):
    #@queue
    def post(self):
        data = self.getBodyAsJSON()
        try:
            taskids = data['taskids']
        except:
            raise HTTPError(400, 'Missing entry: "taskids".')
        else:
            taskidsList = taskids.split(",")
            resultList = []

            for i, taskId in enumerate(taskidsList):
                try:
                    taskId = int(taskId)
                except ValueError:
                    logger.warning("A task id to delete is not a correct integer %r (from list: %r)." % (taskId, taskidsList))
                    continue

                try:
                    task = self.getDispatchTree().tasks[taskId]
                except KeyError:
                    logger.warning("Trying to archive task %s that no longer exists." % str(taskId))
                    continue

                if task.nodes.values()[0].status not in ALLOWED_STATUS_VALUES:
                    logger.warning("Preventing archiving of task %s [Bad status]." % str(taskId))
                    continue
                    #return BadStatusValueResponse()

                resultList.append(taskId)
                task.archive()

            self.writeCallback("%d tasks archived successfully" % len(resultList))


class TaskResource(DispatcherBaseResource):
    #@queue
    def get(self, taskID):
        taskID = int(taskID)
        task = self._findTask(taskID)
        odict = {'tasks': [task.to_json()]}
        body = json.dumps(odict)
        self.set_header('Content-Type', 'application/json')
        self.writeCallback(body)

    def _findTask(self, taskId):
        taskId = int(taskId)
        try:
            return self.getDispatchTree().tasks[taskId]
        except KeyError:
            raise TaskNotFoundError(taskId)


class TaskCommentResource(TaskResource):
    #@queue
    def put(self, taskId):
        '''
        Sets a comment on the task.
        '''

        data = self.getBodyAsJSON()
        try:
            comment = data['comment']
        except:
            return HTTPError(400, 'Missing entry: "comment".')
        else:
            taskId = int(taskId)
            task = self._findTask(taskId)

            # Need to force change of tags attr to trigger this listener
            tmp = task.tags.copy()
            tmp["comment"] = comment
            task.tags = tmp.copy()
            # task.tags["comment"] = comment
            self.dispatcher.dispatchTree.toModifyElements.append(task)


class TaskUserResource(TaskResource):
    #@queue
    def put(self, taskId):
        '''
        Sets the user of a task.
        '''
        data = self.getBodyAsJSON()
        try:
            user = data['user']
        except:
            return HTTPError(400, 'Missing entry: "user".')
        else:
            taskId = int(taskId)
            task = self._findTask(taskId)
            task.user = str(user)
            self.dispatcher.dispatchTree.toModifyElements.append(task)


class TaskRamResource(TaskResource):
    #@queue
    def put(self, taskId):
        '''
        Sets the min ram required for a task.
        '''
        data = self.getBodyAsJSON()
        try:
            ramUse = data['ramUse']
        except:
            return HTTPError(400, 'Missing entry: "ramUse".')
        else:
            taskId = int(taskId)
            task = self._findTask(taskId)
            if isinstance(task, Task):
                task.ramUse = int(ramUse)
                self.dispatcher.dispatchTree.toModifyElements.append(task)


class TaskTimerResource(TaskResource):
    #@queue
    def put(self, taskId):
        '''
        Sets the timer for a task.
        '''
        data = self.getBodyAsJSON()
        try:
            timer = data['timer']
        except:
            return HTTPError(400, 'Missing entry: "timer".')
        else:
            taskId = int(taskId)
            task = self._findTask(taskId)
            task.setTimer(timer)
            # set the timer on the parent node of the task as well
            node = task.nodes.values()[0]
            node.timer = timer
            self.dispatcher.dispatchTree.toModifyElements.append(task)
            self.dispatcher.dispatchTree.toModifyElements.append(node)


class TaskEnvResource(TaskResource):
    #@queue
    def post(self, taskId):
        taskId = int(taskId)
        task = self._findTask(taskId)
        data = self.getBodyAsJSON()
        env = data['environment']
        task.environment.clear()
        task.environment.update(env)
        message = "Environment of task %d has successfully been set." % taskId
        self.writeCallback(message)

    #@queue
    def put(self, taskId):
        taskId = int(taskId)
        data = self.getBodyAsJSON()
        if not 'environment' in data:
            return HTTPError(400, "Missing 'environment' key in data.")
        task = self._findTask(taskId)
        env = data['environment']
        task.environment.clear()
        task.environment.update(env)
        message = "Environment of task %d has successfully been updated." % taskId
        self.writeCallback(message)


class TaskArgumentResource(TaskResource):
    #@queue
    def post(self, taskId):
        taskId = int(taskId)
        data = self.getBodyAsJSON()
        if not 'environment' in data:
            return HTTPError(400, "Missing 'environment' key in data.")
        try:
            task = self._findTask(taskId)
        except TaskNotFoundError:
            return HTTPError(404, "Task not found. No such task %d" % taskId)
        arguments = data['arguments']
        task.arguments.clear()
        task.arguments.update(arguments)
        message = "Arguments of task %d have successfully been set." % taskId
        self.writeCallback(message)

    #@queue
    def put(self, taskId):
        taskId = int(taskId)
        task = self._findTask(taskId)
        data = self.getBodyAsJSON()
        arguments = data['arguments']
        task.arguments.update(arguments)
        message = "Arguments of task %d have successfully been updated." % taskId
        self.writeCallback(message)


class TaskCommandResource(TaskResource):
    #@queue
    def get(self, taskId):
        taskId = int(taskId)
        query = self.getBodyAsJSON()
        if 'status' in query:
            filterfunc = lambda command: command.status in [int(s) for s in query['status']]
        else:
            filterfunc = lambda command: True
        try:
            body, rootTaskId = self.filteredTask(taskId, filterfunc)
            body = json.dumps({'commands': body, 'rootTask': rootTaskId})
        except TaskNotFoundError:
            return HTTPError(404, "No such task. Task %d was not found." % taskId)
        else:
            self.set_header('Content-Type', 'application/json')
            self.writeCallback(body)

    def filteredTask(self, taskId, filterfunc):
        root = self._findTask(taskId)
        commands = []
        tasks = [root]
        while tasks:
            task = tasks.pop(0)
            if isinstance(task, TaskGroup):
                for child in task.tasks:
                    tasks.append(child)
            else:
                commands += [c for c in task.commands if filterfunc(c)]
        while root.parent:
            root = root.parent

        return [c.to_json() for c in commands], root.id


class TaskTreeResource(TaskResource):
    #@queue
    def get(self, taskId):
        taskId = int(taskId)
        try:
            data = self.getSubTasks(taskId)
        except RuntimeError, e:
            if e.args[0][0] is TaskNotFoundError:
                return HTTPError(404, "Task %d not found." % taskId)
        else:
            self.set_header('Content-Type', 'application/json')
            self.writeCallback(data)

    def getSubTasks(self, rootTaskId):
        rootTask = self._findTask(rootTaskId)
        tasks = []
        commands = []
        unprocessed = [rootTask]
        while unprocessed:
            task = unprocessed.pop()
            tasks.append(task.to_json())
            if isinstance(task, TaskGroup):
                unprocessed += task.tasks
            else:
                commands += [command.to_json() for command in task.commands]
        return {
            'tasks': tasks,
            'commands': commands
        }


