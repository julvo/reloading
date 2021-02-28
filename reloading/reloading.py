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


def get_loop_code(loop_frame_info):
    fpath = loop_frame_info[1]
    with open(fpath, "r") as f:
        src = f.read() + "\n"

    # find the loop body in the caller module's source
    tree = ast.parse(src)
    loop = find_loop(tree, lineno=loop_frame_info.lineno)
    start, end = locate_loop_body(tree, loop)

    lines = src.split("\n")
    if end < 0:
        end = len(lines)
    body_lines = lines[start - 1 : end - 1]  # -1 as line numbers are 1-indexed

    # find the iteration variables from the loop target ast
    itervars = tuple_ast_as_name(loop.target)

    # remove indent from lines in loop body, only if a line
    # starts with this indentation as comments might not
    indent = re.search("([ \t]*)\S", body_lines[0])
    body = "\n".join(
        [
            line[len(indent.group(1)) :]
            for line in body_lines
            if line.startswith(indent.group(1))
        ]
    )
    return compile(body, filename="", mode="exec"), itervars


def _reloading_loop(seq, reload_after=1):
    loop_frame_info = inspect.stack()[2]

    caller_globals = loop_frame_info.frame.f_globals
    caller_locals = loop_frame_info.frame.f_locals
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
            exc = traceback.format_exc()
            exc = exc.replace('File "<string>"', 'File "{}"'.format(fpath))
            sys.stderr.write(exc + "\n")
            print(
                "Edit {} and press return to continue with the next iteration".format(
                    fpath
                )
            )
            sys.stdin.readline()

    return []


def ast_get_decorator_name(dec):
    if hasattr(dec, "id"):
        return dec.id
    else:
        return dec.func.id


def find_function_in_source(fn_name, src):
    """Finds line number of start and end of a function with a
    given name within the given source code.
    """
    tree = ast.parse(src)

    # find the parent of the function definition so that we can find out
    # where the function definition ends by using the starting line
    # number of the subsequent child after the function definition
    for parent in ast.walk(tree):
        fn_end = len(src.split("\n"))

        for child in reversed(list(ast.iter_child_nodes(parent))):
            if (
                not isinstance(child, ast.FunctionDef)
                or child.name != fn_name
                or not hasattr(child, "decorator_list")
                or len(
                    [
                        dec
                        for dec in child.decorator_list
                        if ast_get_decorator_name(dec) == "reloading"
                    ]
                )
                < 1
            ):
                # TODO: Awfull getattr workaround, needs fixing. in fact,
                # this whole function could need some cleaning up.
                if hasattr(child, "lineno"):
                    fn_end = child.lineno - 1
                continue

            # if we arrived here, child is the function definition
            fn_start = min([d.lineno for d in child.decorator_list])
            return fn_start, fn_end, child.col_offset

    return -1, -1, 0


def ast_filter_decorator(func_module):
    """Filter out the reloading decorator, inplace."""
    func_module.body[0].decorator_list = [
        dec
        for dec in func_module.body[0].decorator_list
        if ast_get_decorator_name(dec) != "reloading"
    ]


def get_function_def_code(fpath, fn):
    src = ""
    while src == "": # while loop here since while saving, the file may sometimes be empty.
        with open(fpath, "r") as f:
            src = f.read()

    start, end, indent = find_function_in_source(fn.__name__, src)
    lines = src.split("\n")
    fn_src = "\n".join([l[indent:] for l in lines[start - 1 : end]])
    mod = ast.parse(fn_src)
    ast_filter_decorator(mod)
    # parse the function source as ast, to be able to easily filter out the reloading decorator.
    # this avoids all the wierd things the previous version had to do, to prevent infinite reload recursion.
    compiled = compile(mod, filename="", mode="exec")
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
            print("reloaded")
        counter += 1
        a = the_func(*args, **kwargs)
        return a
    caller_locals[fn.__name__] = wrapped
    return wrapped