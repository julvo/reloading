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
                "({})".format(tuple_ast_as_name(child))
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
    """Strip ast from anything but the loop body, also returning the loop vars."""
    for child in ast.walk(tree):
        # i hope this is enough checks
        if (
            getattr(child, "lineno", None) == lineno
            and child.iter.func.id == "reloading"
        ):
            itervars = tuple_ast_as_name(child.target)
            # replace the original body with the loop body
            tree.body = child.body
            return itervars


def get_loop_code(loop_frame_info):
    fpath = loop_frame_info[1]
    # find the loop body in the caller module's source
    tree = load_ast_parse(fpath)
    # same working principle as the functio nversion, strip the ast of everything but the loop body.
    itervars = isolate_loop_ast(tree, lineno=loop_frame_info[2])
    return compile(tree, filename="", mode="exec"), itervars


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


def ast_get_decorator_name(dec):
    if hasattr(dec, "id"):
        return dec.id
    return dec.func.id


def ast_filter_decorator(func):
    """Filter out the reloading decorator, inplace."""
    func.decorator_list = [
        dec for dec in func.decorator_list if ast_get_decorator_name(dec) != "reloading"
    ]


def isolate_func_ast(funcname, tree):
    """Remove everything but the function definition from the ast."""
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
            tree.body = [
                child
            ]  # reassign body, i would create a new ast if i knew how to create ast.Module objects


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


def _reloading_function(fn, every=1):
    stack = inspect.stack()
    frame, fpath = stack[2][:2]
    caller_locals = frame.f_locals
    caller_globals = frame.f_globals

    # crutch to use dict as python2 doesn't support nonlocal
    state = {
        "func": get_reloaded_function(caller_globals, caller_locals, fpath, fn),
        "reloads": 1,
    }

    def wrapped(*args, **kwargs):
        if state["reloads"] % every == 0:
            state["func"] = get_reloaded_function(caller_globals, caller_locals, fpath, fn)
        state["reloads"] += 1
        while True:
            try:
                result = state["func"](*args, **kwargs)
                break
            except Exception:
                handle_exception(fpath)
                state["func"] = get_reloaded_function(
                    caller_globals, caller_locals, fpath, fn
                )
        return result

    caller_locals[fn.__name__] = wrapped
    return wrapped