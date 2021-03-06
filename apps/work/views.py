from datetime import datetime, timedelta
import logging

from django.db import transaction
from django.shortcuts import render_to_response, get_object_or_404
from django.template import loader, RequestContext

import jingo

from common.stdlib import json
from common.decorators import json_view
from work.models import Worker, WorkQueue, TestRun


log = logging.getLogger('jstestnet')


def collect_garbage():
    # Reap unresponsive workers, engines, and related work queue:
    Worker.objects.filter(
            last_heartbeat__lt=datetime.now()-timedelta(seconds=30)).delete()


@json_view
@transaction.commit_on_success()
def query(request):
    try:
        worker = Worker.objects.get(pk=request.POST.get('worker_id', 0))
    except (ValueError, Worker.DoesNotExist):
        return {
            'work_queue_id': -1,
            'cmd': 'restart',
            'description': 'Unknown worker ID',
            'args': []
        }
    worker.last_heartbeat = datetime.now()
    worker.parse_user_agent(request.POST['user_agent'])
    worker.save()
    collect_garbage()
    # Look for work, FIFO:
    queue = (WorkQueue.objects
                      .filter(worker=worker, work_received=False)
                      .order_by('created'))
    if not queue.count():
        return {'desc': 'No commands from server.'}
    q = queue[0]
    q.work_received = True
    q.save()
    args = json.loads(q.cmd_args)
    if len(args):
        # Always patch in the work_queue_id because
        # this is awkward to generate when the arg packet is
        # generated.
        args[0]['work_queue_id'] = q.id
    return {
        'work_queue_id': q.id,
        'cmd': q.cmd,
        'desc': q.description,
        'args': args
    }


@json_view
@transaction.commit_on_success()
def submit_results(request):
    q = get_object_or_404(WorkQueue,
                          pk=request.POST.get('work_queue_id', 0))
    results = json.loads(request.POST['results'])
    if results.get('test_run_error'):
        tests = results.get('tests', [])
        tests.append({
            'result': False,
            'module': '__jstestnet__',
            'test': 'test_run_error',
            'message': results['test_run_error_msg']
        })
        results['tests'] = tests
    if 'tests' not in results:
        raise ValueError('Results JSON is missing key tests (list)')
    for i, test in enumerate(results['tests']):
        if 'result' not in test:
            raise ValueError(
                'results.tests[%s] JSON is missing key result '
                '(True or False)' % i)
        for k in ('module', 'test', 'message'):
            if k not in test:
                test[k] = '<%r was empty>' % k
    q.finished = True
    q.results = json.dumps(results)
    q.save()
    return {
        'desc': 'Test result received'
    }


def work(request):
    collect_garbage()
    worker = Worker()
    ip = request.META.get('REMOTE_ADDR')
    if ip:
        log.info('Worker started at %s' % ip)
        ip = ip[0:200]
        worker.ip_address = ip
    worker.save()
    return jingo.render(request, 'work/work.html', {'worker_id': worker.id})
