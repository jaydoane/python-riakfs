
Create a RiakFS object::

    >>> from riakfs import RiakFS
    >>> fs = RiakFS('test-bucket')

Delete anything previously saved::

    >>> fs.reset()

There's a delay here while Riak does its thing, wait 3 seconds to be safe::

    >>> import time
    >>> time.sleep(3)
    >>> bucket = fs.bucket
    >>> bucket.get_keys()
    []

Create a directory::

    >>> fs.tree(terminal_colors=False)
    >>> fs.makedir('a')
    >>> fs.tree(terminal_colors=False)
    `-- a
    >>> fs.makedir('a/b')
    >>> fs.tree(terminal_colors=False)
    `-- a
        `-- b

Directories aren't saved as objects, so the only key present is the special
"journal" key - __VFS__. The journal has been autosaved as a result of the
``makedir`` call::

    >>> time.sleep(3)
    >>> bucket.get_keys()
    [u'__VFS__']

Create a file::

    >>> fs.setcontents('a/b/test1.txt', 'testingtestingtesting')
    >>> fs.tree(terminal_colors=False)
    `-- a
        `-- b
            `-- test1.txt

Files autosave on close::

    >>> time.sleep(3)
    >>> sorted(bucket.get_keys())
    [u'__VFS__', u'__VFS__/a/b/test1.txt']

Retrieve the file directly from Riak::

    >>> obj = bucket.get_binary('__VFS__/a/b/test1.txt')
    >>> print(obj.get_data())
    testingtestingtesting



