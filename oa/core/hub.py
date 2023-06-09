# Need something to act as 'core'

import logging
_logger = logging.getLogger(__name__)

import os
import threading

class Hub:
    def __init__(self, config=None):
        self.config = config

        self.ready = threading.Event()
        self.finished = threading.Event()

        self.thread_pool = []
        self.parts = {}


    def start(self):
        self.ready.clear()
        self.finished.clear()
        self._load_modules()
        self._link_modules()
        self._start_modules()
        self.ready.set()


    def _load_modules(self):
        """ Setup all parts. """

        for module_repo in self.config.get('module_path', []):
            _logger.info("Loading Modules <- {}".format(module_repo))

            for module_name in os.listdir(module_repo):
                if module_name in self.config.get('modules'):
                    try:
                        m = load_module(os.path.join(module_repo, module_name))
                        m.name = module_name
                        self.parts[module_name] = m
                    except Exception as ex:
                        _logger.error("Error loading {}: {}".format(module_name, ex))


    def _link_modules(self):
        for _in, _out in self.config.get('module_map', []):
            self.parts[_in].outputs += [self.parts[_out]]


    def _start_modules(self):
        # Setup input threads.
        b = threading.Barrier(len(self.parts)+1)

        for module_name in self.parts:
            m = self.parts[module_name]
            thr = threading.Thread(target=thread_loop, name=module_name, args=(self, m, b))
            self.thread_pool.append(thr)

        # Start all threads.
        [thr.start() for thr in self.thread_pool]
        b.wait()


def command_registry(kws):
    def command(cmd):
        def _command(fn):
            if type(cmd) == str:
                kws[cmd.upper()] = fn
            elif type(cmd) == list:
                for kw in cmd:
                    kws[kw.upper()] = fn
            return fn
        return _command
    return command


def load_module(path):
    """Load an OA module from path."""
    import os
    import logging
    import importlib

    # An OA module is a folder with an __oa__.py file
    if not all([
        os.path.isdir(path),
        os.path.exists(os.path.join(path, '__oa__.py')),
    ]): raise Exception("Invalid module: {}".format(path))

    # Import package
    module_name = os.path.basename(path)
    _logger.info('{} <- {}'.format(module_name, path))
    M = importlib.import_module("oa.modules"+'.{}'.format(module_name))

    # XXX: differently hacky (these don't seem quite right or the same)
    M.__dict__.setdefault('outputs', [])

    return M


def thread_loop(hub, part, b):
    """ Setup part inputs to the message wire. """
    _logger.debug('Starting')

    if hasattr(part, 'init'):
        part.init()

    b.wait()

    hub.ready.wait()

    while not hub.finished.is_set():
        try:
            for msg in part.__call__(hub):
                for listener in part.outputs:
                    _logger.debug('{} -> {}'.format(part.name, listener.name))
                    listener.input_queue.put(msg)
        except Exception as ex:
            _logger.error("Error processing queue: {}".format(ex))

    _logger.debug('Stopped')
