import time
import re
import inspect
import sys
import ast
import traceback
import types
from itertools import chain
from functools import partial, update_wrapper, wraps


def reloading(*fn_or_seq, **kwargs):
    """Wraps a loop iterator or decorates a function to reload source code.

    A function that when wrapped around the outermost iterator in a for loop,
    causes the loop body to reload from source before every iteration while
    keeping the state.
    When used as a function decorator, the function is reloaded from source
    before each execution.

    If the reload_after keyword-only argument is passed, the function/loop
    body wont be reloaded from source, until that many iterations/calls
    have passed. This was added to allow for increased performance
    in fast-running loops.

    Args:
        fn_or_seq (function | iterable): A function or loop iterator which should
            be reloaded from source before each execution or iteration,
            respectively
        reload_after (int, Optional): After how many iterations/calls to reload.
    """
    if len(fn_or_seq) > 0:
        # check if a loop or function was passed, for decorator keyword argument support
        fn_or_seq = fn_or_seq[0]
        if isinstance(fn_or_seq, types.FunctionType):
            return _reloading_function(fn_or_seq, **kwargs)
        return _reloading_loop(fn_or_seq, **kwargs)
    else:
        return update_wrapper(partial(reloading, **kwargs), reloading)
        # return this function with the keyword arguments partialed in,
        # so that the return value can be used as a decorator


def find_loop(tree, lineno=0):
    for child in ast.walk(tree):
        if getattr(child, "lineno", 0) < lineno:
            continue
        if not isinstance(child, ast.For):
            continue
        if not isinstance(child.iter, ast.Call):
            continue
        if child.iter.func.id == "reloading":
            return child


def locate_loop_body(module, loop):
    ends = set(
        [
            node.lineno
            for node in ast.walk(module)
            if hasattr(node, "lineno") and node.lineno > loop.lineno
        ]
    )

    starts = set()

    def visit(node):
        if hasattr(node, "lineno") and node.lineno > loop.lineno:
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


def tuple_ast_as_name(tup):
    if isinstance(
        tup, ast.Name
    ):  # handle the case that there only is a single loop var
        return tup.id
    names = []
    for child in tup.elts:
        if isinstance(child, ast.Name):
            names.append(child.id)
        elif isinstance(child, ast.Tuple):
            names.append(
                f"({tuple_ast_as_name(child)})"
            )  # if its another tuple, like "a, (b, c)", recurse.
    return ", ".join(names)


def load_file(path):
    src = ""
    while (
        src == ""
    ):  # while loop here since while saving, the file may sometimes be empty.
        with open(path, "r") as f:
            src = f.read()
    return src + "\n"


def load_ast_parse(path):
    source = load_file(path)
    while True:
        try:
            tree = ast.parse(source)
            break
        except SyntaxError:
            handle_exception(path)
            source = load_file(path)
    return tree


def isolate_loop_ast(tree, lineno=None):
    """strip ast from anything but the loop body, also returning the loop vars"""
    for child in ast.walk(tree):
        # i hope this is enough checks
        if getattr(child, "lineno", None) == lineno and child.iter.func.id == "reloading":
            itervars = tuple_ast_as_name(child.target)
            # replace the original body with the loop body
            tree.body = child.body
            return itervars

def get_loop_code(loop_frame_info):
    fpath = loop_frame_info[1]
    # find the loop body in the caller module's source
    tree = load_ast_parse(fpath)
    # same working principle as the functio nversion, strip the ast of everything but the loop body.
    itervars = isolate_loop_ast(tree, lineno=loop_frame_info.lineno)
    return compile(tree, filename="", mode="exec"), itervars


def handle_exception(fpath):
    exc = traceback.format_exc()
    exc = exc.replace('File "<string>"', 'File "{}"'.format(fpath))
    sys.stderr.write(exc + "\n")
    print("Edit {} and press return to continue with the next iteration".format(fpath))
    sys.stdin.readline()


def _reloading_loop(seq, reload_after=1):
    loop_frame_info = inspect.stack()[2]
    fpath = loop_frame_info[1]

    caller_globals = loop_frame_info.frame.f_globals
    caller_locals = loop_frame_info.frame.f_locals
    
    # this creates a uniqe name by adding "0" to the end of the key.
    # this ensures its always uniqe and unlikey to be used by the user
    unique = unique_name(chain(caller_locals.keys(), caller_globals.keys()))
    
    compiled_body, itervars = get_loop_code(loop_frame_info)  # inital call
    counter = 0
    for j in seq:
        if counter % reload_after == 0:
            compiled_body, itervars = get_loop_code(loop_frame_info)
        counter += 1
        caller_locals[unique] = j
        exec(itervars + " = " + unique, caller_globals, caller_locals)
        try:
            # run main loop body
            exec(compiled_body, caller_globals, caller_locals)
        except Exception:
            handle_exception(fpath)

    return []


def ast_get_decorator_name(dec):
    if hasattr(dec, "id"):
        return dec.id
    return dec.func.id


def ast_filter_decorator(func):
    """Filter out the reloading decorator, inplace."""
    func.decorator_list = [
        dec
        for dec in func.decorator_list
        if ast_get_decorator_name(dec) != "reloading"
    ]


def isolate_func_ast(funcname, tree):
    """ This removes everything but the function definition from the ast """
    for child in ast.walk(tree):
        if (
            isinstance(child, ast.FunctionDef)
            and child.name == funcname
            and len(
                [
                    dec
                    for dec in child.decorator_list
                    if ast_get_decorator_name(dec) == "reloading"
                ]
            )
            == 1
        ):
            ast_filter_decorator(child)
            tree.body = [child] # reassign body, i would create a new ast if i knew how to create ast.Module objects

def get_function_def_code(fpath, fn):
    tree = load_ast_parse(fpath)
    # these both work inplace and modify the ast
    isolate_func_ast(fn.__name__, tree)
    compiled = compile(tree, filename="", mode="exec")
    return compiled


def get_reloaded_function(caller_globals, caller_locals, fpath, fn):
    code = get_function_def_code(fpath, fn)
    # need to copy locals, otherwise the exec will overwrite the decorated with the undecorated new version
    # this became a need after removing the reloading decorator from the newly defined version
    caller_locals = caller_locals.copy()
    exec(code, caller_globals, caller_locals)
    func = caller_locals[fn.__name__]
    # get the newly defined function from the caller_locals copy
    return func


def _reloading_function(fn, reload_after=1):
    frame, fpath = inspect.stack()[2][:2]
    caller_locals = frame.f_locals
    caller_globals = frame.f_globals
    counter = 0
    the_func = get_reloaded_function(caller_globals, caller_locals, fpath, fn)

    def wrapped(*args, **kwargs):
        nonlocal counter
        nonlocal the_func
        if counter % reload_after == 0:
            the_func = get_reloaded_function(caller_globals, caller_locals, fpath, fn)
        counter += 1
        while True:
            try:
                a = the_func(*args, **kwargs)
                break
            except Exception:
                handle_exception(fpath)
                the_func = get_reloaded_function(
                    caller_globals, caller_locals, fpath, fn
                )
        return a

    caller_locals[fn.__name__] = wrapped
    return wrapped