"""Tk patches: hidden windows, recorded message boxes, and calls on the Tk thread."""

import os
import queue
import threading
import tkinter
import tkinter.messagebox
import traceback

from dryrun import clock, trace

SHOW = os.environ.get("DRYRUN_SHOW_GUI") == "1"
_root = None
_REAL_TK_INIT = tkinter.Tk.__init__
_REAL_MAINLOOP = tkinter.Misc.mainloop


def _tk_init(self, *args, **kwargs):
    global _root
    _REAL_TK_INIT(self, *args, **kwargs)
    if _root is None:
        _root = self
    if not SHOW:
        self.withdraw()
    self.report_callback_exception = _report_callback_exception


def _report_callback_exception(exc, val, tb):
    trace.record("exception", where="tk_callback", error=repr(val),
                 traceback="".join(traceback.format_exception(exc, val, tb))[-4000:])


def _msg(kind):
    def f(title=None, message=None, **kw):
        trace.record("messagebox", box=kind, title=title, message=message)
        return True if kind.startswith("ask") else "ok"
    return f


_on_mainloop = None


def _mainloop(self, n=0):
    global _on_mainloop
    cb, _on_mainloop = _on_mainloop, None
    if cb is not None:
        cb()
    return _REAL_MAINLOOP(self, n)


def install(on_mainloop):
    global _on_mainloop
    _on_mainloop = on_mainloop
    tkinter.Tk.__init__ = _tk_init
    tkinter.Misc.mainloop = _mainloop
    for kind in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askquestion",
                 "askretrycancel", "askyesnocancel"):
        setattr(tkinter.messagebox, kind, _msg(kind))


def root():
    return _root


def call(fn, *args, timeout=600.0, **kwargs):
    """Run fn on the Tk main thread (like a button click) and wait for it."""
    done = clock.REAL_EVENT()
    box = {}

    def wrapper():
        try:
            box["value"] = fn(*args, **kwargs)
        except Exception as e:  # recorded, like Tk would print it
            box["error"] = e
            trace.record("exception", where=f"gui call {getattr(fn, '__name__', fn)}", error=repr(e),
                         traceback=traceback.format_exc()[-4000:])
        finally:
            done.set()

    _root.after(0, wrapper)
    if not done.wait(timeout):
        raise TimeoutError(f"GUI call {fn} did not return")
    return box.get("value")


def all_text_widgets():
    """Contents of every Text/ScrolledText widget in every Tk window."""
    out = {}

    def walk(w, path):
        for child in w.winfo_children():
            p = f"{path}/{child.winfo_class()}:{child.winfo_name()}"
            if child.winfo_class() == "Text":
                try:
                    out[p] = child.get("1.0", "end")
                except Exception:
                    pass
            walk(child, p)

    walk(_root, "root")
    return out
