#!/usr/bin/env python

from distutils.core import setup


__version__ = '0.0.1'

readme = open("README").read()
changes = open("docs/changes.rst").read()
long_description = readme + "\n\n" + changes


setup(
    name="riakfs",
    version=__version__,
    author="Gerard Flanagan",
    author_email="contact@devopsni.com",
    description="Riak-backed virtual file system.",
    long_description=long_description,
    url="https://github.com/podados/riakfs",
    download_url="http://pypi.python.org/packages/source/r/riakfs/riakfs-%s.tar.gz" % __version__,
    py_modules=['riakfs'],
)

