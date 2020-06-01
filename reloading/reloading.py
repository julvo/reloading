import time
import re
import inspect
import sys
import ast
import traceback
import types
from itertools import chain


def reloading(fn_or_seq):
    '''Wraps a loop iterator or decorates a function to reload source code.

    A function that when wrapped around the outermost iterator in a for loop,
    causes the loop body to reload from source before every iteration while
    keeping the state.
    When used as a function decorator, the function is reloaded from source 
    before each execution.

    Args:
        fn_or_seq (function | iterable): A function or loop iterator which should
            be reloaded from source before each execution or iteration,
            respectively
    '''
    if isinstance(fn_or_seq, types.FunctionType):
        return _reloading_function(fn_or_seq)
    return _reloading_loop(fn_or_seq)


def find_loop(tree):
    for child in ast.walk(tree):
        if not isinstance(child, ast.For):
            continue
        if not isinstance(child.iter, ast.Call):
            continue
        if child.iter.func.id == 'reloading':
            return child


def locate_loop_body(module, loop):
    ends = set([ node.lineno 
                    for node in ast.walk(module) 
                    if hasattr(node, 'lineno') and node.lineno > loop.lineno ])

    starts = set()

    def visit(node):
        if hasattr(node, 'lineno') and node.lineno > loop.lineno:
            starts.add(node.lineno)
            if node.lineno in ends:
                ends.remove(node.lineno)
        for child in ast.iter_child_nodes(node):
            visit(child)

    for stmt in loop.body:
        visit(stmt)

    if len(ends) == 0: 
        return min(starts), -1

    return min(starts), min(ends)


def unique_name(used):
    return max(used, key=len) + "0"


def _reloading_loop(seq):
    frame = inspect.currentframe()

    caller_globals = frame.f_back.f_back.f_globals
    caller_locals = frame.f_back.f_back.f_locals
    unique = unique_name(chain(caller_locals.keys(), caller_globals.keys()))
    for j in seq:
        fpath = inspect.stack()[2][1]
        with open(fpath, 'r') as f:
            src = f.read() + '\n'

        # find the iteration variables in the caller module's source
        match = re.search('\s*for (.+?) in reloading', src)
        if match is None:
            break 
        itervars = match.group(1)

        # find the loop body in the caller module's source
        tree = ast.parse(src)
        loop = find_loop(tree)
        start, end = locate_loop_body(tree, loop)
        lines  = src.split('\n')
        if end < 0:
            end = len(lines)
        body_lines = lines[start-1:end-1] # -1 as line numbers are 1-indexed

        # remove indent from lines in loop body, only if a line
        # starts with this indentation as comments might not
        indent = re.search('([ \t]*)\S', body_lines[0])
        body = '\n'.join([ line[len(indent.group(1)):] 
            for line in body_lines 
            if line.startswith(indent.group(1))])

        caller_locals[unique] = j
        exec(itervars + ' = ' + unique, caller_globals, caller_locals)

        try:
            # run main loop body
            exec(body, caller_globals, caller_locals)
        except Exception:
            exc = traceback.format_exc()
            exc = exc.replace('File "<string>"', 'File "{}"'.format(fpath))
            sys.stderr.write(exc + '\n')
            print('Edit {} and press return to continue with the next iteration'.format(fpath))
            sys.stdin.readline()

    return []


def find_function_in_source(fn_name, src):
    '''Finds line number of start and end of a function with a 
    given name within the given source code.
    '''
    tree = ast.parse(src)

    # find the parent of the function definition so that we can find out
    # where the function definition ends by using the starting line
    # number of the subsequent child after the function definition
    for parent in ast.walk(tree):
        fn_end = len(src.split('\n'))

        for child in reversed(list(ast.iter_child_nodes(parent))):
            if not isinstance(child, ast.FunctionDef)\
               or child.name != fn_name\
               or not hasattr(child, 'decorator_list')\
               or len([ 
                   dec 
                   for dec in child.decorator_list 
                   if dec.id == 'reloading' ]) < 1:

                if hasattr(child, 'lineno'):
                    fn_end = child.lineno - 1
                continue

            # if we arrived here, child is the function definition
            fn_start = min([d.lineno for d in child.decorator_list])
            return fn_start, fn_end, child.col_offset

    return -1, -1, 0


def _reloading_function(fn):
    frame, fpath = inspect.stack()[2][:2]
    caller_locals = frame.f_locals
    caller_globals = frame.f_globals

    # if we are redefining the function, we need to load the file path
    # from the function's dictionary as it would be `<string>` otherwise
    # which happens when defining functions using `exec`
    if fn.__name__ in caller_locals:
        fpath = caller_locals[fn.__name__].__dict__['__fpath__']

    def wrapped(*args, **kwargs):
        with open(fpath, 'r') as f:
            src = f.read()

        start, end, indent = find_function_in_source(fn.__name__, src)
        lines = src.split('\n')
        fn_src = '\n'.join([ l[indent:] for l in lines[start-1:end] ])

        while True:
            try:
                exec(fn_src, caller_globals, caller_locals)
                break
            except Exception:
                exc = traceback.format_exc()
                exc = exc.replace('File "<string>"', 'File "{}"'.format(fpath))
                sys.stderr.write(exc + '\n')
                print('Edit {} and press return to try again'.format(fpath))
                sys.stdin.readline()


        # the newly defined function will also be decorated 
        # with `reloading` and, hence, we call the inner function without
        # triggering another reload (and another one...)
        inner = caller_locals[fn.__name__].__dict__['__inner__']
        return inner(*args, **kwargs)

    # save the inner function to be able to call it without 
    # triggering infinitely recursive reloading
    wrapped.__dict__['__inner__'] = fn
    # save the file path for later, as the original file path gets
    # lost by reloading and redefining the function using `exec`
    wrapped.__dict__['__fpath__'] = fpath
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__

    return wrapped
