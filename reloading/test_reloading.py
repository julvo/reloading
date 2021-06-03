import unittest
import os
import subprocess as sp
import time

from reloading import reloading

SRC_FILE_NAME = "temporary_testing_file.py"

TEST_CHANGING_SOURCE_LOOP_CONTENT = """
from reloading import reloading
from time import sleep

for epoch in reloading(range(10)):
    sleep(0.2)
    print('INITIAL_FILE_CONTENTS')
"""

TEST_CHANGING_SOURCE_FN_CONTENT = """
from reloading import reloading
from time import sleep

@reloading
def reload_this_fn():
    print('INITIAL_FILE_CONTENTS')

for epoch in reloading(range(10)):
    sleep(0.2)
    reload_this_fn()
"""

TEST_KEEP_LOCAL_VARIABLES_CONTENT = """
from reloading import reloading
from time import sleep

fpath = "DON'T CHANGE ME"
for epoch in reloading(range(1)):
    assert fpath == "DON'T CHANGE ME"
"""

TEST_PERSIST_AFTER_LOOP = """
from reloading import reloading
from time import sleep

state = 'INIT'
for epoch in reloading(range(1)):
    state = 'CHANGED'

assert state == 'CHANGED'
"""

TEST_COMMENT_AFTER_LOOP_CONTENT = """
from reloading import reloading
from time import sleep

for epoch in reloading(range(10)):
    sleep(0.2)
    print('INITIAL_FILE_CONTENTS')

# a comment here should not cause an error
"""

TEST_FORMAT_STR_IN_LOOP_CONTENT = """
from reloading import reloading
from time import sleep

for epoch in reloading(range(10)):
    sleep(0.2)
    file_contents = 'FILE_CONTENTS'
    print(f'INITIAL_{file_contents}')
"""

TEST_FUNCTION_AFTER = """
from reloading import reloading
from time import sleep

@reloading
def some_func(a, b):
    sleep(0.2)
    print(a+b)

for _ in range(10):
    some_func(2,1)
"""


def run_and_update_source(init_src, updated_src=None, update_after=0.5, bin="python3"):
    """Runs init_src in a subprocess and updates source to updated_src after
    update_after seconds. Returns the standard output of the subprocess and
    whether the subprocess produced an uncaught exception.
    """
    with open(SRC_FILE_NAME, "w") as f:
        f.write(init_src)

    cmd = [bin, SRC_FILE_NAME]
    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE) as proc:
        if updated_src is not None:
            time.sleep(update_after)
            with open(SRC_FILE_NAME, "w") as f:
                f.write(updated_src)

        try:
            stdout, _ = proc.communicate(timeout=2)
            stdout = stdout.decode("utf-8")
            has_error = False
        except:
            stdout = ""
            has_error = True
            proc.terminate()

    if os.path.isfile(SRC_FILE_NAME):
        os.remove(SRC_FILE_NAME)

    return stdout, has_error


class TestReloading(unittest.TestCase):
    def test_simple_looping(self):
        iters = 0
        for _ in reloading(range(10)):
            iters += 1

    def test_changing_source_loop(self):
        for bin in ["python", "python3"]:
            stdout, _ = run_and_update_source(
                init_src=TEST_CHANGING_SOURCE_LOOP_CONTENT,
                updated_src=TEST_CHANGING_SOURCE_LOOP_CONTENT.replace("INITIAL", "CHANGED").rstrip("\n"),
                bin=bin,
            )

            self.assertTrue("INITIAL_FILE_CONTENTS" in stdout and "CHANGED_FILE_CONTENTS" in stdout)

    def test_comment_after_loop(self):
        for bin in ["python", "python3"]:
            stdout, _ = run_and_update_source(
                init_src=TEST_COMMENT_AFTER_LOOP_CONTENT,
                updated_src=TEST_COMMENT_AFTER_LOOP_CONTENT.replace("INITIAL", "CHANGED").rstrip("\n"),
                bin=bin,
            )

            self.assertTrue("INITIAL_FILE_CONTENTS" in stdout and "CHANGED_FILE_CONTENTS" in stdout)

    def test_format_str_in_loop(self):
        stdout, _ = run_and_update_source(
            init_src=TEST_FORMAT_STR_IN_LOOP_CONTENT,
            updated_src=TEST_FORMAT_STR_IN_LOOP_CONTENT.replace("INITIAL", "CHANGED").rstrip("\n"),
            bin="python3",
        )

        self.assertTrue("INITIAL_FILE_CONTENTS" in stdout and "CHANGED_FILE_CONTENTS" in stdout)

    def test_keep_local_variables(self):
        for bin in ["python", "python3"]:
            _, has_error = run_and_update_source(init_src=TEST_KEEP_LOCAL_VARIABLES_CONTENT, bin=bin)
            self.assertFalse(has_error)

    def test_persist_after_loop(self):
        for bin in ["python", "python3"]:
            _, has_error = run_and_update_source(init_src=TEST_PERSIST_AFTER_LOOP, bin=bin)
            self.assertFalse(has_error)

    def test_simple_function(self):
        @reloading
        def some_func():
            return "result"

        self.assertTrue(some_func() == "result")

    def test_reloading_function(self):
        for bin in ["python", "python3"]:
            stdout, _ = run_and_update_source(
                init_src=TEST_FUNCTION_AFTER,
                updated_src=TEST_FUNCTION_AFTER.replace("a+b", "a-b"),
                bin=bin,
            )
            self.assertTrue("3" in stdout and "1" in stdout)

    def test_changing_source_function(self):
        for bin in ["python", "python3"]:
            stdout, _ = run_and_update_source(
                init_src=TEST_CHANGING_SOURCE_FN_CONTENT,
                updated_src=TEST_CHANGING_SOURCE_FN_CONTENT.replace("INITIAL", "CHANGED").rstrip("\n"),
                bin=bin,
            )

            self.assertTrue("INITIAL_FILE_CONTENTS" in stdout and "CHANGED_FILE_CONTENTS" in stdout)


if __name__ == "__main__":
    unittest.main()
