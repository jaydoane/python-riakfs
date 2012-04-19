
import time
from datetime import datetime
import threading

from fs import _thread_synchronize_default
from fs.path import iteratepath, pathsplit, normpath
from fs.base import synchronize
from fs.memoryfs import MemoryFS, MemoryFile, DirEntry
from fs.filelike import StringIO
from fs.errors import (
    ResourceNotFoundError, ResourceInvalidError, PathError,
    DestinationExistsError, ParentDirectoryMissingError,
)

import riak

TRANSPORTS = {
    'HTTP': riak.RiakHttpTransport,
    'PBC': riak.RiakPbcTransport,
}

def RiakBucket(name, host, port, transport):
    """
    Utility for creating a `riak.RiakBucket` instance from string parameters.
    """
    client = riak.RiakClient(
        host=host, port=port, transport_class=TRANSPORTS[transport]
    )
    return client.bucket(name)

class RiakFSObject(DirEntry):

    @classmethod
    def from_dict(cls, bucket, data):
        def obj_from_dict(d):
            type = d.pop('type')
            name = d.pop('name')
            prefix = d.pop('prefix', None)
            contents = d.pop('contents', {})
            obj = cls(bucket, type, name, prefix)
            obj.xattrs = d['xattrs']
            obj.timestamps = d['timestamps']
            for k, v in contents.items():
                obj.contents[k] = obj_from_dict(v)
            return obj
        return obj_from_dict(data)

    def to_dict(self):
        def serialize(obj):
            d = {}
            for k,v in obj.__dict__.iteritems():
                if k == 'bucket' or k == 'contents' or k == 'lock' or k.startswith('_'):
                    continue
                d[k] = v
            if obj.contents:
                d['contents'] = dict(
                    (k, serialize(v)) for k, v in obj.contents.items()
                )
            return d
        return serialize(self)

    def _get_ct(self):
        return datetime.fromtimestamp(time.mktime(self.timestamps['ctime']))

    def _get_mt(self):
        return datetime.fromtimestamp(time.mktime(self.timestamps['mtime']))

    def _get_at(self):
        return datetime.fromtimestamp(time.mktime(self.timestamps['atime']))

    def _set_ct(self, val):
        self.timestamps['ctime'] = list(val.timetuple())

    def _set_mt(self, val):
        self.timestamps['mtime'] = list(val.timetuple())

    def _set_at(self, val):
        self.timestamps['atime'] = list(val.timetuple())

    created_time = property(_get_ct, _set_ct)
    modified_time = property(_get_mt, _set_mt)
    accessed_time = property(_get_at, _set_at)

    def _get_file(self):
        if self.type == 'file' and self._mem_file is None:
            bytes = self.bucket.get_binary(self.path).get_data()
            self._mem_file = StringIO(bytes)
        return self._mem_file

    def _set_file(self, stream):
        self._mem_file = stream

    mem_file = property(_get_file, _set_file)

    def __init__(self, bucket, type, name, prefix=None, contents=None):
        assert type in ("dir", "file"), "Type must be dir or file!"
        self.bucket = bucket
        self.type = type
        self.name = name.rstrip('/')
        prefix = prefix or '/'
        prefix = '/' + prefix.strip('/') + '/'
        self.path = prefix + name
        if type == 'dir':
            self.path += '/'
            if contents is None:
                contents = {}
        self.open_files = []
        self.contents = contents        

        now = list(datetime.now().timetuple())
        self.timestamps = {'ctime': now, 'mtime': now, 'atime': now}
        
        self.xattrs = {}
        
        self.key = None
        self.lock = None
        self._mem_file = None
        if self.type == 'file':
            self.lock = threading.RLock()
            
    def _make_dir_entry(self, type, name, contents=None):
        child = self.__class__(
            self.bucket, type, name, prefix=self.path, contents=contents
        )
        self.contents[name] = child
        return child

    def __getstate__(self):
        state = self.__dict__.copy()        
        del state['lock']
        bucket = state.pop('bucket')
        state['bucket'] = bucket.get_name()
        state['host'] = bucket._client._host
        state['port'] = bucket._client._port
        state['transport'] = \
            bucket._client._transport.__class__.__name__[4:-9].upper()
        if self._mem_file is not None:
            state['_mem_file'] = self.data
        return state
            
    def __setstate__(self, state):
        state['bucket'] = RiakBucket(
            state.pop('bucket'), state.pop('host'),
            state.pop('port'), state.pop('transport')
        )
        self.__dict__.update(state)
        if self.type == 'file':
            self.lock = threading.RLock()
        else:
            self.lock = None
        if self._mem_file is not None:
            data = self._mem_file
            self._mem_file = StringIO()
            self._mem_file.write(data) 

