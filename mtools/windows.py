"""Windows shell calls with typed arguments, never a shell command string."""
import ctypes
from ctypes import wintypes


def reveal_file(path):
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    ole = ctypes.OleDLL("ole32")
    shell.SHParseDisplayName.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD, ctypes.c_void_p]
    shell.SHParseDisplayName.restype = ctypes.c_long
    shell.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD]
    shell.SHOpenFolderAndSelectItems.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    pidl = ctypes.c_void_p()
    hr = ole.CoInitializeEx(None, 2)
    initialized = hr in (0, 1)
    try:
        if shell.SHParseDisplayName(str(path), None, ctypes.byref(pidl), 0, None) < 0:
            raise OSError("Windows could not locate the file")
        if shell.SHOpenFolderAndSelectItems(pidl, 0, None, 0) < 0:
            raise OSError("Windows could not reveal the file")
    finally:
        if pidl:
            ole.CoTaskMemFree(pidl)
        if initialized:
            ole.CoUninitialize()
