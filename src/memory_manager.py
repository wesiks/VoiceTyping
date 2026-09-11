import os
import sys
import gc

def trim_process_memory():
    """Forces garbage collection and releases physical RAM pages back to the OS."""
    try:
        gc.collect()
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.EmptyWorkingSet(handle)
    except Exception:
        pass

def get_process_memory_mb() -> float:
    """Returns the current process Working Set memory in megabytes."""
    if sys.platform != "win32":
        return 0.0
    try:
        import ctypes
        from ctypes import wintypes
        class PMC(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)
            ]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        h = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, os.getpid())
        if h:
            ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), ctypes.sizeof(PMC))
            ctypes.windll.kernel32.CloseHandle(h)
            return pmc.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0
