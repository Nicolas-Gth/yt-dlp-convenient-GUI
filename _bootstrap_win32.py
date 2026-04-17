"""
Win32 ctypes bootstrap GUI — splash screen and PySide6 install dialog.

Used only on Windows so that pythonw.exe can show feedback without a console.
"""
import os
import sys
import ctypes
import ctypes.wintypes
import threading

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_comctl32 = ctypes.windll.comctl32
_gdi32 = ctypes.windll.gdi32

# ---------------------------------------------------------------------------
# Return / argument types (64-bit safety)
# ---------------------------------------------------------------------------
_kernel32.GetModuleHandleW.restype = ctypes.c_void_p
_user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p,
]
_user32.CreateWindowExW.restype = ctypes.wintypes.HWND
_user32.LoadImageW.restype = ctypes.c_void_p
_user32.LoadCursorW.restype = ctypes.c_void_p
_gdi32.CreateFontW.restype = ctypes.c_void_p
_user32.DefWindowProcW.restype = ctypes.wintypes.LPARAM
_user32.DefWindowProcW.argtypes = [
    ctypes.wintypes.HWND, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
_user32.SendMessageW.restype = ctypes.wintypes.LPARAM
_user32.SendMessageW.argtypes = [
    ctypes.wintypes.HWND, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
_user32.PostMessageW.argtypes = [
    ctypes.wintypes.HWND, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
_user32.DestroyWindow.argtypes = [ctypes.wintypes.HWND]
_user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_user32.UpdateWindow.argtypes = [ctypes.wintypes.HWND]

# ---------------------------------------------------------------------------
# WNDPROC callback
# ---------------------------------------------------------------------------
_WM_APP_DONE = 0x8001

_WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.LPARAM,
    ctypes.wintypes.HWND, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
)


def _wnd_proc(hwnd, msg, wp, lp):
    if msg == 0x0010:          # WM_CLOSE — block user closing
        return 0
    if msg == _WM_APP_DONE:    # install thread finished
        _user32.PostQuitMessage(0)
        return 0
    return _user32.DefWindowProcW(hwnd, msg, wp, lp)


_wnd_proc_cb = _WNDPROC(_wnd_proc)

# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint), ("style", ctypes.c_uint),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p), ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
        ("hIconSm", ctypes.c_void_p),
    ]


class _INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("dwICC", ctypes.wintypes.DWORD),
    ]


_wndclass_atom = 0
_SCRIPT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__)))


def _ensure_wndclass():
    """Register the bootstrap window class (once)."""
    global _wndclass_atom
    if _wndclass_atom:
        return
    icc = _INITCOMMONCONTROLSEX()
    icc.dwSize = ctypes.sizeof(icc)
    icc.dwICC = 0x20  # ICC_PROGRESS_CLASS
    _comctl32.InitCommonControlsEx(ctypes.byref(icc))

    hinst = _kernel32.GetModuleHandleW(None)
    wc = _WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(wc)
    wc.lpfnWndProc = _wnd_proc_cb
    wc.hInstance = hinst
    wc.hCursor = _user32.LoadCursorW(None, 32512)    # IDC_ARROW
    wc.hbrBackground = ctypes.c_void_p(16)            # COLOR_BTNFACE + 1
    wc.lpszClassName = "YtDlpBootstrap"
    _wndclass_atom = _user32.RegisterClassExW(ctypes.byref(wc))


def create_window(title, client_w, client_h):
    """Create a centred, topmost, non-resizable bootstrap window."""
    _ensure_wndclass()
    style = 0x00C80000       # WS_CAPTION | WS_SYSMENU
    ex = 0x00000008          # WS_EX_TOPMOST
    rect = ctypes.wintypes.RECT(0, 0, client_w, client_h)
    _user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex)
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    sx = _user32.GetSystemMetrics(0)  # SM_CXSCREEN
    sy = _user32.GetSystemMetrics(1)  # SM_CYSCREEN
    hinst = _kernel32.GetModuleHandleW(None)
    hwnd = _user32.CreateWindowExW(
        ex, "YtDlpBootstrap", title, style,
        (sx - w) // 2, (sy - h) // 2, w, h,
        None, None, hinst, None,
    )
    ico_path = os.path.join(_SCRIPT_DIR, "assets", "icon.ico")
    if os.path.isfile(ico_path):
        hi = _user32.LoadImageW(None, ico_path, 1, 0, 0, 0x10)
        if hi:
            _user32.SendMessageW(hwnd, 0x0080, 0, hi)   # WM_SETICON SMALL
            _user32.SendMessageW(hwnd, 0x0080, 1, hi)   # WM_SETICON BIG
    return hwnd


