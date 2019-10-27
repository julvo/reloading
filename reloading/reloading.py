import time
import re
import inspect
import sys
import ast
import traceback
from itertools import chain


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
        if hasattr(node, 'lineno'):
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


def reloading(seq):
    frame = inspect.currentframe()

    caller_globals = frame.f_back.f_globals
    caller_locals = frame.f_back.f_locals
    unique = unique_name(chain(caller_locals.keys(), caller_globals.keys()))
    for j in seq:
        fpath = inspect.stack()[1][1]
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
        s, end = locate_loop_body(tree, loop)
        lines  = src.split('\n')
        if end < 0:
            end = len(lines)
        body_lines = lines[s-1:end-1] # -1 as line numbers are 1-indexed

        # remove indent from loop body
        indent = re.search('([ \t]*)\S', body_lines[0])
        body = '\n'.join([ line[len(indent.group(1)):] for line in body_lines ])

        caller_locals[unique] = j
        exec(itervars + ' = ' + unique, caller_globals, caller_locals)

        try:
            # run main loop body
            exec(body, caller_globals, caller_locals)
        except Exception:
            exc = traceback.format_exc()
            exc = exc.replace('File "<string>"', 'File "{}"'.format(fpath))
            sys.stderr.write(exc + '\n')
            print('Edit the file and press return to continue with the next iteration')
            sys.stdin.readline()

    return []
