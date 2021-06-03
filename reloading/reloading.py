import inspect
import sys
import ast
import traceback
import types
from itertools import chain
from functools import partial, update_wrapper


# have to make our own partial in case someone wants to use reloading as a iterator without any arguments
# they would get a partial back because a call without a iterator argument is assumed to be a decorator.
# getting a "TypeError: 'functools.partial' object is not iterable"
# which is not really descriptive.
# hence we overwrite the iter to make sure that the error makes sense.
class no_iter_partial(partial):
    def __iter__(self):
        raise TypeError("Nothing to iterate over. Please pass an iterable to reloading.")


def reloading(fn_or_seq=None, every=1, forever=None):
    """Wraps a loop iterator or decorates a function to reload the source code 
    before every loop iteration or function invocation.

    When wrapped around the outermost iterator in a `for` loop, e.g. 
    `for i in reloading(range(10))`, causes the loop body to reload from source 
    before every iteration while keeping the state.
    When used as a function decorator, the decorated function is reloaded from 
    source before each execution.

    Pass the integer keyword argument `every` to reload the source code
    only every n-th iteration/invocation.

    Args:
        fn_or_seq (function | iterable): A function or loop iterator which should
            be reloaded from source before each invocation or iteration,
            respectively
        every (int, Optional): After how many iterations/invocations to reload
        forever (bool, Optional): Pass `forever=true` instead of an iterator to
            create an endless loop

    """
    if fn_or_seq:
        if isinstance(fn_or_seq, types.FunctionType):
            return _reloading_function(fn_or_seq, every=every)
        return _reloading_loop(fn_or_seq, every=every)
    if forever:
        return _reloading_loop(iter(int, 1), every=every)

    # return this function with the keyword arguments partialed in,
    # so that the return value can be used as a decorator
    decorator = update_wrapper(no_iter_partial(reloading, every=every), reloading)
    return decorator


def unique_name(used):
    # get the longest element of the used names and append a "0"
    return max(used, key=len) + "0"


def format_itervars(ast_node):
    """Formats a an `ast_node` of loop iteration variables as string, e.g. 'a, b'"""

    # handle the case that there only is a single loop var
    if isinstance(ast_node, ast.Name):  
        return ast_node.id

    names = []
    for child in ast_node.elts:
        if isinstance(child, ast.Name):
            names.append(child.id)
        elif isinstance(child, ast.Tuple):
            # if its another tuple, like "a, (b, c)", recurse
            names.append("({})".format(format_itervars(child)))  

    return ", ".join(names)


def load_file(path):
    src = ""
    # while loop here since while saving, the file may sometimes be empty.
    while (src == ""):  
        with open(path, "r") as f:
            src = f.read()
    return src + "\n"


def parse_file_until_successful(path):
    source = load_file(path)
    while True:
        try:
            tree = ast.parse(source)
            return tree
        except SyntaxError:
            handle_exception(path)
            source = load_file(path)


def isolate_loop_body_and_get_itervars(tree, lineno):
    """Modifies tree inplace as unclear how to create ast.Module.
    Returns itervars"""
    for node in ast.walk(tree):
        if (getattr(node, "lineno", None) == lineno and node.iter.func.id == "reloading"):
            tree.body = node.body
            return node.target


def get_loop_code(loop_frame_info):
    fpath = loop_frame_info[1]
    tree = parse_file_until_successful(fpath)
    itervars = isolate_loop_body_and_get_itervars(tree, lineno=loop_frame_info[2])
    return compile(tree, filename="", mode="exec"), format_itervars(itervars)


def handle_exception(fpath):
    exc = traceback.format_exc()
    exc = exc.replace('File "<string>"', 'File "{}"'.format(fpath))
    sys.stderr.write(exc + "\n")
    print("Edit {} and press return to continue".format(fpath))
    sys.stdin.readline()


def _reloading_loop(seq, every=1):
    loop_frame_info = inspect.stack()[2]
    fpath = loop_frame_info[1]

    caller_globals = loop_frame_info[0].f_globals
    caller_locals = loop_frame_info[0].f_locals

    # create a unique name in the caller namespace that we can safely write 
    # the values of the iteration variables into
    unique = unique_name(chain(caller_locals.keys(), caller_globals.keys()))

    for i, itervar_values in enumerate(seq):
        if i % every == 0:
            compiled_body, itervars = get_loop_code(loop_frame_info)

        caller_locals[unique] = itervar_values
        exec(itervars + " = " + unique, caller_globals, caller_locals)
        try:
            # run main loop body
            exec(compiled_body, caller_globals, caller_locals)
        except Exception:
            handle_exception(fpath)

    return []


def get_decorator_name(dec_node):
    if hasattr(dec_node, "id"):
        return dec_node.id
    return dec_node.func.id


def strip_reloading_decorator(func):
    """Remove the reloading decorator in-place"""
    func.decorator_list = [
        dec for dec in func.decorator_list if get_decorator_name(dec) != "reloading"
    ]


def isolate_function_def(funcname, tree):
    """Strip everything but the function definition from the ast in-place.
    Also strips the reloading decorator from the function definition"""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == funcname
            and "reloading" in [
                get_decorator_name(dec)
                for dec in node.decorator_list
            ]
        ):
            strip_reloading_decorator(node)
            tree.body = [ node ]  
            return True
    return False


def get_function_def_code(fpath, fn):
    tree = parse_file_until_successful(fpath)
    found = isolate_function_def(fn.__name__, tree)
    if not found:
        return None
    compiled = compile(tree, filename="", mode="exec")
    return compiled


def get_reloaded_function(caller_globals, caller_locals, fpath, fn):
    code = get_function_def_code(fpath, fn)
    if code is None:
        return None
    # need to copy locals, otherwise the exec will overwrite the decorated with the undecorated new version
    # this became a need after removing the reloading decorator from the newly defined version
    caller_locals_copy = caller_locals.copy()
    exec(code, caller_globals, caller_locals_copy)
    func = caller_locals_copy[fn.__name__]
    return func


def _reloading_function(fn, every=1):
    stack = inspect.stack()
    frame, fpath = stack[2][:2]
    caller_locals = frame.f_locals
    caller_globals = frame.f_globals

    # crutch to use dict as python2 doesn't support nonlocal
    state = {
        "func": None,
        "reloads": 0,
    }

    def wrapped(*args, **kwargs):
        if state["reloads"] % every == 0:
            state["func"] = get_reloaded_function(caller_globals, caller_locals, fpath, fn) or state["func"]
        state["reloads"] += 1
        while True:
            try:
                result = state["func"](*args, **kwargs)
                return result
            except Exception:
                handle_exception(fpath)
                state["func"] = get_reloaded_function(caller_globals, caller_locals, fpath, fn) or state["func"]

    caller_locals[fn.__name__] = wrapped
    return wrapped