def add_label(parent, text, x, y, w, h, pt=10):
    """Add a centred static text label with Segoe UI font."""
    hinst = _kernel32.GetModuleHandleW(None)
    lbl = _user32.CreateWindowExW(
        0, "Static", text,
        0x50000001,  # WS_VISIBLE | WS_CHILD | SS_CENTER
        x, y, w, h, parent, None, hinst, None,
    )
    hfont = _gdi32.CreateFontW(
        -int(pt * 96 / 72), 0, 0, 0, 400,
        0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI",
    )
    if hfont:
        _user32.SendMessageW(lbl, 0x0030, hfont, 1)  # WM_SETFONT
    return lbl


def add_marquee_bar(parent, x, y, w, h):
    """Add an indeterminate marquee progress bar."""
    hinst = _kernel32.GetModuleHandleW(None)
    bar = _user32.CreateWindowExW(
        0, "msctls_progress32", None,
        0x50000008,  # WS_VISIBLE | WS_CHILD | PBS_MARQUEE
        x, y, w, h, parent, None, hinst, None,
    )
    _user32.SendMessageW(bar, 0x040A, 1, 20)  # PBM_SETMARQUEE on, 20ms
    return bar


def show_window(hwnd):
    """Make the window visible and process pending messages."""
    _user32.ShowWindow(hwnd, 5)   # SW_SHOW
    _user32.UpdateWindow(hwnd)
    msg = ctypes.wintypes.MSG()
    while _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        _user32.TranslateMessage(ctypes.byref(msg))
        _user32.DispatchMessageW(ctypes.byref(msg))


def run_message_loop():
    """Block on the Win32 message loop until PostQuitMessage is called."""
    msg = ctypes.wintypes.MSG()
    while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        _user32.TranslateMessage(ctypes.byref(msg))
        _user32.DispatchMessageW(ctypes.byref(msg))


def destroy_window(hwnd):
    """Destroy a window."""
    _user32.DestroyWindow(hwnd)


def post_done(hwnd):
    """Post the WM_APP_DONE message to the given window."""
    _user32.PostMessageW(hwnd, _WM_APP_DONE, 0, 0)


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------

_splash_hwnd = None


def install_pyside6_with_gui(pip_install_fn, msg):
    """Show a progress dialog while *pip_install_fn* runs."""
    hwnd = create_window("yt-dlp Convenient GUI", 350, 80)
    if hwnd:
        add_label(hwnd, msg, 15, 12, 320, 22, pt=10)
        add_marquee_bar(hwnd, 15, 40, 320, 22)
        show_window(hwnd)

        def do_install():
            pip_install_fn()
            post_done(hwnd)

        threading.Thread(target=do_install, daemon=True).start()
        run_message_loop()
        destroy_window(hwnd)
    else:
        pip_install_fn()


def show_splash(loading_text):
    """Show a splash window while the app loads."""
    global _splash_hwnd
    try:
        hwnd = create_window("yt-dlp Convenient GUI", 300, 65)
        if not hwnd:
            return
        add_marquee_bar(hwnd, 10, 10, 280, 18)
        add_label(hwnd, loading_text, 10, 33, 280, 20, pt=9)
        show_window(hwnd)
        _splash_hwnd = hwnd
    except Exception:
        pass


def close_splash():
    """Close the splash window if it's open."""
    global _splash_hwnd
    if _splash_hwnd is not None:
        try:
            destroy_window(_splash_hwnd)
        except Exception:
            pass
        _splash_hwnd = None
