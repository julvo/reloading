import unittest
import os
import subprocess as sp
import time

from reloading import reloading

SRC_FILE_NAME = 'temporary_testing_file.py'

TEST_CHANGING_SOURCE_LOOP_CONTENT = '''
from reloading import reloading
from time import sleep

for epoch in reloading(range(10)):
    sleep(0.1)
    print('INITIAL_FILE_CONTENTS')
'''

TEST_CHANGING_SOURCE_FN_CONTENT = '''
from reloading import reloading
from time import sleep

@reloading
def reload_this_fn():
    print('INITIAL_FILE_CONTENTS')

for epoch in reloading(range(10)):
    sleep(0.1)
    reload_this_fn()
'''

TEST_KEEP_LOCAL_VARIABLES_CONTENT = '''
from reloading import reloading
from time import sleep

fpath = "DON'T CHANGE ME"
for epoch in reloading(range(1)):
    assert fpath == "DON'T CHANGE ME"
'''

TEST_PERSIST_AFTER_LOOP = '''
from reloading import reloading
from time import sleep

state = 'INIT'
for epoch in reloading(range(1)):
    state = 'CHANGED'

assert state == 'CHANGED'
'''

TEST_COMMENT_AFTER_LOOP_CONTENT = '''
from reloading import reloading
from time import sleep

for epoch in reloading(range(10)):
    sleep(0.1)
    print('INITIAL_FILE_CONTENTS')

# a comment here should not cause an error
'''

TEST_FORMAT_STR_IN_LOOP_CONTENT = '''
from reloading import reloading
from time import sleep

for epoch in reloading(range(10)):
    sleep(0.1)
    file_contents = 'FILE_CONTENTS'
    print(f'INITIAL_{file_contents}')
'''


def run_and_update_source(init_src, updated_src=None, update_after=0.5):
    '''Runs init_src in a subprocess and updates source to updated_src after
    update_after seconds. Returns the standard output of the subprocess and
    whether the subprocess produced an uncaught exception.
    '''
    with open(SRC_FILE_NAME, 'w') as f:
        f.write(init_src)

    cmd = ['python3', SRC_FILE_NAME]
    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE) as proc:
        if updated_src != None:
            time.sleep(update_after)
            with open(SRC_FILE_NAME, 'w') as f:
                f.write(updated_src)

        try:
            stdout, _ = proc.communicate(timeout=2)
            stdout = stdout.decode('utf-8')
            has_error = False
        except:
            stdout = ''
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
        stdout, _ = run_and_update_source(
          init_src=TEST_CHANGING_SOURCE_LOOP_CONTENT,
          updated_src=TEST_CHANGING_SOURCE_LOOP_CONTENT.replace('INITIAL', 'CHANGED').rstrip('\n'))

        self.assertTrue('INITIAL_FILE_CONTENTS' in stdout and
                        'CHANGED_FILE_CONTENTS' in stdout)

    def test_comment_after_loop(self):
        stdout, _ = run_and_update_source(
          init_src=TEST_COMMENT_AFTER_LOOP_CONTENT,
          updated_src=TEST_COMMENT_AFTER_LOOP_CONTENT.replace('INITIAL', 'CHANGED').rstrip('\n'))

        self.assertTrue('INITIAL_FILE_CONTENTS' in stdout and
                        'CHANGED_FILE_CONTENTS' in stdout)

    def test_format_str_in_loop(self):
        stdout, _ = run_and_update_source(
          init_src=TEST_FORMAT_STR_IN_LOOP_CONTENT,
          updated_src=TEST_FORMAT_STR_IN_LOOP_CONTENT.replace('INITIAL', 'CHANGED').rstrip('\n'))

        self.assertTrue('INITIAL_FILE_CONTENTS' in stdout and
                        'CHANGED_FILE_CONTENTS' in stdout)

    def test_keep_local_variables(self):
        _, has_error = run_and_update_source(init_src=TEST_KEEP_LOCAL_VARIABLES_CONTENT)
        self.assertFalse(has_error)

    def test_persist_after_loop(self):
        _, has_error = run_and_update_source(init_src=TEST_PERSIST_AFTER_LOOP)
        self.assertFalse(has_error)

    def test_simple_function(self):
        @reloading
        def some_func():
            return 'result'
        
        self.assertTrue(some_func() == 'result')

    def test_changing_source_function(self):
        stdout, _ = run_and_update_source(
          init_src=TEST_CHANGING_SOURCE_FN_CONTENT,
          updated_src=TEST_CHANGING_SOURCE_FN_CONTENT.replace('INITIAL', 'CHANGED').rstrip('\n'))

        self.assertTrue('INITIAL_FILE_CONTENTS' in stdout and
                        'CHANGED_FILE_CONTENTS' in stdout)


if __name__ == '__main__':
    unittest.main()