class RiakFS(MemoryFS):

    ROOTKEY = '__VFS__'

    _meta = {'thread_safe' : True,            
             'network' : True,
             'virtual': False,
             'read_only' : False,
             'unicode_paths' : False,
             'case_insensitive_paths' : False,
             'atomic.move' : False,
             'atomic.copy' : False,
             'atomic.makedir' : True,
             'atomic.rename' : True,
             'atomic.setcontents' : False,              
              }

    def get_journal(self):
        obj = self.bucket.get(self.ROOTKEY)
        data = obj.get_data()
        if data:
            return RiakFSObject.from_dict(self.bucket, data)
        else:
            return RiakFSObject(self.bucket, 'dir', self.ROOTKEY)

    def set_journal(self):
        obj = self.bucket.new(self.ROOTKEY, self.root.to_dict())
        obj.store()

    def __init__(self, bucket, host='127.0.0.1', port=8091, transport="HTTP"):
        super(MemoryFS, self).__init__(thread_synchronize=_thread_synchronize_default)
        self.host = host
        self.port = port
        self.transport = transport.upper()
        self._bucket = bucket
        self.file_factory = MemoryFile
        self.root = self.get_journal()

    def _get_bucket(self):
        if isinstance(self._bucket, basestring):
            self._bucket = RiakBucket(
                self._bucket, self.host, self.port, self.transport
            )
        return self._bucket

    bucket = property(_get_bucket)

    def __str__(self):
        return "<MemoryFS>"

    __repr__ = __str__

    def __unicode__(self):
        return unicode(self.__str__())

    def __getstate__(self):
        state = super(RiakFS, self).__getstate__()
        try:
            state['_bucket'] = self._bucket.get_name()
        except AttributeError:
            pass
        return state

    def close(self):
        self.set_journal()

    @synchronize
    def _get_dir_entry(self, dirpath):
        dirpath = normpath(dirpath)
        current_dir = self.root
        for path_component in iteratepath(dirpath):
            if current_dir.contents is None:
                return None
            dir_entry = current_dir.contents.get(path_component, None)
            if dir_entry is None:
                return None
            current_dir = dir_entry
        return current_dir
    
    @synchronize
    def _on_close_memory_file(self, open_file, path):
        dir_entry = self._get_dir_entry(path)
        if dir_entry is not None:
            data = open_file.mem_file.getvalue()
            if data:
                entity = self.bucket.new_binary(dir_entry.path, data)
                entity.store()
            dir_entry.open_files.remove(open_file)        
            del dir_entry._mem_file
            dir_entry._mem_file = None
                
    @synchronize
    def makedir(self, dirname, recursive=False, allow_recreate=False):
        if not dirname and not allow_recreate:
            raise PathError(dirname)
        fullpath = normpath(dirname)
        if fullpath in ('', '/'):
            if allow_recreate:
                return
            raise DestinationExistsError(dirname)
        dirpath, dirname = pathsplit(dirname)

        if recursive:
            parent_dir = self._get_dir_entry(dirpath)
            if parent_dir is not None:
                if parent_dir.isfile():
                    raise ResourceInvalidError(dirname, msg="Can not create a directory, because path references a file: %(path)s")
                else:
                    if not allow_recreate:
                        if dirname in parent_dir.contents:
                            raise DestinationExistsError(dirname, msg="Can not create a directory that already exists (try allow_recreate=True): %(path)s")

            current_dir = self.root
            for path_component in iteratepath(dirpath)[:-1]:
                dir_item = current_dir.contents.get(path_component, None)
                if dir_item is None:
                    break
                if not dir_item.isdir():
                    raise ResourceInvalidError(dirname, msg="Can not create a directory, because path references a file: %(path)s")
                current_dir = dir_item

            current_dir = self.root
            for path_component in iteratepath(dirpath):
                dir_item = current_dir.contents.get(path_component, None)
                if dir_item is None:
                    new_dir = current_dir._make_dir_entry("dir", path_component)
                    #current_dir.contents[path_component] = new_dir
                    current_dir = new_dir
                else:
                    current_dir = dir_item

            parent_dir = current_dir

        else:
            parent_dir = self._get_dir_entry(dirpath)
            if parent_dir is None:
                raise ParentDirectoryMissingError(dirname, msg="Could not make dir, as parent dir does not exist: %(path)s")

        dir_item = parent_dir.contents.get(dirname, None)
        if dir_item is not None:
            if dir_item.isdir():
                if not allow_recreate:
                    raise DestinationExistsError(dirname)
            else:
                raise ResourceInvalidError(dirname, msg="Can not create a directory, because path references a file: %(path)s")

        if dir_item is None:
            #parent_dir.contents[dirname] = self._make_dir_entry("dir", dirname)
            parent_dir._make_dir_entry("dir", dirname)
        

    @synchronize
    def open(self, path, mode="r", **kwargs):
        path = normpath(path)
        filepath, filename = pathsplit(path)
        parent_dir_entry = self._get_dir_entry(filepath)

        if parent_dir_entry is None or not parent_dir_entry.isdir():
            raise ResourceNotFoundError(path)
        
        if 'r' in mode or 'a' in mode:
            if filename not in parent_dir_entry.contents:
                raise ResourceNotFoundError(path)

            file_dir_entry = parent_dir_entry.contents[filename]
            if file_dir_entry.isdir():
                raise ResourceInvalidError(path)
            
            file_dir_entry.accessed_time = datetime.now()

            mem_file = self.file_factory(path, self, file_dir_entry.mem_file, mode, file_dir_entry.lock)
            file_dir_entry.open_files.append(mem_file)
            return mem_file

        elif 'w' in mode:
            if filename not in parent_dir_entry.contents:
                file_dir_entry = parent_dir_entry._make_dir_entry("file", filename)
                #parent_dir_entry.contents[filename] = file_dir_entry
            else:
                file_dir_entry = parent_dir_entry.contents[filename]

            file_dir_entry.accessed_time = datetime.now()            
            
            mem_file = self.file_factory(path, self, file_dir_entry.mem_file, mode, file_dir_entry.lock)
            file_dir_entry.open_files.append(mem_file)
            return mem_file

        if parent_dir_entry is None:
            raise ResourceNotFoundError(path)

