import time
import re
import inspect
import sys
import ast
import traceback


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


def reloading(seq):
    frame = inspect.currentframe()

    # copy caller's globals into this module's namespace
    caller_globals = frame.f_back.f_globals
    for k, v in caller_globals.items():
        globals()[k] = v

    # copy caller's locals into this module's namespace
    caller_locals = frame.f_back.f_locals
    for k, v in caller_locals.items():
        exec('{} = caller_locals["{}"]'.format(k, k))

    for j in seq:
        fpath = inspect.stack()[1][1]
        with open(fpath, 'r') as f:
            src = f.read()

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

        exec(itervars + ' = j')

        try:
            # run main loop body
            exec(body)
        except Exception:
            exc = traceback.format_exc()
            exc = exc.replace('File "<string>"', f'File "{fpath}"')
            sys.stderr.write(exc + '\n')
            input('Edit the file and press return to continue with the next iteration')

    # copy locals back into the caller's locals
    for k, v in locals().items():
        frame.f_back.f_locals[k] = v

    return []
