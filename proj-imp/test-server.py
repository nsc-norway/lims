# Test configuration for server UI only
from server import *
import time

class OkTask(Task):
    def run(self):
        self.status = "Running..."
        time.sleep(2)


class DummyJob(Job):
    def __init__(self, **kwargs):
        super(DummyJob, self).__init__(**kwargs)
        self.tasks = [
            OkTask(self)
            ] * 20

Job = DummyJob

ProjectTypeWorker.check_lims_credentials = lambda *args: None

app.debug = True
app.run(host="0.0.0.0", port=5001, threaded=True)

