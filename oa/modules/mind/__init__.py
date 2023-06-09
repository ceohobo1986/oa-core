# mind.py - Core mind operations.
import logging
_logger = logging.getLogger(__name__)

import importlib
import logging
import os

from oa.util.legacy import Core as LegacyCore

from oa.util.abilities.core import info, call_function, get
from oa.util.abilities.system import read_file, sys_exec


""" Core mind functions. """

import queue
input_queue = queue.Queue()

_history = []

def load_mind(path):
    """ Load a mind by its `name`. """
    mind = LegacyCore()
    mind.module = path
    mind.name = os.path.splitext(os.path.basename(mind.module))[0]
    # XXX: repo-centric path
    mind.cache_dir = os.path.join(os.path.dirname(__file__), 'cache', mind.name)

    # Make directories.
    if not os.path.exists(mind.cache_dir):
        os.makedirs(mind.cache_dir)

    M = importlib.import_module("oa.modules.mind.minds"+".{}".format(mind.name))
    mind.__dict__.update(M.__dict__)
    
    # Add command keywords without spaces.
    mind.kws = {}
    for key, value in M.kws.items():
        for synonym in key.strip().split(','):
            mind.kws[synonym] = value

    return mind

def set_mind(ctx, name, history=True):
    """ Activate new mind. """
    _logger.info('Opening Mind: {}'.format(name))
    if history:
        _history.append(name)
        
    ctx.mind = ctx.minds[name]
    return ctx.mind

def switch_back(ctx):
    """ Switch back to the previous mind. (from `switch_hist`). """
    set_mind(ctx, _history.pop(), history=False)

def load_minds(ctx):
    """ Load and check dictionaries for all minds. Handles updating language models using the online `lmtool`.
    """
    _logger.info('Loading minds...')
    # XXX: repo-centric path
    mind_path = os.path.join(os.path.dirname(__file__), 'minds')
    for mind in os.listdir(mind_path):
        if mind.lower().endswith('.py'):
            _logger.info("<- {}".format(mind))
            m = load_mind(os.path.join(mind_path, mind))
            ctx.minds[m.name] = m
    _logger.info('Minds loaded!')

def __call__(ctx):

    default_mind = 'boot'
    load_minds(ctx)
    set_mind(ctx, default_mind)

    _logger.debug('"{}" is now listening. Say "Boot Mind!" to see if it can hear you.'.format(default_mind))


    while not ctx.finished.is_set():
        text = input_queue.get()
        _logger.debug('Input: {}'.format(text))
        # XXX: not a great way to mind
        mind = ctx.mind
        if (text is None) or (text.strip() == ''):
            # Nothing to do.
            continue
        t = text.upper()

        # Check for a matching command.
        fn = mind.kws.get(t, None)

        if fn is not None:
            # There are two types of commands, stubs and command line text.
            # For stubs, call `perform()`.
            if hasattr(fn, "__call__"):
                # call_function(fn)
                fn()
                ctx.last_command = t
            # For strings, call `sys_exec()`.
            elif isinstance(fn, str):
                sys_exec(fn)
                ctx.last_command = t
            else:
                # Any unknown command raises an exception.
                raise Exception("Unable to process: {}".format(text))
        yield text

