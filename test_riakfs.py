
import unittest

from fs.tests import FSTestCases, ThreadingTestCases
from fs.path import *

from riakfs import RiakFS

class TestRiakFS(unittest.TestCase,FSTestCases,ThreadingTestCases):

    __test__ = True

    bucket = "test-riakfs"

    def setUp(self):
        self.fs = RiakFS(self.bucket)
        #for key in self.fs.bucket.get_keys():
        #    self.fs.bucket.get(key).delete()

    def tearDown(self):
        self.fs.close()

    def test_unicode(self):
        #Unicode paths are not supported
        pass

