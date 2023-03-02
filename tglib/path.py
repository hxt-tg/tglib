import os
import re
from os.path import join, exists, normpath, splitext, sep
from collections.abc import Iterable, Callable
from typing import Any, TypeVar, NewType

__all__ = ['PathIterator']

FileName = NewType('FileName', str)
DirName = NewType('DirName', str)

FilterExtensionType = TypeVar('FilterExtensionType', str, Iterable[str], Callable[[str], bool])
FilterPatternType = TypeVar('FilterPatternType', re.Pattern, Iterable[re.Pattern], Callable[[str], bool])

tmp = """
    Parameters
    ----------
    paths : str or Iterable[str]
        A path or a list of paths to be iterated. The path can be a file name or a directory path.
        If a directory is given, files in this directory will be iterated recursively according to the level.
    level : int, default=None
        Recursive level. If `None`, all subdirectories will be iterated.
    root : str, default=''
        If not null string, the root path will concatenate to the front of all the paths.
    filter_file_extension s: FilterExtensionType, default=None
        If not None, only file that matches given extensions will be yielded.
    filter_file_name : FilterPatternType, default=None
        If not None, only file whose name matches re pattern will be yielded.
    filter_dir_name : FilterPatternType, default=None
        If not None, only directory whose name matches re pattern will be yielded.
        Notice: This rule will affect directories of all files, including separate files in `paths`.
    raise_not_found : bool, default=False
        If `True`, a FileNotFoundError will be raised when a file or a directory does not exist.
    yield_dir : bool, default=False
        If `True`, directories will be yielded all alone.
    verbose : bool, default=False
        Print more info.
        """


