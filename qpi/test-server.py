# Test configuration for server UI only
import server
import time
from flask import Flask

class OkTask(server.Task):
    NAME = "OK test task"
    def run(self):
        self.status = "Running..."
        time.sleep(2)

class ErrorTask(server.Task):
    NAME = "Error test task"
    def run(self):
        time.sleep(2)
        self.status = "Produced an error"
        raise RuntimeError("Test error")


class DummyJob(server.Job):
    def __init__(self, *args, **kwargs):
        super(DummyJob, self).__init__(*args, **kwargs)
        self.tasks = [
            OkTask(self)
            for ok in range(8)
            ] + [ErrorTask(self)] + [OkTask(self)]

server.Job = DummyJob

server.ProjectTypeWorker.check_lims_credentials = lambda *args: None

server.app.debug = True
server.app.run(host="0.0.0.0", port=5001, threaded=True)

