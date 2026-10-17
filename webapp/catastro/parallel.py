"""Bounded network workers with all ledger/PDF work on the coordinator thread."""
from concurrent.futures import Future, TimeoutError
import os
from queue import Empty, Queue
import threading
import time


def worker_count(value=None):
    value = os.environ.get('CATASTRO_MAX_WORKERS', '10') if value is None else value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('Selecciona entre 1 y 10 lotes simultáneos.')
    try:
        result = int(value)
    except ValueError:
        raise ValueError('Selecciona entre 1 y 10 lotes simultáneos.') from None
    if not 1 <= result <= 10:
        raise ValueError('Selecciona entre 1 y 10 lotes simultáneos.')
    return result


class RequestGate:
    """Share request spacing and server-requested cooldown across source clients."""
    def __init__(self, interval=1, clock=time.monotonic, sleep=time.sleep):
        self.interval = max(1, interval)
        self.clock, self.sleep = clock, sleep
        self.next_request = 0
        self.lock = threading.Lock()

    def wait(self, checkpoint):
        while True:
            checkpoint()
            with self.lock:
                now = self.clock()
                delay = self.next_request - now
                if delay <= 0:
                    self.next_request = now + self.interval
                    return
            self.sleep(min(delay, .2))

    def defer(self, seconds):
        with self.lock:
            self.next_request = max(self.next_request, self.clock() + max(0, seconds))


class Coordinator:
    def __init__(self, checkpoint):
        self.owner = threading.get_ident()
        self.checkpoint = checkpoint
        self.requests = Queue()

    def call(self, function, *args, **kwargs):
        if threading.get_ident() == self.owner:
            return function(*args, **kwargs)
        self.checkpoint()
        future = Future()
        self.requests.put((future, function, args, kwargs))
        while True:
            try:
                return future.result(timeout=.2)
            except TimeoutError:
                if future.done():
                    raise
                try:
                    self.checkpoint()
                except Exception:
                    future.cancel()
                    raise

    def service(self, timeout=0):
        try:
            future, function, args, kwargs = self.requests.get(timeout=timeout)
        except Empty:
            return False
        if future.set_running_or_notify_cancel():
            try:
                future.set_result(function(*args, **kwargs))
            except Exception as error:
                future.set_exception(error)
        return True


class CoordinatorState:
    """Workers cannot access a SQLite connection, cursor or transaction."""
    METHODS = {'lot', 'uploaded_hash', 'save_upload', 'upload_bytes', 'save_lot', 'set_lot_bytes'}

    def __init__(self, state, coordinator):
        self.root = state.root
        self.state, self.coordinator = state, coordinator
        self.totals = {'processed': 0, 'uploaded': 0, 'partial': 0, 'failed': 0, 'local_saved': 0}

    def __getattr__(self, name):
        if name not in self.METHODS:
            raise AttributeError(name)
        function = getattr(self.state, name)
        def invoke(*args, **kwargs):
            def execute():
                result = function(*args, **kwargs)
                if name == 'save_lot':
                    self.totals['processed'] += 1
                    self.totals['uploaded'] += kwargs['uploaded']
                    self.totals['partial'] += kwargs['status'] == 'partial'
                    self.totals['failed'] += kwargs['status'] == 'failed'
                    self.totals['local_saved'] += kwargs['status'] != 'failed'
                return result
            return self.coordinator.call(execute)
        return invoke
