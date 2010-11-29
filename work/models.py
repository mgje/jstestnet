
import json

from django.db import models

from system.models import TestSuite

class Worker(models.Model):
    user_agent = models.CharField(max_length=255)
    last_heartbeat = models.DateTimeField(null=True)
    is_alive = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    def restart(self):
        q = WorkQueue(
            worker=self,
            cmd='restart',
            description='Server said restart. Goodbye!',
            cmd_args=json.dumps([]),
        )
        q.save()

    def run_test(self, test):
        q = WorkQueue(
            worker=self,
            cmd='run_test',
            description='Running test suite.',
            cmd_args=json.dumps([{
                'test_run_id': test.id,
                'url': test.test_suite.url,
                'name': test.test_suite.name
            }]),
        )
        q.save()
        tq = TestRunQueue(test_run=test, work_queue=q)
        tq.save()

class TestRun(models.Model):
    test_suite = models.ForeignKey(TestSuite)
    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    def is_finished(self):
        # TODO(Kumar) maybe do something here if a worker
        # has died while running the test (i.e. it will never finish)
        q = TestRunQueue.objects.filter(test_run=self,
                                        work_queue__finished=False)
        return q.count() == 0

class WorkQueue(models.Model):
    worker = models.ForeignKey(Worker)
    # The cmds should match those in media/js/system/work.js
    cmd = models.CharField(max_length=25,
                           choices=((f,f) for f in
                                    ['run_test','reload','change_rate']))
    cmd_args = models.TextField()
    description = models.CharField(max_length=255)
    work_received = models.BooleanField(default=False)
    finished = models.BooleanField(default=False)
    results = models.TextField(null=True)
    results_received = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

class TestRunQueue(models.Model):
    test_run = models.ForeignKey(TestRun)
    work_queue = models.ForeignKey(WorkQueue)
