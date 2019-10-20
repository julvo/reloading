import unittest
import os
import subprocess as sp
import time

from reloading import reloading

SRC_FILE_NAME = 'temporary_testing_file.py'
SRC_FILE_CONTENT = '''
from reloading import reloading
from time import sleep

for epoch in reloading(range(10)):
    sleep(0.1)
    print('INITIAL_FILE_CONTENTS')
'''

class TestReloading(unittest.TestCase):

    def test_simple_looping(self):
        iters = 0
        for _ in reloading(range(10)):
            iters += 1

    def test_changing_source(self):
        with open(SRC_FILE_NAME, 'w') as f:
            f.write(SRC_FILE_CONTENT)

        cmd = ['python', SRC_FILE_NAME]
        with sp.Popen(cmd, stdout=sp.PIPE) as proc:
            # wait for first loop iterations to run before changing source file
            time.sleep(0.2)
            with open(SRC_FILE_NAME, 'w') as f:
                f.write(SRC_FILE_CONTENT.replace('INITIAL', 'CHANGED').rstrip('\n'))

            # check if output contains results from before and after change
            stdout = proc.stdout.read().decode('utf-8')
            self.assertTrue('INITIAL_FILE_CONTENTS' in stdout and
                            'CHANGED_FILE_CONTENTS' in stdout)

    def tearDown(self):
        if os.path.isfile(SRC_FILE_NAME):
            os.remove(SRC_FILE_NAME)

if __name__ == '__main__':
    unittest.main()