class PathIterator:
    """
    A class used to iterate over paths.

    Parameters
    ----------
    paths : str or Iterable[str]
        A path or a list of paths to be iterated. The path can be a file name or a directory path.
        If a directory is given, files in this directory will be iterated recursively according to the level.
    level : int, default=None
        Recursive level. If `None`, all subdirectories will be iterated.
    root : str, default=''
        If not null string, the root path will concatenate to the front of all the paths.
    filter_file_extension s: FilterExtensionType, default=None
        If not None, only file that matches given extensions will be yielded.
    filter_file_name : FilterPatternType, default=None
        If not None, only file whose name matches re pattern will be yielded.
    filter_dir_name : FilterPatternType, default=None
        If not None, only directory whose name matches re pattern will be yielded.
        Notice: This rule will affect directories of all files, including separate files in `paths`.
    raise_not_found : bool, default=False
        If `True`, a FileNotFoundError will be raised when a file or a directory does not exist.
    yield_dir : bool, default=False
        If `True`, directories will be yielded all alone.
    verbose : bool, default=False
        Print more info.
    """

    SEP = sep

    def __init__(self,
                 paths: str | Iterable[str],
                 level: int = None,
                 root: str = '',
                 filter_file_extensions: FilterExtensionType = None,
                 filter_file_name: FilterPatternType = None,
                 filter_dir_name: FilterPatternType = None,
                 raise_not_found: bool = True,
                 yield_dir: bool = True,
                 verbose: bool = True):
        """TODO docstring

        :param paths:
        :param level:
        :param root:
        :param filter_file_extensions:
        :param filter_file_name:
        :param filter_dir_name:
        :param raise_not_found:
        :param yield_dir:
        :param verbose:
        """
        self.verbose = verbose

        if isinstance(paths, str):
            paths = [paths]
        self.paths = [normpath(join(root, p)) for p in paths]
        self.level = level
        self.root = normpath(root)

        self.f_file_ext: Callable = self._wrapper_filter_extension(filter_file_extensions)
        self.f_file_name: Callable = self._wrapper_filter_pattern(filter_file_name)
        self.f_dir_name: Callable = self._wrapper_filter_pattern(filter_dir_name)

        self.raise_not_found = raise_not_found
        self.yield_dir = yield_dir

        assert self.level is None or self.level > 0, 'Level should be as least 1.'

    def __iter__(self):
        """
        :return: A tuple of dir path and file name. If a dir is iterated, file name will be None.
        """
        for root in self.paths:
            root = normpath(root)
            if os.path.isdir(root):

                if self.raise_not_found and not exists(root):
                    raise FileNotFoundError(root)

                level_root = root.count(PathIterator.SEP)
                for dir_path, dirs, files in os.walk(root):
                    self._verbose_print(f'====== Current: [{dir_path}] ======')

                    # Check directory level
                    level_dir = dir_path.count(PathIterator.SEP)
                    if self.level is not None and level_dir >= level_root + self.level:
                        continue

                    # Check directory name
                    if not self.f_dir_name(dir_path):
                        continue
                    if self.yield_dir:
                        self._verbose_print(f'[D] "{dir_path}"')
                        yield dir_path, None

                    # Iterate files in the dir_path
                    for file in files:
                        if self.f_file_name(file) and self.f_file_ext(splitext(file)[1]):
                            self._verbose_print(f'[F] "{join(dir_path, file)}"')
                            yield dir_path, file
            else:  # File or link
                dir_path, file = os.path.split(root)
                if self.f_dir_name(dir_path) and self.f_file_name(file) and self.f_file_ext(splitext(file)[1]):
                    self._verbose_print(f'[F] "{join(dir_path, file)}"')
                    yield dir_path, file

    @staticmethod
    def _ext(ext: str):
        return ext.lower().lstrip('.')

    def _verbose_print(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    def _wrapper_filter_extension(self, filter_obj: FilterExtensionType):
        if isinstance(filter_obj, str):
            self._verbose_print("Filter for extension: An extension string")
            filter_obj = self._ext(filter_obj)
            flt = lambda fn_ext: self._ext(fn_ext) == filter_obj
        elif isinstance(filter_obj, Iterable):
            filter_obj = [self._ext(ext) for ext in filter_obj]
            if len(filter_obj) > 0 and all(isinstance(obj, str) for obj in filter_obj):
                self._verbose_print("Filter for extension: An iterable of extension string")
                flt = lambda fn_ext: self._ext(fn_ext) in filter_obj
            else:
                raise TypeError("Only support iterable of extension string")
        elif callable(filter_obj):
            # A function that pass in an extension string and return a bool
            self._verbose_print("Filter for extension: A function")
            flt = filter_obj
        elif filter_obj is None:
            flt = lambda fn: True
        else:
            raise TypeError('Unsupported filter type:', type(filter_obj))
        return flt

    def _wrapper_filter_pattern(self, filter_obj: FilterPatternType):
        if isinstance(filter_obj, re.Pattern):
            self._verbose_print("Filter for file/dir name: A re.Pattern")
            flt = lambda fn: bool(filter_obj.match(fn))
        elif isinstance(filter_obj, Iterable):
            filter_obj = list(filter_obj)
            if len(filter_obj) > 0 and all(isinstance(obj, re.Pattern) for obj in filter_obj):
                self._verbose_print("Filter for file/dir name: An iterable of re.Pattern")
                flt = lambda fn: any(bool(pat.match(fn)) for pat in filter_obj)
            else:
                raise TypeError("Only support iterable of re.Pattern.")
        elif callable(filter_obj):
            self._verbose_print("Filter for file/dir name: A function")
            flt = filter_obj
        elif filter_obj is None:
            flt = lambda fn: True
        else:
            raise TypeError('Unsupported filter type:', type(filter_obj))
        return flt

    def traverse(self,
                 handler_file: Callable[[DirName, FileName], Any] = None,
                 handler_dir: Callable[[DirName], Any] = None) -> None:
        """
        Traverse all files and dirs with given handler functions.
        (Notice: If yield_dir is False, `handler_dir` will have no effects.)

        :param handler_file: A handler function that accept a full file name.
        :param handler_dir: A handler function that accept a directory path.
        :return: None
        """
        for dir_name, file in self:
            if file is None:
                if handler_dir is not None:
                    handler_dir(dir_name)
            else:  # File or link
                if handler_file is not None:
                    handler_file(dir_name, file)


if __name__ == "__main__":
    def general_test():
        pi = PathIterator(
            ['test', 'test/1.txt'],
            root=join(os.path.dirname(__file__), '../_data'),
            filter_file_extensions=['pdf', 'txt'],
            # filter_dir_name=re.compile(r'.+\\test$'),
            filter_dir_name=re.compile(r'.+sub.+'),
            # verbose=False,
            yield_dir=False
        )
        # pi.traverse(lambda f: None, lambda d: None)
        pi.traverse(lambda d, f: print(f"File: {d, f}"), lambda d: print(f" Dir: {d}"))


    general_test()
