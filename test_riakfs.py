
import unittest

from fs.tests import FSTestCases, ThreadingTestCases
from fs.path import *

from riakfs import RiakFS

class TestRiakFS(unittest.TestCase,FSTestCases,ThreadingTestCases):

    #  Disable the tests by default
    __test__ = True

    bucket = "test-riakfs"

    def setUp(self):
        self.fs = RiakFS(self.bucket)

    def tearDown(self):
        self.fs.close()

    def test_unicode(self):
        pass

    def test_concurrent_copydir(self):
        #  makedir() on S3FS is currently not atomic
        pass

    def test_makedir_winner(self):
        #  makedir() on S3FS is currently not atomic
        pass

    def test_multiple_overwrite(self):
        # S3's eventual-consistency seems to be breaking this test
        pass


