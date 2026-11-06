#!/usr/bin/env python3
"""History viewer for the Tandem duoplasmatron logs. NOT LIVE, never touches hardware.

Run it next to s1s2_main.py:

    python3 history_viewer.py [--db PATH]

Without --db a file dialog opens in the log folder. The S1 or S2 GUI is chosen
from the run table. Two windows open: the lab GUI, filled with logged values, and
the timeline. Closing either one quits the viewer. Nothing in the lab is affected.

Lab window
    The time strip on top moves the cursor. The lab GUI scrolls inside the window;
    "Fit to screen" reflows its columns. It cannot be scaled: the lab layout uses fixed
    pixel positions. Press ? in either window for all controls.

Timeline, mouse and keys
    Scroll / two fingers    zoom time around the pointer
    Shift + scroll          pan time (also two fingers sideways)
    Ctrl or Cmd + scroll    zoom Y of the plot under the pointer
    Click                   put the cursor there
    Drag                    pan time; near the cursor line, drag the cursor
    Right-drag, Shift+drag  box zoom
    Drag the time axis      zoom time only
    Drag a y-axis           up/down pans Y, left/right zooms Y
    Double-click a y-axis   back to auto Y
    Left / Right            one logged cycle back / forward
    Shift + Left / Right    one minute back / forward
    Home / Backspace        whole selected range / previous view
    Hover / click a marker  read a note or event (orange = note, grey = event)

Time fields are LOCAL time, "YYYY-MM-DD HH:MM". The DB stores UTC. During the
autumn clock change the repeated hour resolves to its first occurrence.

What you see
    - Windows up to 1 hour are read straight from the DB. Longer windows use a
      per-minute min/max overview, built once per DB file and kept in
      ~/.cache/duo_history/ (progress bar, Cancel). Short dips stay visible, because
      every plotted point keeps the min and max of what it covers.
    - Gaps are gaps. Nothing is interpolated. Disabled items, missing values and the
      -1 failure values of pressure and gas pos are not plotted.
    - Ammeter I includes CHEAT_OFFSET, as the live GUI shows it. The log holds the
      value before the offset. The current offset from ammeter.py is used.
    - Grey or a dash in the GUI means disabled or not logged at that moment.
    - The GUI cannot show what was never logged: interlock, HV off, ARC START, DAC
      FAIL and 'No connection' text, the rs/cf counters, magnet polarity, the
      Regulate settings. A NULL status does not prove a reading was good: during
      a communication failure the logger stores the last values unchanged.
    - The lab chart shows +-10 minutes around the cursor, from the same run, with the
      cursor as a red line. Like the live chart it shows values as logged. It cannot
      draw gaps, so cycles with a missing value are left out of it: trust the timeline.

Safety
    Before any lab module is imported, socket connect/bind, serial.Serial and
    subprocess are replaced by guards that raise "blocked in history viewer" and
    print the attempt. The lab code is then patched from the outside so that it never
    gets that far. A closed DB is opened with immutable=1, which creates no files. A
    DB with a non-empty -wal is being written, so it is opened with mode=ro, which
    uses the existing -shm; prefer a .backup copy of a live file. The only file this
    program writes is its own overview cache.
"""

# ===== 0. Environment, before anything from the lab is imported =====
import os
import sys

os.environ["DUO_LOG_DISABLE"] = "1"   # the logger must never start
sys.dont_write_bytecode = True        # no __pycache__ in the lab folder

import argparse
import array
import bisect
import contextlib
import datetime
import importlib
import io
import json
import math
import queue
import re
import socket
import sqlite3
import subprocess
import threading
import time
import types
import urllib.parse
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_DIR = "/home/s1s2/Documents/duoplasmatron_logs"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "duo_history")

RAW_MAX_S = 3600           # longest window read straight from the DB
GAP_S = 15.0               # no cycle for this long means a gap
CHART_SPAN_MIN = 10.0      # the lab chart shows this many minutes each side of the cursor
SETTLE_MS = 150            # cursor idle time before the lab GUI repaints
PLAY_LAB_S = 0.5           # lab GUI repaint interval while playing
PLAY_TICK_S = 0.1          # cursor step interval while playing
HISTORY_MAX = 50
POLL_MS = 30               # how often the Tk thread collects worker results
RAW_CHUNK = 2000           # cycles per query, so a live WAL is never pinned for long
OVERVIEW_CHUNK = 3000
NAN = float("nan")

# Plain colours: one ink for data; orange and grey only ever mean note and event.
INK = "#1f4e9c"
BAND = "#b9cbe8"
GRID = "#e4e6ea"
AXIS = "#6b7280"
TEXT = "#1f2937"
NOTE = "#c2570c"
EVENT = "#9aa1ab"
CURSOR = "#b00020"
GREY = "#9aa1ab"
NO_DATA = "#cccccc"

LAB_MAX_W = 1400
PLOT_LEFT, PLOT_RIGHT = 150, 96    # timeline margins: labels and y-axes, values and toggles
STRIP_H = 46
STATE_SHIFT, STATE_CONTROL, STATE_COMMAND = 0x1, 0x4, 0x8   # event.state; Cmd on a Mac

HELP_TEXT = """Cursor (shared by both windows)
  Click a plot, drag the red line, or use the slider
  Left / Right          one cycle
  Shift + Left / Right  one minute
  Play, speed x1 x10 x60

Timeline navigation
  Scroll, two fingers up/down      zoom time at the pointer
  Shift + scroll, fingers sideways pan time
  Ctrl or Cmd + scroll on a plot   zoom Y of that plot
  Drag empty plot area             pan time
  Right-drag or Shift + drag       box zoom
  Drag the time axis               zoom time only
  Drag a y-axis                    up/down pan Y, left/right zoom Y
  Double-click a y-axis            reset Y
  'auto' / 'fixed', 'log' / 'lin'  per-plot toggles
  Home                             whole selected range
  Backspace                        previous view
  Top strip                        drag the box or its edges, click to jump
  10 min, 1 h, 6 h, 1 day          window around the cursor

Lab window
  Scroll to move around, Fit to screen to reflow"""

# (item, signal, kind) shown when a DB is opened
DEFAULT_SIGNALS = {
    "S2": [("Ammeter", "I", "readout"), ("intensities", "intensity", "readout"),
           ("intensities", "fc_index", "readout"),
           ("Solid filament", "I", "readout"), ("S2_Arc", "I", "readout"),
           ("S2_Arc", "U", "readout"), ("Einzel lens", "V", "control"),
           ("Einzel lens", "U", "readout"), ("Neutral trap", "V", "control"),
           ("Neutral trap", "U", "readout"), ("Magnet", "I", "readout")],
    "S1": [("Ammeter", "I", "readout"), ("Filament", "I", "readout"),
           ("S1_Arc", "I", "readout"), ("S1_Arc", "U", "readout"),
           ("Einzel lens", "V", "control"), ("Einzel lens", "U", "readout"),
           ("Solenoid", "I", "readout"), ("pressure", "S1", "readout")],
}
LOG_BY_DEFAULT = ("pressure", "Pirani")


# ===== 1. Hardware guards =====
BLOCKED = []        # every refused attempt, for the summary printed on exit


def report_blocked(what, detail=""):
    BLOCKED.append((what, detail))
    print("blocked in history viewer:", what, detail,
          file=sys.__stderr__, flush=True)


def guard(what):
    def refuse(*args, **_kwargs):
        report_blocked(what, repr(args[1:3]))
        raise OSError("blocked in history viewer: " + what)
    return refuse


def install_guards():
    for name in ("connect", "connect_ex", "bind", "listen", "sendto"):
        setattr(socket.socket, name, guard("socket." + name))
    socket.create_connection = guard("socket.create_connection")
    # common.getDBValue reaches the control system through ssh, not a socket
    subprocess.Popen = guard("subprocess.Popen")
    os.system = guard("os.system")
    os.popen = guard("os.popen")
    # common.py imports serial; the real pyserial is never loaded
    fake = types.ModuleType("serial")
    fake.Serial = guard("serial.Serial")
    fake.SerialException = OSError
    sys.modules["serial"] = fake


# ===== 2. Lab code, patched from the outside =====
class FakeLink:
    """Stands in for every socket and serial link of the lab code."""
    connected = False
    building = True    # KOven.__init__ asks 'pid' once; that is the only expected call

    def __init__(self, *_args, **_kwargs):
        pass

    def _refuse(self, msg):
        if not (FakeLink.building and msg == "pid"):
            report_blocked("link message", repr(msg))

    def send_message(self, msg, *_args, **_kwargs):
        self._refuse(msg)
        return ""

    def send_message_array(self, msg, *_args, **_kwargs):
        self._refuse(msg)
        return array.array("h", [])

    def close(self):
        pass


class FakeServer:
    """Replaces the socket server, so port 18001 is never bound and stop() never
    connects to localhost, which could be the live GUI's server."""

    def __init__(self, *_args, **_kwargs):
        pass

    def stop(self):
        pass


def noop(*_args, **_kwargs):
    return None


# Anything that reads hardware, sends a command, changes a setpoint or opens a
# dialog that can do so. Applied to every item class that defines the method.
ITEM_NOOPS = (
    "get_data", "on_currentReturn", "on_F_return", "set_I", "set_F", "set_dI", "set_dF",
    "switchOff", "switchOff2", "reset_pico", "reset_dac", "dac_IV_reset_swhw",
    "get_probe_I", "get_probe_V", "get_probe_F", "show_menu", "menu_save_restore_show",
    "menu_save_restore_save", "menu_save_restore_restore", "menu_save_restore_larger",
    "menu_save_restore_finer", "clear_fails", "ramp_ctrl_var", "arc_start",
    "switch_polarity", "on_check_fast", "fast_func", "set_flow", "moveValve",
    "gas_on", "gas_off", "on_click_regulate",
)
# Includes everything that would write the files shared with the live GUI:
# presets, saved_zoom, saved_minmax, Save data and the operator note fallback.
APP_NOOPS = (
    "start_thread", "the_thread_function_multi_once", "on_destroy", "process_shutdown",
    "on_click_shutdown", "update_ui", "save_minmax", "on_save_zoom_proc", "save_data",
    "clear_graphs", "load_preset", "menu_presets_save", "on_btn_presets", "on_btn_probe",
    "on_note_post", "on_change_ctrl_proc", "on_enable", "on_socket_server_data",
    "place_note_widgets", "on_resize", "place_boxes",    # layout_lab replaces these two
)


def load_lab(source):
    """Import the lab modules and patch them. Call after install_guards()."""
    sys.path.insert(0, HERE)
    os.chdir(HERE)     # saved_zoom_*.txt and friends are opened by relative path
    names = ("common", "socket_server", "duo_sqlite_logger", "mychart_pil", "s1s2_main",
             "commonPS2", "valve", "pressures", "intensities", "koven", "ammeter",
             "magnet_pirani", "magnet_gas", "solidfilament", "arcfilament",
             "switchingmagnet", "mass_flow_controller")
    lab = types.SimpleNamespace(
        **{name: importlib.import_module(name) for name in names})

    # connections, at the point the item constructors ask for them
    lab.common.SocketOrSerial = FakeLink
    lab.common.MySocket = FakeLink
    lab.common.MySerial = FakeLink
    lab.common.MySerialRemote = FakeLink
    lab.common.getDBValue = lambda _id: [-1.0]
    lab.socket_server.SingleConnectionSocketServer = FakeServer
    lab.duo_sqlite_logger.create_logger_from_env = lambda _app: None

    # filament lifetime files are shared with the live GUI; the ramp dialog drives PSUs
    for name in ("update", "savefile", "reset_lifetime"):
        setattr(lab.common.FilamentLifetimeTracker, name, noop)
    lab.common.FilamentRamper.ramp_up = noop
    lab.common.ABar.on_rclick_canvas = noop     # would write saved_minmax

    item_classes = [
        lab.commonPS2.CommonPS, lab.valve.Valve, lab.pressures.Pressure1,
        lab.intensities.Intensities, lab.koven.KOven, lab.ammeter.Ammeter,
        lab.magnet_pirani.MagnetPirani, lab.magnet_gas.MagnetGas,
        lab.solidfilament.SolidFilament, lab.arcfilament.ArcFilament,
        lab.switchingmagnet.SwitchingMagnet,
        lab.mass_flow_controller.MassFlowController]
    for cls in item_classes:
        for name in ITEM_NOOPS:
            if name in cls.__dict__:
                setattr(cls, name, noop)

    for name in APP_NOOPS:
        setattr(lab.s1s2_main.S1S2, name, noop)

    lab.items_module = importlib.import_module(source)
    return lab


class LabHost(tk.Frame):
    """Stands in for the Tk root as the lab GUI's master, so that the GUI can live
    inside a scrollable canvas. S1S2 calls master.title(); the real title is set later."""

    def title(self, *_args):
        return ""


def build_app(lab, host, source):
    """Build the real GUI inside host. Much of the lab code creates widgets with no
    master, so Tk's default root points at host for as long as the build takes. Its
    __init__ also prints a lot, which goes to a buffer."""
    real_root = tk._default_root
    tk._default_root = host
    FakeLink.building = True
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            app = lab.s1s2_main.S1S2(lab.items_module.the_items, source)
            host.update_idletasks()
    finally:
        tk._default_root = real_root
        FakeLink.building = False
    return app


def layout_lab(app, view_width, view_height):
    """S1S2.place_boxes with the column height taken from the window instead of its fixed
    1050, and the chart given the remaining space. Returns the content size."""
    top, col, lowest = 1, 0, 0
    for index, item in enumerate(app.the_items):
        if hasattr(item, "next_pos"):
            item = app.the_items[index + 1]
        elif hasattr(item, "prev_pos"):
            item = app.the_items[index - 1]
        elif hasattr(item, "hide_pos"):
            item.the_box.place(y=-400)
            item.chb_enabled.place(y=-400)
            continue
        height = int(float(item.the_box.place_info().get("height") or 0))
        if height + top + 1 > max(view_height, 300) and top > 1:
            top = 1
            col += 354
        item.the_box.place(x=4 + col, y=top, width=350)
        item.chb_enabled.place(x=1 + col, y=top)
        top += 1 + height
        lowest = max(lowest, top)
    chart_x = 358 + col
    chart_width = max(320, view_width - chart_x - 6)
    chart_height = max(300, view_height - 24)
    app.chart.place(x=chart_x, y=20)
    app.chart.resize(chart_width, chart_height)
    app.btn_probe.place(x=chart_x, y=0, height=18)
    app.btn_clear_graphs.place(x=100 + chart_x, y=0, height=18)
    app.btn_save_data.place(x=220 + chart_x, y=0, height=18)
    app.btn_presets.place(x=320 + chart_x, y=0, height=18)
    return chart_x + chart_width + 4, max(lowest, 20 + chart_height) + 2


def make_read_only(app, lab):
    """state=disabled alone is not enough: instance bindings still fire on disabled
    widgets (mouse wheel on setpoints, the '...' menu, Presets). So the bindtags go too.
    The value checkbuttons only pick what the lab chart shows, so they stay usable."""
    keep = {str(chb) for chb in app.the_checkbuttons}

    def walk(widget):
        if isinstance(widget, lab.mychart_pil.Chart):
            return                      # the lab chart's zoom is display only
        kind = widget.winfo_class()
        if kind in ("Button", "Checkbutton", "Radiobutton", "Entry") and str(widget) not in keep:
            if kind == "Entry":
                widget.configure(state="disabled", disabledforeground="black")
            elif kind == "Checkbutton":
                widget.configure(state="disabled", disabledforeground=widget.cget("fg"))
            else:
                widget.configure(state="disabled")
            widget.bindtags((str(widget.winfo_toplevel()), "all"))
        for child in widget.winfo_children():
            walk(child)
    walk(app.master)
    app.btn_shutdown.place_forget()

    for item in app.the_items:
        if hasattr(item, "lbl_restarts"):       # the counters were never logged
            item.lbl_restarts.configure(text="rs: —")
            item.lbl_comfails.configure(text="cf: —")
        if hasattr(item, "var_polarity"):       # nor was polarity: select neither
            item.var_polarity.set(-1)
        if hasattr(item, "coef_ctrl"):
            item.flags = -1                     # SwitchingMagnet.update_ui reads this


# ===== 3. Logged values -> item attributes =====
# update_ui reads item attributes (current, CR, stats_minI, p, pos, ...), not last_ret,
# so a logged cycle is written back per item through a 'slot': one slot per logged
# control or readout. Signals are matched on (last_names[0], kind, channel_index).
def make_slot(item, name, kind, channel, apply, widgets, bar=None, unit="", label=""):
    return types.SimpleNamespace(item=item, name=name, kind=kind, channel=channel,
                                 apply=apply, widgets=widgets, bar=bar, unit=unit,
                                 label=label, ids=[])


def band(value, low, high):
    return (value if low is None else low, value if high is None else high)


def common_ps_slots(lab, item):
    """CommonPS and subclasses. Readout channels count only existing readouts, so
    with coef_I_read == 0 the U readout is channel 0. F/FR live on the master but are
    logged under the slave's name."""
    name = item.last_names[0]
    slots = []
    if item.coef_ctrl != 0:
        def set_ctrl(v, _lo, _hi):
            item.current = v
            item.var_current_set(v)
        slots.append(make_slot(
            item, name, "control", 0, set_ctrl,
            [(item.chb_currentSet, "Set " + item.descr_ctrl + " = —")],
            item.bar_ctrl, item.units_ctrl, item.descr_ctrl))
    channel = 0
    if item.coef_I_read != 0:
        is_ammeter = isinstance(item, lab.ammeter.Ammeter)
        offset = lab.ammeter.CHEAT_OFFSET if is_ammeter else 0.0

        def set_i(v, lo, hi):
            lo, hi = band(v, lo, hi)
            item.CR, item.stats_minI, item.stats_maxI = v + offset, lo + offset, hi + offset
            item.stats_deltaI = round((hi - lo) / item.coef_I_read)
        widgets = [(item.chb_currentRead, item.descr_I + " = —")]
        if is_ammeter:
            widgets.append((item.chb_nA, "— " + item.units_I))
        slots.append(make_slot(item, name, "readout", channel, set_i, widgets,
                               item.bar_I, item.units_I, item.descr_I))
        channel += 1
    if item.coef_V_read != 0:
        def set_v(v, lo, hi):
            lo, hi = band(v, lo, hi)
            item.VR, item.stats_minV, item.stats_maxV = v, lo, hi
            item.stats_deltaV = round((hi - lo) / item.coef_V_read)
        slots.append(make_slot(item, name, "readout", channel, set_v,
                               [(item.chb_voltageRead, item.descr_V + " = —")],
                               item.bar_V, item.units_V, item.descr_V))
    if item.slave is not None:
        slave_name = item.slave.last_names[0]
        if item.coef_F_ctrl != 0:
            def set_f(v, _lo, _hi):
                item.F = v
                item.var_F_set(v)
            slots.append(make_slot(
                item.slave, slave_name, "control", 0, set_f,
                [(item.chb_F_set, "Set " + item.descr_F_ctrl + " = —")],
                item.bar_ctrlF, item.units_F, item.descr_F_ctrl))
        if item.coef_F_read != 0:
            def set_fr(v, lo, hi):
                lo, hi = band(v, lo, hi)
                item.FR, item.stats_minF, item.stats_maxF = v, lo, hi
                item.stats_deltaF = round((hi - lo) / item.coef_F_read)
            slots.append(make_slot(item.slave, slave_name, "readout", 0, set_fr,
                                   [(item.chb_F_read, item.descr_F + " = —")],
                                   item.bar_F, item.units_F, item.descr_F))
    return slots


def valve_slots(item):
    name = item.last_names[0]

    def set_pos(v, _lo, _hi):
        item.pos = v

    def set_gas(v, _lo, _hi):
        # the log stores 1 for 'on', 0 for anything else; pos -1 means no answer
        item.gas = "???" if item.pos == -1 else ("on" if v == 1 else "off")
        item.gas_update_flag = True
    return [make_slot(item, name, "readout", 0, set_pos,
                      [(item.chb_valvePosRead, "pos = —")], label="pos"),
            make_slot(item, name, "control", 0, set_gas,
                      [(item.lbl_gasOnRead, "Gas ???")], label="on")]


def pressure_slots(item):
    def set_p(v, _lo, _hi):
        item.p = [v / 1e6]      # logged as p*1e6
    return [make_slot(item, item.last_names[0], "readout", 0, set_p,
                      [(item.chb_S1, item.short_name + " = —")], item.bar_P,
                      "1e-6 mbar", item.last_names[1])]


def intensity_slots(app, item):
    def set_intensity(v, lo, hi):
        item.fc_v = v
        item.fc_mi, item.fc_ma = band(v, lo, hi)

    def set_fc(v, _lo, _hi):
        index = int(v)
        app.main_selected_fc_index = index if -1 <= index <= 3 else -1
    return [make_slot(item, "intensities", "readout", 0, set_intensity,
                      [(item.chb_int, "I = —")], item.bar_P, "nA", "intensity"),
            make_slot(item, "intensities", "readout", 1, set_fc,
                      [(item.chb_fc_ind, "FC ind = —")], label="fc_index")]


def build_slots(app, lab, meta):
    """All slots of the GUI, each with the signal ids that can feed it. A name_mismatch
    row is logged as channel_N under the_name, so the_name is tried as well."""
    slots = []
    for item in app.the_items:
        if isinstance(item, lab.commonPS2.CommonPS):
            slots += common_ps_slots(lab, item)
        elif isinstance(item, lab.valve.Valve):
            slots += valve_slots(item)
        elif isinstance(item, lab.pressures.Pressure1):
            slots += pressure_slots(item)
        elif isinstance(item, lab.intensities.Intensities):
            slots += intensity_slots(app, item)
    for slot in slots:
        for sig in meta["signals"].values():
            if (sig["kind"] == slot.kind and sig["channel"] == slot.channel
                    and sig["item"] in (slot.name, slot.item.the_name)):
                slot.ids.append(sig["id"])
    return slots


def set_colour(widget, colour, memo):
    if memo.get(widget) != colour:
        memo[widget] = colour
        widget.configure(fg=colour, disabledforeground=colour)


def inject(app, lab, slots, enabled_ids, snapshot, colours, base_colours):
    """Write one cycle into the items and let their own update_ui draw it. snapshot is
    {signal_id: (value, band_min, band_max, value_text, status)}; {} means no data."""
    for item in app.the_items:
        rec = snapshot.get(enabled_ids.get(item.the_name))
        enabled = rec is None or rec[0] is None or bool(rec[0])
        item.enabled = enabled
        lab.s1s2_main.set_checked(item.chb_enabled, enabled)

    states = []
    for slot in slots:
        rec = next((snapshot[i] for i in slot.ids if i in snapshot), None)
        value = None if rec is None else rec[0]
        ok = value is not None
        slot.apply(value if ok else 0.0,
                   rec[1] if ok else None, rec[2] if ok else None)
        status = (rec[4] or "") if rec else ""
        states.append((slot, ok, rec[3] if rec else None,
                       "disabled_cached" in status or not slot.item.enabled))

    for item in app.the_items:
        if item.is_master:
            try:
                item.update_ui()
            except Exception as ex:
                print("update_ui failed for", item.the_name + ":", ex, file=sys.__stderr__)

    # item.update_ui formats numbers only, so a dash is written over it afterwards
    for slot, ok, value_text, stale in states:
        for widget, dash in slot.widgets:
            if not ok:
                text = dash
                if value_text:      # non_numeric: the logged text is what was shown
                    text = dash.replace("—", value_text)
                widget.configure(text=text)
                widget._orig_text = text    # common.change_text compares against this
            set_colour(widget, GREY if stale or not ok else base_colours[widget], colours)
        if slot.bar is not None and not ok:
            slot.bar.update(0, 0, txt="no data")
            slot.bar.canvas.itemconfigure(slot.bar.bar_mi, fill=NO_DATA)
            slot.bar.clr = NO_DATA
    for slot, ok, _text, _stale in states:
        if not ok and hasattr(slot.item, "lbl_power"):
            slot.item.lbl_power.configure(text="— W")


# ===== 4. Reading the DB =====
class Db:
    """One read-only connection, owned by one thread.

    mode=ro on a closed WAL file creates -shm and -wal next to it and leaves them
    there, so a closed file is opened immutable. immutable ignores the WAL, so a file
    with a non-empty -wal is opened mode=ro. That is checked before every query,
    because the live GUI can start writing to a file while it is open here."""

    def __init__(self, path):
        self.path = path
        self.mode = None
        self.conn = None
        self.warning = ""

    def wanted_mode(self):
        try:
            return "ro" if os.path.getsize(self.path + "-wal") > 0 else "immutable"
        except OSError:
            return "immutable"

    def open_as(self, mode):
        # mode=ro is needed with immutable too: alone, it creates a missing file
        query = "mode=ro" if mode == "ro" else "mode=ro&immutable=1"
        uri = "file:" + urllib.parse.quote(self.path) + "?" + query
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        conn.execute("PRAGMA query_only=ON")
        return conn

    def connect(self):
        mode = self.wanted_mode()
        if self.conn is not None and mode == self.mode:
            return self.conn
        self.close()
        self.warning = ""
        try:
            self.conn = self.open_as(mode)
        except sqlite3.OperationalError:
            if mode != "ro":
                raise
            mode = "immutable"      # no write access to the -shm, e.g. a read-only copy
            self.conn = self.open_as(mode)
            self.warning = "Could not read the -wal: its newest cycles are not shown."
        self.mode = mode
        return self.conn

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None


def table_columns(conn, table):
    return [row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")]


def load_runs(conn):
    """Runs that have cycles, oldest first. Times come from idx_cycle_run_ts: MIN()
    over the whole table would scan it, and run.stop_utc is missing in old files."""
    runs = []
    has_stop = "stop_utc" in table_columns(conn, "run")
    sql = "SELECT id, source" + (", stop_utc" if has_stop else ", NULL") + " FROM run ORDER BY id"
    for run_id, source, stop_utc in conn.execute(sql).fetchall():
        first = conn.execute("SELECT id, ts_unix FROM cycle WHERE run_id=?"
                             " ORDER BY ts_unix LIMIT 1", (run_id,)).fetchone()
        if first is None:
            continue
        last = conn.execute("SELECT id, ts_unix FROM cycle WHERE run_id=?"
                            " ORDER BY ts_unix DESC LIMIT 1", (run_id,)).fetchone()
        runs.append({"id": run_id, "source": source, "stop_utc": stop_utc,
                     "first_id": first[0], "first_t": first[1],
                     "last_id": last[0], "last_t": last[1]})
    runs.sort(key=lambda run: run["first_t"])
    return runs


def load_signals(conn):
    signals = {}
    for sid, item, name, kind, channel in conn.execute(
            "SELECT id, item_name, signal_name, signal_kind, channel_index FROM signal"):
        signals[sid] = {"id": sid, "item": item, "name": name, "kind": kind,
                        "channel": channel}
    return signals


def load_notes(conn, tables):
    if "note" not in tables:     # schema v1 files have no note table
        return []
    return conn.execute("SELECT ts_unix, text FROM note ORDER BY ts_unix, id").fetchall()


RAMP_KINDS = ("setpoint_change", "setpoint_request")
RAMP_GAP_S = 10.0


def load_events(conn, tables):
    """Marker list. A ramp logs an event per cycle (real October data: 9401 requests,
    7021 filament changes), so each ramp collapses into one marker.
    Returns [(ts_unix, text)]."""
    if "event" not in tables:
        return []
    rows = conn.execute(
        "SELECT ts_unix, event_type, item_name, signal_name, value_before, value_after"
        " FROM event WHERE event_type != 'run_start_snapshot' ORDER BY ts_unix, id").fetchall()
    events = []
    ramp = {}       # (kind, item, signal) -> (index into events, last ts, start, steps)
    for ts, kind, item, signal, before, after in rows:
        name = ".".join(str(x) for x in (item, signal) if x is not None)
        key = (kind, item, signal)
        if kind in RAMP_KINDS and key in ramp and ts - ramp[key][1] < RAMP_GAP_S:
            index, _last, start, steps = ramp[key]
            events[index] = (events[index][0], "{}: {} → {} (ramp, {} steps)".format(
                name, start, after, steps + 1))
            ramp[key] = (index, ts, start, steps + 1)
            continue
        if kind in RAMP_KINDS:
            ramp[key] = (len(events), ts, before, 1)
        if kind == "setpoint_change":
            text = "{}: {} → {}".format(name, before, after)
        elif kind == "setpoint_request":
            text = "{} requested: {}".format(name, after)
        else:
            text = "{} {}: {} → {}".format(kind, name, before, after)
        events.append((ts, text))
    return events


def load_meta(path):
    db = Db(path)
    conn = db.connect()
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    missing = {"run", "signal", "cycle", "measurement"} - tables
    if missing:
        raise ValueError("not a duoplasmatron log, missing tables: " + ", ".join(sorted(missing)))
    meta = {"tables": tables, "runs": load_runs(conn), "signals": load_signals(conn),
            "notes": load_notes(conn, tables), "events": load_events(conn, tables),
            "schema": conn.execute("PRAGMA user_version").fetchone()[0],
            "mode": db.mode, "warning": db.warning}
    db.close()
    if not meta["runs"]:
        raise ValueError("this DB has no logged cycles")
    return meta


def gui_for(meta, path):
    """S1 or S2 from run.source. S1_burnin and the test GUIs have other items."""
    sources = {run["source"] for run in meta["runs"]}
    if sources == {"S1"} or sources == {"S2"}:
        return sources.pop()
    raise ValueError("{}: run source is {}, this viewer shows only S1 or S2".format(
        os.path.basename(path), ", ".join(sorted(sources))))


def run_at(runs, t):
    index = bisect.bisect_right([run["first_t"] for run in runs], t) - 1
    return runs[max(index, 0)]


def locate_cycle(conn, runs, t):
    """(cycle_id, ts_unix, run_id) of the last cycle at or before t, through
    idx_cycle_run_ts. cycle has no index on ts_unix alone."""
    run = run_at(runs, t)
    row = conn.execute("SELECT id, ts_unix FROM cycle WHERE run_id=? AND ts_unix<=?"
                       " ORDER BY ts_unix DESC LIMIT 1", (run["id"], t)).fetchone()
    if row is None:
        row = (run["first_id"], run["first_t"])
    return row[0], row[1], run["id"]


def read_cycle(conn, cycle_id):
    # INDEXED BY: without ANALYZE data the planner can pick idx_measurement_signal,
    # which walks a whole month. That query did not finish in 90 s on 2 GB.
    return {row[0]: row[1:] for row in conn.execute(
        "SELECT signal_id, value, band_min, band_max, value_text, status"
        " FROM measurement INDEXED BY idx_measurement_cycle WHERE cycle_id=?", (cycle_id,))}


def cycle_id_range(conn, runs, t0, t1):
    """Smallest and largest cycle id inside [t0, t1], or None."""
    low = high = None
    for run in runs:
        if run["last_t"] < t0 or run["first_t"] > t1:
            continue
        a = conn.execute("SELECT id FROM cycle WHERE run_id=? AND ts_unix>=?"
                         " ORDER BY ts_unix LIMIT 1", (run["id"], t0)).fetchone()
        b = conn.execute("SELECT id FROM cycle WHERE run_id=? AND ts_unix<=?"
                         " ORDER BY ts_unix DESC LIMIT 1", (run["id"], t1)).fetchone()
        if a is None or b is None:
            continue
        low = a[0] if low is None else min(low, a[0])
        high = b[0] if high is None else max(high, b[0])
    return None if low is None else (low, high)


def sentinel_ids(meta):
    """Signals where a negative value means 'no reading': pressure is logged as
    -1e6 when the control system does not answer, gas pos as -1."""
    return {sid for sid, sig in meta["signals"].items()
            if sig["kind"] == "readout" and (
                sig["item"] == "pressure" or (sig["item"] == "gas" and sig["name"] == "pos"))}


def read_raw(db, meta, sids, t0, t1, offsets, is_stale):
    """Plot data for [t0, t1]: {sid: ([t], [lo], [value], [hi])}. A NaN row marks a
    gap. Reads in chunks, so a live WAL is not pinned and a newer request can stop it."""
    series = {sid: ([], [], [], []) for sid in sids}
    last_seen = {}
    conn = db.connect()
    id_range = cycle_id_range(conn, meta["runs"], t0, t1)
    if id_range is None:
        return series
    negative_is_gap = sentinel_ids(meta)
    marks = ",".join("?" * len(sids))
    sql = ("SELECT cycle_id, signal_id, value, band_min, band_max, status FROM measurement"
           " INDEXED BY idx_measurement_cycle WHERE cycle_id BETWEEN ? AND ?"
           " AND signal_id IN (" + marks + ")")
    for start in range(id_range[0], id_range[1] + 1, RAW_CHUNK):
        if is_stale():
            return None
        conn = db.connect()
        stop = min(start + RAW_CHUNK - 1, id_range[1])
        cycles = {row[0]: row[1:] for row in conn.execute(
            "SELECT id, ts_unix, run_id FROM cycle WHERE id BETWEEN ? AND ?", (start, stop))}
        for cycle_id, sid, value, low, high, status in conn.execute(
                sql, [start, stop] + list(sids)):
            ts, run_id = cycles[cycle_id]
            if ts < t0 or ts > t1:
                continue
            ts_list, lo_list, mid_list, hi_list = series[sid]
            previous = last_seen.get(sid)
            if previous is not None and (run_id != previous[1] or ts - previous[0] > GAP_S):
                ts_list.append(previous[0])
                lo_list.append(NAN)
                mid_list.append(NAN)
                hi_list.append(NAN)
            last_seen[sid] = (ts, run_id)
            gone = (value is None or (status and "disabled_cached" in status)
                    or (sid in negative_is_gap and value < 0))
            if gone:
                value = low = high = NAN
            elif low is None or high is None or not low <= value <= high:
                low = high = value      # placeholder bands (5.1-5.8) were logged around 0
            shift = offsets.get(sid, 0.0)
            ts_list.append(ts)
            lo_list.append(low + shift)
            mid_list.append(value + shift)
            hi_list.append(high + shift)
    return series


# ===== 5. Per-minute overview cache =====
def overview_path(path):
    stat = os.stat(path)
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(path))
    return os.path.join(CACHE_DIR, "{}-{}-{}.sqlite".format(name, stat.st_size, stat.st_mtime_ns))


def build_overview(path, meta, cache_path, report, cancel):
    """One pass over the DB into a sidecar file, never into the DB or its folder.
    Written to .tmp and renamed at the end, so a cancelled build leaves nothing behind.
    Returns True when finished."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = cache_path + ".tmp"
    with contextlib.suppress(FileNotFoundError):
        os.remove(tmp)
    out = sqlite3.connect(tmp)
    out.execute("PRAGMA journal_mode=OFF")
    out.execute("PRAGMA synchronous=OFF")
    out.execute("CREATE TABLE minute (signal_id INTEGER, bucket INTEGER, vmin REAL, vmax REAL,"
                " vsum REAL, n INTEGER, PRIMARY KEY (signal_id, bucket)) WITHOUT ROWID")
    data_ids = [sid for sid, sig in meta["signals"].items()
                if sig["kind"] in ("control", "readout")]
    gaps = ",".join(str(sid) for sid in sentinel_ids(meta))
    # A valid band keeps dips that happened inside a cycle. A band that does not contain
    # the value is the constructor's placeholder and is ignored.
    low = "CASE WHEN m.band_min<=m.value AND m.band_max>=m.value THEN m.band_min ELSE m.value END"
    high = "CASE WHEN m.band_min<=m.value AND m.band_max>=m.value THEN m.band_max ELSE m.value END"
    sql = ("SELECT m.signal_id, CAST(c.ts_unix/60 AS INTEGER), MIN(" + low + "), MAX(" + high + "),"
           " SUM(m.value), COUNT(m.value)"
           " FROM cycle c CROSS JOIN measurement m INDEXED BY idx_measurement_cycle"
           " ON m.cycle_id=c.id WHERE c.id BETWEEN ? AND ?"
           " AND m.signal_id IN (" + ",".join(str(sid) for sid in data_ids) + ")"
           " AND (m.status IS NULL OR m.status NOT LIKE '%disabled_cached%')"
           " AND NOT (m.signal_id IN (" + gaps + ") AND m.value<0)"
           " GROUP BY 1, 2")
    upsert = ("INSERT INTO minute VALUES (?,?,?,?,?,?) ON CONFLICT (signal_id, bucket) DO UPDATE"
              " SET vmin=min(vmin, excluded.vmin), vmax=max(vmax, excluded.vmax),"
              " vsum=vsum+excluded.vsum, n=n+excluded.n")
    db = Db(path)
    first = min(run["first_id"] for run in meta["runs"])
    last = max(run["last_id"] for run in meta["runs"])
    try:
        for start in range(first, last + 1, OVERVIEW_CHUNK):
            if cancel.is_set():
                out.close()
                os.remove(tmp)
                return False
            rows = db.connect().execute(sql, (start, start + OVERVIEW_CHUNK - 1)).fetchall()
            out.executemany(upsert, [row for row in rows if row[5]])
            report((start - first) / max(last - first, 1))
        out.commit()
        out.close()
        os.replace(tmp, cache_path)
    finally:
        db.close()
    prefix = os.path.basename(cache_path).rsplit("-", 2)[0] + "-"
    for name in os.listdir(CACHE_DIR):      # older versions of this same file
        if name.startswith(prefix) and name != os.path.basename(cache_path):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(CACHE_DIR, name))
    return True


def read_overview(cache_path, sids, t0, t1, columns, offsets):
    """Same shape as read_raw, from the cache. Minutes are merged into about one
    bucket per screen column, keeping the min and max of what they cover."""
    span_minutes = max((t1 - t0) / 60.0, 1.0)
    merge = max(1, int(span_minutes / max(columns, 1)))
    conn = sqlite3.connect("file:" + urllib.parse.quote(cache_path) + "?mode=ro&immutable=1", uri=True)
    series = {}
    try:
        for sid in sids:
            ts_list, lo_list, mid_list, hi_list = [], [], [], []
            previous = None
            shift = offsets.get(sid, 0.0)
            for group, first, low, high, total, count in conn.execute(
                    "SELECT bucket/?, MIN(bucket), MIN(vmin), MAX(vmax), SUM(vsum), SUM(n)"
                    " FROM minute WHERE signal_id=? AND bucket BETWEEN ? AND ?"
                    " GROUP BY 1 ORDER BY 1",
                    (merge, sid, int(t0 // 60) - merge, int(t1 // 60) + merge)):
                centre = (first + merge / 2.0) * 60.0
                if previous is not None and group - previous > 1:
                    ts_list.append(centre)
                    lo_list.append(NAN)
                    mid_list.append(NAN)
                    hi_list.append(NAN)
                previous = group
                ts_list.append(centre)
                lo_list.append(low + shift)
                mid_list.append(total / count + shift)
                hi_list.append(high + shift)
            series[sid] = (ts_list, lo_list, mid_list, hi_list)
    finally:
        conn.close()
    return series


# ===== 6. Time helpers =====
def to_local(t, fmt="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.fromtimestamp(t).strftime(fmt)


def parse_local(text):
    return datetime.datetime.strptime(text.strip(), "%Y-%m-%d %H:%M").timestamp()


def duration_text(seconds):
    minutes = int(seconds // 60)
    if minutes < 60:
        return "{} min".format(minutes)
    return "{} h {:02d} min".format(minutes // 60, minutes % 60)


TIME_STEPS = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800,
              21600, 43200, 86400, 172800, 604800)


def time_ticks(t0, t1, max_ticks):
    """Ticks on round local times."""
    step = next((s for s in TIME_STEPS if (t1 - t0) / s <= max_ticks), TIME_STEPS[-1])
    utc_offset = datetime.datetime.fromtimestamp(t0).astimezone().utcoffset().total_seconds()
    tick = math.ceil((t0 + utc_offset) / step) * step - utc_offset
    if step >= 86400:
        fmt = "%d %b"
    elif t1 - t0 > 86400:
        fmt = "%d %b %H:%M"
    elif step < 60:
        fmt = "%H:%M:%S"
    else:
        fmt = "%H:%M"
    ticks = []
    while tick <= t1:
        ticks.append((tick, to_local(tick, fmt)))
        tick += step
    return ticks


# ===== 7. The viewer =====
def rebin(ts, lows, mids, highs, t0, t1, columns):
    """Reduce to one point per screen column, keeping each column's min and max, so a
    dip of one cycle survives. Short series pass through untouched."""
    if len(ts) <= 2 * columns:
        return ts, lows, mids, highs
    width = (t1 - t0) / max(columns, 1)
    out = ([], [], [], [])
    current = None
    start = low = mid = high = None

    def flush():
        if current is not None:
            for column, value in zip(out, (start, low, mid, high)):
                column.append(value)

    for t, lo, value, hi in zip(ts, lows, mids, highs):
        if value != value:
            flush()
            current = None
            for column, gap in zip(out, (t, NAN, NAN, NAN)):
                column.append(gap)
            continue
        col = int((t - t0) / width)
        if col != current:
            flush()
            current, start, low, mid, high = col, t, lo, value, hi
        else:
            low, high, mid = min(low, lo), max(high, hi), value
    flush()
    return out


def wheel_units(event):
    """Scroll amount, positive = up or away. Linux sends Button-4/5, Windows multiples
    of 120, and a Mac trackpad many small deltas."""
    if event.num == 4:
        return 1.0
    if event.num == 5:
        return -1.0
    if abs(event.delta) >= 120:
        return event.delta / 120.0
    return max(-3.0, min(3.0, event.delta / 4.0))


class Viewer:
    """Both windows and the one shared cursor. DB work happens on two daemon threads
    (cursor, window) and comes back through self.results, which the Tk thread polls: Tk
    is not safe to call from a worker.

    self.cursor_t is the only cursor. Every control calls set_cursor(), which moves the
    lines and the time label at once and asks for the lab GUI repaint, debounced."""

    def __init__(self, root, path, meta, source, app, lab, frame):
        self.root, self.path, self.meta, self.source = root, path, meta, source
        self.app, self.lab, self.frame = app, lab, frame
        self.banner = frame.banner
        self.db_name = os.path.basename(path)
        self.runs = meta["runs"]
        self.first_t = min(run["first_t"] for run in self.runs)
        self.last_t = max(run["last_t"] for run in self.runs)

        self.slots = build_slots(app, lab, meta)
        self.enabled_ids = {sig["item"]: sig["id"] for sig in meta["signals"].values()
                            if sig["kind"] == "item_attr" and sig["name"] == "enabled"}
        self.base_colours = {}
        for slot in self.slots:
            for widget, _dash in slot.widgets:
                self.base_colours[widget] = widget.cget("fg")
        self.colours = {}
        self.offsets = {}
        for slot in self.slots:
            if isinstance(slot.item, lab.ammeter.Ammeter) and slot.kind == "readout":
                for sid in slot.ids:
                    self.offsets[sid] = lab.ammeter.CHEAT_OFFSET
        self.labels = self.signal_labels()
        self.chart_sids = self.chart_signal_ids()

        self.selected = []          # signal ids, in picker order
        self.log_y = set()
        self.y_view = {}            # sid -> (ymin, ymax); absent = auto Y. log10 when log.
        self.panels = []            # what the last redraw laid out
        self.series = {}
        self.strip_series = None
        self.strip_key = None
        self.loaded = None          # (kind, sids, t0, t1, columns)
        self.waiting_for_overview = False
        self.overview_cancelled = False
        self.overview_file = overview_path(path)
        self.overview_ready = os.path.exists(self.overview_file)
        self.overview_cancel = threading.Event()
        self.overview_thread = None

        self.range = [self.first_t, self.last_t]    # what Home, slider and strip cover
        self.view = [self.first_t, self.last_t]     # what the plots show
        self.history = []
        self.last_remembered = 0.0
        self.cursor_t = self.last_t
        self.shown_cycle = None
        self.snapshot = {}
        self.snapshot_t = None
        self.chart_t = self.last_t
        self.drag = None
        self.strip_drag = None
        self.hits = []              # (x, text, is_note, ts) of the drawn markers
        self.redraw_id = None
        self.settle_id = None
        self.settle_view_id = None
        self.last_lab = 0.0
        self.playing = False
        self.play_id = None
        self.closing = False
        self.slider_sync = False

        self.results = queue.Queue()
        self.lock = threading.Lock()
        self.wake_cursor = threading.Event()
        self.wake_window = threading.Event()
        self.cursor_job = None
        self.step_job = 0
        self.chart_job = None
        self.window_job = None
        self.strip_job = None
        self.window_gen = 0

        self.play_text = tk.StringVar(value="▶ Play")
        self.speed_var = tk.StringVar(value="×1")
        self.build_lab_strip()
        self.build_timeline()
        self.report_mapping()
        self.patch_lab_chart()
        self.root.update()
        self.on_fit()

        for target in (self.cursor_worker, self.window_worker):
            threading.Thread(target=target, daemon=True).start()
        self.poll_id = self.root.after(POLL_MS, self.poll)
        self.show_last_hour()
        if self.overview_ready:
            self.request_strip()
        else:
            self.start_overview()

    # ----- signals -----
    def signal_labels(self):
        labels = {}
        for sid, sig in self.meta["signals"].items():
            if sig["kind"] not in ("control", "readout"):
                continue
            unit = next((slot.unit for slot in self.slots if sid in slot.ids), "")
            text = sig["item"] + " " + sig["name"] + (" set" if sig["kind"] == "control" else "")
            labels[sid] = text + (" (" + unit.strip() + ")" if unit.strip() else "")
        return labels

    def chart_signal_ids(self):
        """Signal ids for each lab chart line, in the order of app.the_checkbuttons."""
        by_widget = {}
        for slot in self.slots:
            for widget, _dash in slot.widgets:
                by_widget[widget] = slot
        return [by_widget[chb].ids if chb in by_widget else []
                for chb in self.app.the_checkbuttons]

    def report_mapping(self):
        used = {sid for slot in self.slots for sid in slot.ids}
        no_widget = [self.labels[sid] for sid in self.labels if sid not in used]
        no_data = sorted({slot.item.the_name + " " + slot.label
                          for slot in self.slots if not slot.ids})
        parts = []
        if no_widget:
            parts.append("{} logged signals have no widget".format(len(no_widget)))
            print("Logged signals with no widget:", ", ".join(no_widget))
        if no_data:
            parts.append("{} widgets have no data in this file".format(len(no_data)))
            print("Widgets with no data in this file:", ", ".join(no_data))
        if self.meta["mode"] == "ro":
            parts.insert(0, "Live file (it has a -wal): a .backup copy is preferred")
        if self.meta["warning"]:
            parts.insert(0, self.meta["warning"])
        self.warning_var.set(". ".join(parts))

    # ----- lab chart -----
    def patch_lab_chart(self):
        """The live chart ends at 'now'. Here it spans the cursor, with a line on it."""
        chart = self.app.chart
        real_draw, real_draw_all = chart.draw, chart._draw_all

        def draw(*args, **kwargs):
            kwargs["x_minmax"] = (-CHART_SPAN_MIN, CHART_SPAN_MIN)
            real_draw(*args, **kwargs)

        def draw_all(full=False):
            real_draw_all(full)
            inner = chart.inner_canvas
            inner.delete("hv_cursor")
            # same transform as the chart's own crosshair: pixel = add + mult * minutes
            x = chart.x_coef_add
            inner.create_line(x, 0, x, inner.winfo_height(), fill=CURSOR, width=2,
                              tags="hv_cursor")
        chart.draw = draw
        chart._draw_all = draw_all
        self.lab.mychart_pil.timestr = self.chart_time_text

    def chart_time_text(self, minutes):
        """Replaces mychart_pil.timestr, which adds the offset to the current time."""
        return to_local(self.chart_t + minutes * 60.0, "%a %H:%M")

    # ----- lab window -----
    def build_lab_strip(self):
        strip = self.frame.strip
        row = tk.Frame(strip)
        row.pack(fill="x")
        self.time_var = tk.StringVar()
        self.run_var_lab = tk.StringVar()
        self.gap_var = tk.StringVar()
        tk.Label(row, textvariable=self.time_var, font=("", 15, "bold"), fg=TEXT).pack(side="left")
        tk.Label(row, textvariable=self.run_var_lab, fg=TEXT).pack(side="left", padx=10)
        tk.Label(row, textvariable=self.gap_var, fg=GREY, font=("", 11, "bold")).pack(side="left")
        tk.Button(row, text="?", command=self.on_help).pack(side="right")
        tk.Button(row, text="Fit to screen", command=self.on_fit).pack(side="right", padx=4)

        self.slider = ttk.Scale(strip, from_=0.0, to=1.0, command=self.on_slider)
        self.slider.pack(fill="x", pady=2)

        row = tk.Frame(strip)
        row.pack(fill="x")
        for text, command in (("−1 min", lambda: self.jump(-60.0)),
                              ("−1 cycle", lambda: self.step(-1)),
                              ("+1 cycle", lambda: self.step(1)),
                              ("+1 min", lambda: self.jump(60.0))):
            tk.Button(row, text=text, command=command).pack(side="left", padx=1)
        tk.Button(row, textvariable=self.play_text, command=self.on_play).pack(side="left", padx=(10, 2))
        ttk.Combobox(row, textvariable=self.speed_var, width=4, state="readonly",
                     values=("×1", "×10", "×60")).pack(side="left")

        canvas = self.frame.canvas
        self.root.bind("<MouseWheel>", self.on_lab_wheel)
        self.root.bind("<Button-4>", self.on_lab_wheel)
        self.root.bind("<Button-5>", self.on_lab_wheel)
        self.root.bind("<Shift-Button-4>", self.on_lab_wheel)
        self.root.bind("<Shift-Button-5>", self.on_lab_wheel)
        canvas.configure(xscrollincrement=8, yscrollincrement=8)

    def on_lab_wheel(self, event):
        steps = -int(round(wheel_units(event) * 3)) or (-1 if wheel_units(event) > 0 else 1)
        if event.state & STATE_SHIFT:
            self.frame.canvas.xview_scroll(steps, "units")
        else:
            self.frame.canvas.yview_scroll(steps, "units")

    def on_fit(self):
        """Reflow the item columns to the visible height and give the chart the rest."""
        canvas = self.frame.canvas
        self.root.update_idletasks()
        width, height = layout_lab(self.app, canvas.winfo_width(), canvas.winfo_height())
        self.frame.host.configure(width=width, height=height)
        canvas.itemconfigure(self.frame.window, width=width, height=height)
        canvas.configure(scrollregion=(0, 0, width, height))
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)
        if len(self.app.data_x) > 1:
            self.app.draw_chart(full=True)

    def on_help(self):
        window = tk.Toplevel(self.root)
        window.title("History viewer controls")
        tk.Label(window, text=HELP_TEXT, justify="left", anchor="nw", padx=12, pady=10,
                 font=("", 11)).pack()
        window.bind("<Escape>", lambda _e: window.destroy())
        window.focus_set()

    # ----- timeline window -----
    def build_timeline(self):
        top = self.top = tk.Toplevel(self.root)
        width = min(1150, self.root.winfo_screenwidth() - 40)
        height = min(820, self.root.winfo_screenheight() - 90)
        top.geometry("{}x{}".format(width, height))
        self.banner_var = tk.StringVar()
        tk.Label(top, textvariable=self.banner_var, bg="#b00020", fg="white",
                 font=("", 11, "bold"), anchor="w", padx=8).pack(fill="x")

        side = tk.Frame(top, width=270)
        side.pack(side="left", fill="y", padx=6, pady=6)
        side.pack_propagate(False)
        main = tk.Frame(top)
        main.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=6)

        info = "{}\n{} to {}\nSchema v{}, {} runs".format(
            self.db_name, to_local(self.first_t, "%Y-%m-%d %H:%M"),
            to_local(self.last_t, "%Y-%m-%d %H:%M"), self.meta["schema"], len(self.runs))
        tk.Label(side, text=info, justify="left", anchor="w", fg=TEXT).pack(fill="x")

        times = tk.Frame(side)
        times.pack(fill="x", pady=(6, 0))
        self.from_var, self.to_var = tk.StringVar(), tk.StringVar()
        for row, (text, var) in enumerate((("From", self.from_var), ("To", self.to_var))):
            tk.Label(times, text=text).grid(row=row, column=0, sticky="w")
            entry = tk.Entry(times, textvariable=var, width=17)
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=1)
            entry.bind("<Return>", lambda _e: self.on_load())
        buttons = tk.Frame(side)
        buttons.pack(fill="x", pady=2)
        tk.Button(buttons, text="Load", command=self.on_load).pack(side="left")
        tk.Button(buttons, text="Selected day", command=self.on_day).pack(side="left", padx=3)
        tk.Button(buttons, text="Whole DB", command=self.on_whole).pack(side="left")

        self.run_var = tk.StringVar()
        names = []
        for run in self.runs:
            names.append("Run {}: {} to {} ({})".format(
                run["id"], to_local(run["first_t"], "%d %b %H:%M"),
                to_local(run["last_t"], "%d %b %H:%M"),
                duration_text(run["last_t"] - run["first_t"])))
        self.run_box = ttk.Combobox(side, textvariable=self.run_var, values=names, state="readonly")
        self.run_box.pack(fill="x", pady=2)
        self.run_box.bind("<<ComboboxSelected>>", self.on_run)

        tk.Label(side, text="Signals", anchor="w", font=("", 10, "bold")).pack(fill="x", pady=(6, 0))
        picker = tk.Frame(side)
        picker.pack(fill="both", expand=True)
        pick_canvas = tk.Canvas(picker, highlightthickness=0, width=240)
        scroll = tk.Scrollbar(picker, command=pick_canvas.yview)
        pick_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        pick_canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(pick_canvas)
        pick_canvas.create_window(0, 0, window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: pick_canvas.configure(
            scrollregion=pick_canvas.bbox("all")))
        self.build_picker(inner)

        tk.Label(side, text="Notes (click to jump)", anchor="w",
                 font=("", 10, "bold")).pack(fill="x", pady=(6, 0))
        self.note_list = tk.Listbox(side, height=6, exportselection=False)
        self.note_list.pack(fill="x")
        if "note" not in self.meta["tables"]:
            self.note_list.insert("end", "(this DB has no note table)")
        elif not self.meta["notes"]:
            self.note_list.insert("end", "(no notes)")
        for ts, text in self.meta["notes"]:
            self.note_list.insert("end", to_local(ts, "%d %b %H:%M  ") + text)
        self.note_list.bind("<<ListboxSelect>>", self.on_note_pick)

        controls = tk.Frame(main)
        controls.pack(fill="x")
        tk.Button(controls, textvariable=self.play_text, command=self.on_play).pack(side="left")
        ttk.Combobox(controls, textvariable=self.speed_var, width=4, state="readonly",
                     values=("×1", "×10", "×60")).pack(side="left", padx=4)
        for text, seconds in (("10 min", 600), ("1 h", 3600), ("6 h", 21600), ("1 day", 86400)):
            tk.Button(controls, text=text,
                      command=lambda s=seconds: self.around_cursor(s)).pack(side="left", padx=1)
        self.show_events = tk.IntVar(value=1)
        tk.Checkbutton(controls, text="Events", variable=self.show_events,
                       command=self.schedule_redraw).pack(side="left", padx=4)
        tk.Button(controls, text="?", command=self.on_help).pack(side="right")
        self.cancel_button = tk.Button(controls, text="Cancel", command=self.on_cancel_overview)
        self.build_button = tk.Button(controls, text="Build overview", command=self.on_build_overview)
        self.progress = ttk.Progressbar(controls, length=140, maximum=1.0)
        self.status_var = tk.StringVar()
        tk.Label(controls, textvariable=self.status_var, anchor="w", fg=TEXT).pack(
            side="left", fill="x", expand=True, padx=6)

        self.warning_var = tk.StringVar()
        tk.Label(main, textvariable=self.warning_var, anchor="w", fg=NOTE).pack(fill="x")
        self.info_var = tk.StringVar()
        tk.Label(main, textvariable=self.info_var, anchor="w", fg=TEXT).pack(side="bottom", fill="x")

        strip = self.strip = tk.Canvas(main, bg="white", height=STRIP_H, highlightthickness=0)
        strip.pack(fill="x", pady=(2, 3))
        strip.bind("<Button-1>", self.on_strip_press)
        strip.bind("<B1-Motion>", self.on_strip_drag)
        strip.bind("<ButtonRelease-1>", self.on_strip_release)

        canvas = self.canvas = tk.Canvas(main, bg="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Configure>", lambda _e: self.on_view_changed())
        canvas.bind("<Button-1>", self.on_press)
        canvas.bind("<B1-Motion>", self.on_drag)
        canvas.bind("<ButtonRelease-1>", self.on_release)
        canvas.bind("<Double-Button-1>", self.on_double)
        for button in (2, 3):       # right button: 2 on a Mac, 3 on Linux
            canvas.bind("<Button-%d>" % button, self.on_box_press)
            canvas.bind("<B%d-Motion>" % button, self.on_drag)
            canvas.bind("<ButtonRelease-%d>" % button, self.on_release)
        canvas.bind("<Motion>", self.on_hover)
        canvas.bind("<Leave>", lambda _e: self.canvas.delete("tip"))
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(sequence, self.on_wheel)

        for window in (self.root, top):
            window.bind("<Left>", lambda e: self.on_arrow(e, -1))
            window.bind("<Right>", lambda e: self.on_arrow(e, 1))
            window.bind("<Shift-Left>", lambda e: self.on_arrow(e, -1, 60.0))
            window.bind("<Shift-Right>", lambda e: self.on_arrow(e, 1, 60.0))
            window.bind("<Home>", lambda e: self.typing(e) or self.on_home())
            window.bind("<BackSpace>", lambda e: self.typing(e) or self.on_back())
            window.bind("<question>", lambda e: self.typing(e) or self.on_help())
            window.protocol("WM_DELETE_WINDOW", self.close)

    def build_picker(self, parent):
        """Checkboxes grouped by item, in the order of the GUI."""
        groups = []
        for item in self.app.the_items:
            names = {item.the_name, item.last_names[0]}
            sids = [sid for sid in self.labels if self.meta["signals"][sid]["item"] in names]
            groups.append((item.the_name, sids))
        placed = {sid for _name, sids in groups for sid in sids}
        others = [sid for sid in self.labels if sid not in placed]
        if others:
            groups.append(("Not in this GUI", others))

        defaults = set()
        wanted = DEFAULT_SIGNALS[self.source]
        for sid, sig in self.meta["signals"].items():
            if (sig["item"], sig["name"], sig["kind"]) in wanted:
                defaults.add(sid)
            if sig["item"] in LOG_BY_DEFAULT and sig["kind"] == "readout":
                self.log_y.add(sid)

        self.pick_vars = {}
        self.pick_order = []
        for name, sids in groups:
            if not sids:
                continue
            tk.Label(parent, text=name, font=("", 9, "bold"), anchor="w").pack(fill="x")
            for sid in sids:
                var = tk.IntVar(value=1 if sid in defaults else 0)
                self.pick_vars[sid] = var
                self.pick_order.append(sid)
                sig = self.meta["signals"][sid]
                text = sig["name"] + (" (set)" if sig["kind"] == "control" else "")
                tk.Checkbutton(parent, text=text, variable=var, anchor="w",
                               command=self.on_pick).pack(fill="x", padx=(10, 0))
        self.selected = [sid for sid in self.pick_order if self.pick_vars[sid].get()]

    # ----- view and range -----
    def show_last_hour(self):
        end = self.last_t
        self.set_view(max(run_at(self.runs, end)["first_t"], end - RAW_MAX_S), end)
        self.set_cursor(end)

    def remember(self, gesture=False):
        """Save the view for Backspace. A burst of wheel events counts as one step."""
        now = time.monotonic()
        if gesture and now - self.last_remembered < 0.7:
            self.last_remembered = now
            return
        self.last_remembered = now
        state = (list(self.view), dict(self.y_view))
        if not self.history or self.history[-1] != state:
            self.history.append(state)
            del self.history[:-HISTORY_MAX]

    def on_back(self):
        if self.history:
            view, y_view = self.history.pop()
            self.y_view = y_view
            self.set_view(*view)

    def on_home(self):
        self.remember()
        self.set_view(*self.range)

    def around_cursor(self, seconds):
        self.remember()
        self.set_view(self.cursor_t - seconds / 2.0, self.cursor_t + seconds / 2.0)

    def set_range(self, t0, t1):
        t0, t1 = max(t0, self.first_t), min(t1, self.last_t)
        if t1 - t0 < 1.0:
            self.status_var.set("No data in that range")
            return
        self.remember()
        self.range = [t0, t1]
        self.set_view(t0, t1)
        self.sync_slider()
        self.request_strip()

    def set_view(self, t0, t1):
        low, high = self.range
        span = min(max(t1 - t0, 5.0), max(high - low, 5.0))
        t0 = min(max(t0, low), high - span)
        self.view = [t0, t0 + span]
        self.from_var.set(to_local(self.view[0], "%Y-%m-%d %H:%M"))
        self.to_var.set(to_local(self.view[1], "%Y-%m-%d %H:%M"))
        self.on_view_changed()

    def on_view_changed(self):
        self.schedule_redraw()
        self.draw_strip_box()
        if self.settle_view_id is not None:
            self.root.after_cancel(self.settle_view_id)
        self.settle_view_id = self.root.after(120, self.request_window)

    def plot_box(self):
        width = max(self.canvas.winfo_width(), 400)
        height = max(self.canvas.winfo_height(), 200)
        return PLOT_LEFT, 20, width - PLOT_RIGHT, height - 24   # left, top, right, bottom

    def request_window(self):
        self.settle_view_id = None
        t0, t1 = self.view
        span = t1 - t0
        sids = tuple(self.selected)
        if not sids:
            return
        left, _top, right, _bottom = self.plot_box()
        columns = right - left
        if span <= RAW_MAX_S:
            self.waiting_for_overview = False
            if (self.loaded and self.loaded[0] == "raw" and self.loaded[1] == sids
                    and self.loaded[2] <= t0 and t1 <= self.loaded[3]):
                self.schedule_redraw()
                return
            job = ("raw", sids, t0 - span * 0.25, t1 + span * 0.25, columns)
        elif self.overview_ready:
            self.waiting_for_overview = False
            job = ("overview", sids, t0, t1, columns)
            if self.loaded == job:
                return
        else:
            self.waiting_for_overview = True
            self.schedule_redraw()
            if not self.overview_cancelled:
                self.start_overview()
            return
        self.status_var.set("Loading…")
        with self.lock:
            self.window_job = job
            self.window_gen += 1
        self.wake_window.set()

    def request_strip(self):
        if not self.overview_ready or not self.selected:
            self.draw_strip()
            return
        left, _top, right, _bottom = self.plot_box()
        key = (self.selected[0], self.range[0], self.range[1], right - left)
        if key == self.strip_key:
            return
        self.strip_key = key
        with self.lock:
            self.strip_job = key
        self.wake_window.set()

    def start_overview(self):
        if self.overview_thread is not None:
            return
        self.overview_cancel.clear()
        self.build_button.pack_forget()
        self.progress.pack(side="left", padx=4)
        self.cancel_button.pack(side="left")
        self.progress["value"] = 0
        self.status_var.set("Building the one-time overview…")

        def work():
            try:
                done = build_overview(self.path, self.meta, self.overview_file,
                                      lambda f: self.results.put(("progress", f)),
                                      self.overview_cancel)
                self.results.put(("overview", done, None))
            except (sqlite3.Error, OSError) as ex:
                self.results.put(("overview", False, str(ex)))
        self.overview_thread = threading.Thread(target=work, daemon=True)
        self.overview_thread.start()

    def on_cancel_overview(self):
        self.overview_cancel.set()

    def on_build_overview(self):
        self.overview_cancelled = False
        self.start_overview()

    def finish_overview(self, done, error):
        self.overview_thread = None
        self.progress.pack_forget()
        self.cancel_button.pack_forget()
        self.overview_ready = done
        if done:
            self.status_var.set("Overview ready")
            self.request_window()
            self.request_strip()
            return
        self.overview_cancelled = True
        self.build_button.pack(side="left", padx=4)
        self.status_var.set("Overview failed: " + error if error else "Overview cancelled")
        self.schedule_redraw()

    # ----- the shared cursor -----
    def set_cursor(self, t, follow=False):
        """Every control ends here. Lines and labels move now, the lab GUI follows."""
        self.cursor_t = min(max(t, self.first_t), self.last_t)
        if follow:
            self.keep_cursor_visible()
        self.show_cursor()
        self.schedule_lab()

    def keep_cursor_visible(self):
        if not self.range[0] <= self.cursor_t <= self.range[1]:
            self.set_range(self.first_t, self.last_t)
        if not self.view[0] <= self.cursor_t <= self.view[1]:
            span = self.view[1] - self.view[0]
            self.set_view(self.cursor_t - span * 0.2, self.cursor_t + span * 0.8)

    def show_cursor(self):
        """The live part. It stays out of the lab window on purpose: on a Mac any change
        there repaints the whole window, about 150 ms against 40 ms for the timeline."""
        self.draw_cursor()
        self.draw_strip_box()

    def show_cursor_in_lab(self):
        self.time_var.set(to_local(self.cursor_t))
        self.sync_slider()

    def sync_slider(self):
        self.slider_sync = True
        low, high = self.range
        self.slider.set(min(max((self.cursor_t - low) / max(high - low, 1.0), 0.0), 1.0))
        self.slider_sync = False

    def on_slider(self, value):
        if not self.slider_sync:
            low, high = self.range
            self.set_cursor(low + float(value) * (high - low), follow=True)
            self.time_var.set(to_local(self.cursor_t))     # the slider repaints anyway

    def schedule_lab(self):
        """Repaint the lab GUI SETTLE_MS after the cursor stops, or every PLAY_LAB_S
        while playing. Repainting it costs far more than moving a line."""
        if self.playing:
            if time.monotonic() - self.last_lab >= PLAY_LAB_S:
                self.request_lab()
            return
        if self.settle_id is not None:
            self.root.after_cancel(self.settle_id)
        self.settle_id = self.root.after(SETTLE_MS, self.request_lab)

    def request_lab(self):
        self.settle_id = None
        self.last_lab = time.monotonic()
        with self.lock:
            self.cursor_job = self.cursor_t
            self.chart_job = self.cursor_t
            self.step_job = 0
        self.wake_cursor.set()

    def request_chart(self):
        self.settle_id = None
        with self.lock:
            self.chart_job = self.cursor_t
        self.wake_cursor.set()

    def step(self, direction):
        """One logged cycle. Only the DB knows where that is, so it goes to the worker."""
        with self.lock:
            self.step_job += direction
        self.wake_cursor.set()

    def jump(self, seconds):
        self.set_cursor(self.cursor_t + seconds, follow=True)

    def apply_cycle(self, requested, cycle_id, ts, run_id, snapshot, stepped=False):
        self.shown_cycle = cycle_id
        in_gap = requested - ts > GAP_S
        moved_on = requested != self.cursor_t and not stepped   # newer than this result
        if not moved_on:
            self.cursor_t = requested if in_gap else ts
            if stepped:
                self.keep_cursor_visible()
            self.show_cursor()
        self.show_cursor_in_lab()
        inject(self.app, self.lab, self.slots, self.enabled_ids, {} if in_gap else snapshot,
               self.colours, self.base_colours)
        shown = to_local(requested if in_gap else ts)
        title = "HISTORY VIEWER: NOT LIVE: {} @ {}".format(self.db_name, shown)
        if in_gap:
            title += " (no data at this time)"
        self.root.title(title)
        self.banner.configure(text=title)
        self.banner_var.set(title)
        self.gap_var.set("no data at this time" if in_gap else "")
        self.run_var_lab.set("Run {}, cycle {}".format(run_id, cycle_id))
        self.info_var.set("Run {}, cycle {}".format(run_id, cycle_id))
        self.snapshot = {} if in_gap else snapshot
        self.snapshot_t = self.cursor_t
        self.draw_cursor()
        if stepped:
            if self.settle_id is not None:
                self.root.after_cancel(self.settle_id)
            self.settle_id = self.root.after(SETTLE_MS, self.request_chart)

    def apply_chart(self, cursor_t, data):
        """Fill the lab chart the way the live loop fills data_x and data_y, but around
        the cursor. Values stay as logged, like the live chart."""
        app = self.app
        self.chart_t = cursor_t
        lines = [[next((row[i] for i in ids if i in row), None) for _ts, row in data]
                 for ids in self.chart_sids]
        active = [line for line in lines if any(rec and rec[0] is not None for rec in line)]
        # Chart cannot draw a gap: one None or NaN crashes it. Cycles with a missing
        # value are left out; the timeline is the place that shows gaps.
        keep = [index for index in range(len(data))
                if all(line[index] and line[index][0] is not None for line in active)]
        app.data_x = [(data[index][0] - cursor_t) / 60.0 for index in keep]
        app.data_y = []
        app.data_bands = []
        for line in lines:
            if not any(rec and rec[0] is not None for rec in line):
                app.data_y.append([])       # nothing logged: same as a fresh live chart
                app.data_bands.append(([], []))
                continue
            recs = [line[index] for index in keep]
            app.data_y.append([rec[0] for rec in recs])
            if all(rec[1] is not None and rec[2] is not None for rec in recs):
                app.data_bands.append(([rec[1] for rec in recs], [rec[2] for rec in recs]))
            else:
                app.data_bands.append(([], []))
        if len(app.data_x) > 1:
            app.draw_chart(full=True)
        else:
            app.chart.clear()
            app.chart.inner_canvas.delete("hv_cursor")

    # ----- workers -----
    def cursor_worker(self):
        db = Db(self.path)
        last_cycle = None
        while not self.closing:
            self.wake_cursor.wait()
            self.wake_cursor.clear()
            while not self.closing:
                with self.lock:
                    target, steps, chart = self.cursor_job, self.step_job, self.chart_job
                    self.cursor_job, self.step_job = None, 0
                    if target is None and not steps:
                        self.chart_job = None
                if target is None and not steps and chart is None:
                    break
                try:
                    conn = db.connect()
                    if target is not None:
                        last_cycle, ts, run_id = locate_cycle(conn, self.runs, target)
                        self.results.put(("cycle", target, last_cycle, ts, run_id,
                                          read_cycle(conn, last_cycle), False))
                    elif steps:
                        if last_cycle is None:
                            last_cycle = locate_cycle(conn, self.runs, self.cursor_t)[0]
                        sql = ("SELECT id, ts_unix, run_id FROM cycle WHERE id{} ?"
                               " ORDER BY id{} LIMIT 1 OFFSET ?").format(
                                   ">" if steps > 0 else "<", "" if steps > 0 else " DESC")
                        row = conn.execute(sql, (last_cycle, abs(steps) - 1)).fetchone()
                        if row is None:
                            continue
                        last_cycle, ts, run_id = row
                        self.results.put(("cycle", ts, last_cycle, ts, run_id,
                                          read_cycle(conn, last_cycle), True))
                    else:
                        self.results.put(("chart", chart, self.read_chart(conn, chart)))
                except sqlite3.Error as ex:
                    self.results.put(("error", str(ex)))
                    db.close()

    def read_chart(self, conn, cursor_t):
        """Cycles of the cursor's run around it: [(ts, {sid: rec})]."""
        run = run_at(self.runs, cursor_t)
        half = CHART_SPAN_MIN * 60.0
        cycles = conn.execute(
            "SELECT id, ts_unix FROM cycle WHERE run_id=? AND ts_unix BETWEEN ? AND ?"
            " ORDER BY ts_unix", (run["id"], cursor_t - half, cursor_t + half)).fetchall()
        if not cycles:
            return []
        rows = {cycle_id: (ts, {}) for cycle_id, ts in cycles}
        wanted = sorted({sid for ids in self.chart_sids for sid in ids})
        sql = ("SELECT cycle_id, signal_id, value, band_min, band_max FROM measurement"
               " INDEXED BY idx_measurement_cycle WHERE cycle_id BETWEEN ? AND ?"
               " AND signal_id IN (" + ",".join(str(sid) for sid in wanted) + ")")
        low, high = min(rows), max(rows)
        for cycle_id, sid, value, band_min, band_max in conn.execute(sql, (low, high)):
            if cycle_id in rows:
                rows[cycle_id][1][sid] = (value, band_min, band_max)
        return [rows[cycle_id] for cycle_id, _ts in cycles]

    def window_worker(self):
        db = Db(self.path)
        while not self.closing:
            self.wake_window.wait()
            self.wake_window.clear()
            with self.lock:
                job, gen, strip = self.window_job, self.window_gen, self.strip_job
                self.window_job = self.strip_job = None
            try:
                if strip is not None:
                    sid, t0, t1, columns = strip
                    self.results.put(("strip", strip, read_overview(
                        self.overview_file, (sid,), t0, t1, columns, self.offsets)[sid]))
                if job is None:
                    continue
                kind, sids, t0, t1, columns = job
                if kind == "raw":
                    series = read_raw(db, self.meta, sids, t0, t1, self.offsets,
                                      lambda: gen != self.window_gen)
                else:
                    series = read_overview(self.overview_file, sids, t0, t1, columns, self.offsets)
                if series is not None:
                    self.results.put(("window", gen, job, series))
            except sqlite3.Error as ex:
                self.results.put(("error", str(ex)))
                db.close()

    def poll(self):
        """Collect worker results. Only the newest cycle is drawn, which is what keeps
        scrubbing smooth: the GUI skips cycles instead of queueing them."""
        latest_cycle = None
        try:
            while True:
                result = self.results.get_nowait()
                kind = result[0]
                if kind == "cycle":
                    latest_cycle = result
                elif kind == "chart":
                    self.apply_chart(result[1], result[2])
                elif kind == "window":
                    if result[1] == self.window_gen:
                        self.series = result[3]
                        self.loaded = result[2]
                        self.status_var.set("")
                        self.schedule_redraw()
                elif kind == "strip":
                    if result[1] == self.strip_key:
                        self.strip_series = result[2]
                        self.draw_strip()
                elif kind == "progress":
                    self.progress["value"] = result[1]
                elif kind == "overview":
                    self.finish_overview(result[1], result[2])
                elif kind == "error":
                    self.status_var.set("DB error: " + result[1])
        except queue.Empty:
            pass
        if latest_cycle is not None:
            self.apply_cycle(*latest_cycle[1:])
        if not self.closing:
            self.poll_id = self.root.after(POLL_MS, self.poll)

    # ----- drawing -----
    def schedule_redraw(self):
        if self.redraw_id is None:
            self.redraw_id = self.root.after_idle(self.redraw)

    def x_of(self, t):
        left, _top, right, _bottom = self.plot_box()
        return left + (t - self.view[0]) / (self.view[1] - self.view[0]) * (right - left)

    def t_of(self, x):
        left, _top, right, _bottom = self.plot_box()
        return self.view[0] + (x - left) / (right - left) * (self.view[1] - self.view[0])

    def redraw(self):
        self.redraw_id = None
        canvas = self.canvas
        canvas.delete("all")
        self.panels = []
        left, top, right, bottom = self.plot_box()
        count = len(self.selected)
        if count == 0:
            canvas.create_text((left + right) / 2, (top + bottom) / 2, fill=TEXT,
                               text="Pick signals on the left")
            return
        ticks = time_ticks(self.view[0], self.view[1], max((right - left) // 110, 2))
        for tick, _text in ticks:
            x = self.x_of(tick)
            canvas.create_line(x, top, x, bottom, fill=GRID)
        height = (bottom - top) / count
        for index, sid in enumerate(self.selected):
            self.draw_plot(sid, top + index * height, top + (index + 1) * height - 3, left, right)
        for tick, text in ticks:
            canvas.create_text(self.x_of(tick), bottom + 4, text=text, anchor="n", fill=AXIS)
        self.draw_markers(top, bottom)
        if self.waiting_for_overview:
            text = ("Windows over 1 hour need the per-minute overview."
                    if self.overview_cancelled else "Building the overview…")
            canvas.create_rectangle(left + 40, top + 30, right - 40, top + 62,
                                    fill="white", outline=AXIS)
            canvas.create_text((left + right) / 2, top + 46, text=text, fill=TEXT)
        self.draw_cursor()

    def visible(self, sid, columns):
        data = self.series.get(sid)
        if not data or not data[0]:
            return [], [], [], []
        ts = data[0]
        a = max(bisect.bisect_left(ts, self.view[0]) - 1, 0)
        b = min(bisect.bisect_right(ts, self.view[1]) + 1, len(ts))
        return rebin(ts[a:b], data[1][a:b], data[2][a:b], data[3][a:b],
                     self.view[0], self.view[1], columns)

    def auto_limits(self, lows, highs, log):
        values = [v for v in lows + highs if v == v and (not log or v > 0)]
        if not values:
            return None
        low, high = min(values), max(values)
        if log:
            low, high = math.log10(low), math.log10(high)
        pad = (high - low) * 0.06 or max(abs(high) * 0.05, 0.05)
        return low - pad, high + pad

    def draw_plot(self, sid, y0, y1, left, right):
        canvas = self.canvas
        log = sid in self.log_y
        canvas.create_rectangle(left, y0, right, y1, outline=GRID)
        canvas.create_text(4, y0 + 1, text=self.labels[sid], anchor="nw", fill=TEXT,
                           width=left - 56, font=("", 9))
        tag = "sid%d" % sid
        canvas.create_text(right + 5, y0 + 15, text="log" if log else "lin", anchor="nw",
                           fill=AXIS, font=("", 9), tags=("logtag", tag))
        canvas.create_text(right + 35, y0 + 15, text="fixed" if sid in self.y_view else "auto",
                           anchor="nw", fill=AXIS, font=("", 9), tags=("autotag", tag))
        ts, lows, mids, highs = self.visible(sid, right - left)
        automatic = self.auto_limits(lows, highs, log)
        limits = self.y_view.get(sid, automatic)
        panel = {"sid": sid, "y0": y0, "y1": y1, "limits": limits, "log": log}
        self.panels.append(panel)
        if limits is None:
            canvas.create_text((left + right) / 2, (y0 + y1) / 2, text="no data here", fill=GREY)
            return
        ymin, ymax = limits
        scale = (y1 - y0 - 2) / (ymax - ymin)

        def y_of(v):
            if log:
                v = math.log10(v) if v > 0 else ymin
            return y1 - 1 - (min(max(v, ymin), ymax) - ymin) * scale

        for value, anchor, y in ((ymax, "ne", y0 + 1), (ymin, "se", y1 - 1)):
            shown = 10 ** value if log else value
            canvas.create_text(left - 3, y, text="{:.4g}".format(shown), anchor=anchor,
                               fill=AXIS, font=("", 8))

        def flush(xs, los, his, ms):
            """One unbroken stretch: the band, then the line."""
            if len(xs) == 1:
                canvas.create_line(xs[0], his[0], xs[0], los[0] + 1, fill=INK, width=2)
                return
            if any(abs(a - b) >= 0.5 for a, b in zip(los, his)):
                outline = [c for x, y in zip(xs, his) for c in (x, y)]
                outline += [c for x, y in zip(reversed(xs), reversed(los)) for c in (x, y)]
                canvas.create_polygon(outline, fill=BAND, outline=BAND)
            canvas.create_line([c for x, y in zip(xs, ms) for c in (x, y)], fill=INK)

        xs, los, his, ms = [], [], [], []
        for t, low, mid, high in zip(ts, lows, mids, highs):
            if mid != mid or (log and mid <= 0):
                if xs:
                    flush(xs, los, his, ms)
                xs, los, his, ms = [], [], [], []
                continue
            xs.append(self.x_of(t))
            los.append(y_of(low))
            his.append(y_of(high))
            ms.append(y_of(mid))
        if xs:
            flush(xs, los, his, ms)

    def draw_markers(self, top, bottom):
        canvas = self.canvas
        self.hits = []
        lists = [(self.meta["notes"], True)]
        if self.show_events.get():
            lists.insert(0, (self.meta["events"], False))
        for marks, is_note in lists:
            used_columns = set()
            times = [mark[0] for mark in marks]
            a = bisect.bisect_left(times, self.view[0])
            b = bisect.bisect_right(times, self.view[1])
            for ts, text in marks[a:b]:
                x = self.x_of(ts)
                self.hits.append((x, text, is_note, ts))
                if int(x) in used_columns:
                    continue
                used_columns.add(int(x))
                if is_note:
                    canvas.create_line(x, top, x, bottom, fill=NOTE)
                    canvas.create_polygon(x - 5, top, x + 5, top, x, top + 8, fill=NOTE)
                else:
                    canvas.create_line(x, top, x, bottom, fill=EVENT, dash=(2, 3))

    def value_at_cursor(self, sid):
        """Text beside a plot. Exact once the cycle is loaded; while the cursor is moving
        it comes from what is already plotted, so no query is needed."""
        if self.snapshot_t == self.cursor_t:
            rec = self.snapshot.get(sid)
            if rec is None or rec[0] is None:
                return "—"
            return "{:.5g}".format(rec[0] + self.offsets.get(sid, 0.0))
        data = self.series.get(sid)
        if not data or not data[0]:
            return "—"
        index = bisect.bisect_right(data[0], self.cursor_t) - 1
        if index < 0 or data[2][index] != data[2][index]:
            return "—"
        return "{:.5g}".format(data[2][index])

    def draw_cursor(self):
        canvas = self.canvas
        left, top, right, bottom = self.plot_box()
        canvas.delete("cursor")
        for panel in self.panels:
            canvas.create_text(right + 5, panel["y0"] + 1, text=self.value_at_cursor(panel["sid"]),
                               anchor="nw", fill=TEXT, font=("", 10, "bold"), tags="cursor")
        if self.view[0] <= self.cursor_t <= self.view[1]:
            x = self.x_of(self.cursor_t)
            canvas.create_line(x, top, x, bottom, fill=CURSOR, width=2, tags="cursor")
            near_right = x > (left + right) / 2
            canvas.create_text(x + (-5 if near_right else 5), 3, text=to_local(self.cursor_t),
                               anchor="ne" if near_right else "nw", fill=CURSOR,
                               font=("", 10, "bold"), tags="cursor")

    # ----- overview strip -----
    def strip_x(self, t):
        left, _top, right, _bottom = self.plot_box()
        low, high = self.range
        return left + (t - low) / max(high - low, 1.0) * (right - left)

    def strip_t(self, x):
        left, _top, right, _bottom = self.plot_box()
        low, high = self.range
        return low + (x - left) / (right - left) * (high - low)

    def draw_strip(self):
        strip = self.strip
        strip.delete("all")
        left, _top, right, _bottom = self.plot_box()
        strip.create_rectangle(left, 1, right, STRIP_H - 2, outline=GRID)
        for run in self.runs:       # always there, even before the overview exists
            if run["last_t"] >= self.range[0] and run["first_t"] <= self.range[1]:
                strip.create_rectangle(max(self.strip_x(run["first_t"]), left), STRIP_H - 6,
                                       min(self.strip_x(run["last_t"]), right), STRIP_H - 3,
                                       fill=GRID, outline="")
        data = self.strip_series
        if data and data[0]:
            values = [v for v in data[1] + data[3] if v == v]
            low, high = (min(values), max(values)) if values else (0.0, 1.0)
            scale = (STRIP_H - 12) / ((high - low) or 1.0)
            xs, tops, bottoms = [], [], []

            def flush():
                if len(xs) > 1:
                    outline = [c for x, y in zip(xs, tops) for c in (x, y)]
                    outline += [c for x, y in zip(reversed(xs), reversed(bottoms)) for c in (x, y)]
                    strip.create_polygon(outline, fill=BAND, outline=INK)
                xs.clear()
                tops.clear()
                bottoms.clear()

            for t, lo, value, hi in zip(data[0], data[1], data[2], data[3]):
                if value != value:
                    flush()
                    continue
                xs.append(self.strip_x(t))
                tops.append(STRIP_H - 7 - (hi - low) * scale)
                bottoms.append(STRIP_H - 7 - (lo - low) * scale)
            flush()
        name = self.labels.get(self.selected[0], "") if self.selected else ""
        strip.create_text(4, 2, text="Selected range\n" + name, anchor="nw", fill=AXIS,
                          width=PLOT_LEFT - 10, font=("", 8))
        self.draw_strip_box()

    def draw_strip_box(self):
        strip = self.strip
        strip.delete("box")
        x0, x1 = self.strip_x(self.view[0]), self.strip_x(self.view[1])
        strip.create_rectangle(x0, 1, max(x1, x0 + 2), STRIP_H - 2, outline=INK, width=2, tags="box")
        x = self.strip_x(self.cursor_t)
        strip.create_line(x, 1, x, STRIP_H - 2, fill=CURSOR, tags="box")

    def on_strip_press(self, event):
        x0, x1 = self.strip_x(self.view[0]), self.strip_x(self.view[1])
        self.remember()
        if abs(event.x - x0) <= 5:
            mode = "left"
        elif abs(event.x - x1) <= 5:
            mode = "right"
        elif x0 < event.x < x1:
            mode = "move"
        else:           # click outside the box: jump there
            span = self.view[1] - self.view[0]
            target = self.strip_t(event.x)
            self.set_view(target - span / 2.0, target + span / 2.0)
            mode = "move"
        self.strip_drag = {"mode": mode, "x": event.x, "view": list(self.view)}

    def on_strip_drag(self, event):
        drag = self.strip_drag
        if not drag:
            return
        v0, v1 = drag["view"]
        shift = self.strip_t(event.x) - self.strip_t(drag["x"])
        if drag["mode"] == "move":
            self.set_view(v0 + shift, v1 + shift)
        elif drag["mode"] == "left":     # clamp here: set_view would shift the other edge
            self.set_view(max(min(v0 + shift, v1 - 5.0), self.range[0]), v1)
        else:
            self.set_view(v0, min(max(v1 + shift, v0 + 5.0), self.range[1]))

    def on_strip_release(self, _event):
        self.strip_drag = None

    # ----- mouse and keys on the plots -----
    def zoom(self, x, factor):
        """Zoom X only, around pixel x."""
        pivot = self.t_of(x)
        self.set_view(pivot - (pivot - self.view[0]) * factor,
                      pivot + (self.view[1] - pivot) * factor)

    def panel_at(self, y):
        return next((p for p in self.panels if p["y0"] <= y <= p["y1"] + 3), None)

    def zoom_y(self, panel, y, factor):
        """Zoom Y of one plot only, around pixel y."""
        if panel["limits"] is None:
            return
        ymin, ymax = panel["limits"]
        pivot = ymax - (y - panel["y0"]) / (panel["y1"] - panel["y0"]) * (ymax - ymin)
        self.set_y(panel, pivot - (pivot - ymin) * factor, pivot + (ymax - pivot) * factor)

    def set_y(self, panel, ymin, ymax):
        if ymax - ymin > 1e-12:
            self.y_view[panel["sid"]] = (ymin, ymax)
            panel["limits"] = (ymin, ymax)
            self.schedule_redraw()

    def on_wheel(self, event):
        units = wheel_units(event)
        if event.state & (STATE_CONTROL | STATE_COMMAND):
            panel = self.panel_at(event.y)
            if panel:
                self.remember(gesture=True)
                self.zoom_y(panel, event.y, 0.85 ** units)
            return
        self.remember(gesture=True)
        if event.state & STATE_SHIFT:
            span = self.view[1] - self.view[0]
            self.set_view(self.view[0] - units * span * 0.05, self.view[1] - units * span * 0.05)
        else:
            self.zoom(event.x, 0.85 ** units)

    def tag_at(self, x, y):
        for item in self.canvas.find_overlapping(x, y, x, y):
            tags = self.canvas.gettags(item)
            for name in ("logtag", "autotag"):
                if name in tags:
                    return name, int(next(tag for tag in tags if tag.startswith("sid"))[3:])
        return None, None

    def on_press(self, event):
        self.canvas.focus_set()
        left, _top, _right, bottom = self.plot_box()
        name, sid = self.tag_at(event.x, event.y)
        if name == "logtag":
            self.log_y.symmetric_difference_update({sid})
            self.y_view.pop(sid, None)      # limits are stored per scale
            self.schedule_redraw()
            return
        if name == "autotag":
            panel = next(p for p in self.panels if p["sid"] == sid)
            if sid in self.y_view:
                del self.y_view[sid]
            elif panel["limits"]:
                self.y_view[sid] = panel["limits"]
            self.schedule_redraw()
            return
        if event.state & STATE_SHIFT:
            self.on_box_press(event)
            return
        panel = self.panel_at(event.y)
        if event.y > bottom:
            mode = "xaxis"
        elif event.x < left:
            mode = "yaxis" if panel else None
        elif abs(self.x_of(self.cursor_t) - event.x) <= 6:
            mode = "cursor"
        else:
            mode = "pan"
        if mode in ("pan", "xaxis", "yaxis"):
            self.remember()
        self.drag = {"mode": mode, "x": event.x, "y": event.y, "view": list(self.view),
                     "panel": panel, "limits": panel["limits"] if panel else None,
                     "moved": False}

    def on_box_press(self, event):
        self.drag = {"mode": "box", "x": event.x, "y": event.y, "panel": self.panel_at(event.y),
                     "moved": False}

    def on_drag(self, event):
        drag = self.drag
        if not drag or not drag["mode"]:
            return
        dx, dy = event.x - drag["x"], event.y - drag["y"]
        if abs(dx) + abs(dy) > 3:
            drag["moved"] = True
        if not drag["moved"]:
            return
        mode = drag["mode"]
        if mode == "cursor":
            self.set_cursor(self.t_of(event.x))
        elif mode == "pan":
            v0, v1 = drag["view"]
            left, _top, right, _bottom = self.plot_box()
            shift = -dx / (right - left) * (v1 - v0)
            self.set_view(v0 + shift, v1 + shift)
        elif mode == "xaxis":
            v0, v1 = drag["view"]
            pivot = self.t_of(drag["x"])
            factor = math.exp(-dx / 150.0)
            self.view = list(drag["view"])
            self.set_view(pivot - (pivot - v0) * factor, pivot + (v1 - pivot) * factor)
        elif mode == "yaxis":
            panel, limits = drag["panel"], drag["limits"]
            if limits:
                ymin, ymax = limits
                shift = dy / (panel["y1"] - panel["y0"]) * (ymax - ymin)
                factor = math.exp(-dx / 80.0)
                middle = (ymin + ymax) / 2.0 + shift
                half = (ymax - ymin) / 2.0 * factor
                self.set_y(panel, middle - half, middle + half)
        elif mode == "box":
            self.canvas.delete("boxzoom")
            self.canvas.create_rectangle(drag["x"], drag["y"], event.x, event.y, outline=INK,
                                         dash=(3, 2), tags="boxzoom")

    def on_release(self, event):
        drag, self.drag = self.drag, None
        if not drag or not drag["mode"]:
            return
        self.canvas.delete("boxzoom")
        if drag["mode"] == "box":
            if drag["moved"] and abs(event.x - drag["x"]) >= 5:
                self.apply_box(drag, event)
            return
        if drag["moved"] or drag["mode"] not in ("pan", "cursor"):
            return
        near = [hit for hit in self.hits if abs(hit[0] - event.x) <= 5]
        if near:        # a click on a marker reads it and takes the cursor there
            hit = min(near, key=lambda h: (not h[2], abs(h[0] - event.x)))
            self.info_var.set(to_local(hit[3], "%d %b %H:%M:%S  ") + hit[1])
            self.set_cursor(hit[3])
        else:
            self.set_cursor(self.t_of(event.x))

    def apply_box(self, drag, event):
        self.remember()
        panel = drag["panel"]
        if panel and panel["limits"] and abs(event.y - drag["y"]) >= 5:
            ymin, ymax = panel["limits"]
            height = panel["y1"] - panel["y0"]
            values = [ymax - (min(max(y, panel["y0"]), panel["y1"]) - panel["y0"]) / height
                      * (ymax - ymin) for y in (drag["y"], event.y)]
            self.set_y(panel, min(values), max(values))
        t0, t1 = sorted((self.t_of(drag["x"]), self.t_of(event.x)))
        self.set_view(t0, t1)

    def on_double(self, event):
        self.drag = None
        panel = self.panel_at(event.y)
        if event.x < self.plot_box()[0] and panel:
            self.y_view.pop(panel["sid"], None)     # double-click the y-axis: back to auto
            self.schedule_redraw()

    def on_hover(self, event):
        self.canvas.delete("tip")
        near = [hit for hit in self.hits if abs(hit[0] - event.x) <= 5]
        if not near:
            return
        hit = min(near, key=lambda h: (not h[2], abs(h[0] - event.x)))
        anchor = "ne" if event.x > self.canvas.winfo_width() / 2 else "nw"
        text = self.canvas.create_text(event.x + (-8 if anchor == "ne" else 8), event.y + 10,
                                       text=to_local(hit[3], "%d %b %H:%M:%S  ") + hit[1],
                                       anchor=anchor, width=420, fill=TEXT, tags="tip")
        box = self.canvas.bbox(text)
        self.canvas.tag_lower(self.canvas.create_rectangle(
            box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3, fill="white", outline=AXIS,
            tags="tip"), text)

    def typing(self, event):
        """True in the From/To fields, where the keys edit text."""
        return isinstance(event.widget, tk.Entry) and str(event.widget.cget("state")) == "normal"

    def on_arrow(self, event, direction, seconds=None):
        if self.typing(event):
            return
        if seconds is not None:
            self.jump(direction * seconds)
        else:
            self.step(direction)

    # ----- panel commands -----
    def on_load(self):
        try:
            t0, t1 = parse_local(self.from_var.get()), parse_local(self.to_var.get())
        except ValueError:
            self.status_var.set("Use YYYY-MM-DD HH:MM")
            return
        if t1 <= t0:
            self.status_var.set("To must be after From")
            return
        self.set_range(t0, t1)
        if not self.range[0] <= self.cursor_t <= self.range[1]:
            self.set_cursor(self.range[0])

    def on_day(self):
        try:
            day = parse_local(self.from_var.get().strip()[:10] + " 00:00")
        except ValueError:
            self.status_var.set("Use YYYY-MM-DD HH:MM")
            return
        start = datetime.datetime.fromtimestamp(day)
        self.set_range(day, (start + datetime.timedelta(days=1)).timestamp())

    def on_whole(self):
        self.set_range(self.first_t, self.last_t)

    def on_run(self, _event):
        run = self.runs[self.run_box.current()]
        self.set_range(run["first_t"], run["last_t"])
        self.set_cursor(run["first_t"])

    def on_pick(self):
        self.selected = [sid for sid in self.pick_order if self.pick_vars[sid].get()]
        self.on_view_changed()
        self.request_strip()

    def on_note_pick(self, _event):
        chosen = self.note_list.curselection()
        if chosen and self.meta["notes"]:
            self.set_cursor(self.meta["notes"][chosen[0]][0], follow=True)

    def on_play(self):
        self.playing = not self.playing
        self.play_text.set("⏸ Pause" if self.playing else "▶ Play")
        if self.playing:
            self.play_tick()
        else:
            if self.play_id is not None:
                self.root.after_cancel(self.play_id)
                self.play_id = None
            self.request_lab()

    def play_tick(self):
        speed = float(self.speed_var.get().lstrip("×"))
        if self.cursor_t >= self.last_t:
            self.on_play()
            return
        target = self.cursor_t + PLAY_TICK_S * speed
        run = run_at(self.runs, self.cursor_t)
        if target > run["last_t"]:      # do not sit through the night between two runs
            later = [r["first_t"] for r in self.runs if r["first_t"] > run["last_t"]]
            target = min(later) if later else self.last_t
        self.set_cursor(target, follow=True)
        self.play_id = self.root.after(int(PLAY_TICK_S * 1000), self.play_tick)

    def close(self):
        """Ends the viewer. S1S2.on_destroy is a no-op here, so nothing but windows closes."""
        self.closing = True
        self.overview_cancel.set()
        self.wake_cursor.set()
        self.wake_window.set()
        for after_id in (self.poll_id, self.settle_id, self.settle_view_id, self.play_id):
            if after_id is not None:
                self.root.after_cancel(after_id)
        if self.redraw_id is not None:
            self.root.after_cancel(self.redraw_id)
        self.root.destroy()


def build_lab_frame(root):
    """Time strip, banner, and the scrollable area that holds the lab GUI."""
    strip = tk.Frame(root, padx=6, pady=3)
    strip.pack(fill="x")
    banner = tk.Label(root, bg="#b00020", fg="white", font=("", 11, "bold"), anchor="w", padx=8)
    banner.pack(fill="x")
    area = tk.Frame(root)
    area.pack(fill="both", expand=True)
    canvas = tk.Canvas(area, highlightthickness=0)
    bar_y = tk.Scrollbar(area, orient="vertical", command=canvas.yview)
    bar_x = tk.Scrollbar(area, orient="horizontal", command=canvas.xview)
    canvas.configure(xscrollcommand=bar_x.set, yscrollcommand=bar_y.set)
    bar_y.pack(side="right", fill="y")
    bar_x.pack(side="bottom", fill="x")
    canvas.pack(side="left", fill="both", expand=True)
    host = LabHost(canvas)
    window = canvas.create_window(0, 0, window=host, anchor="nw")
    return types.SimpleNamespace(strip=strip, banner=banner, canvas=canvas, host=host,
                                 window=window)


def open_viewer(path, root):
    """Everything between choosing a DB and the mainloop. Returns the Viewer."""
    outcome = {}

    def read():
        try:
            outcome["meta"] = load_meta(path)
        except (sqlite3.Error, ValueError, OSError) as ex:
            outcome["error"] = ex
    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    while worker.is_alive():
        root.update()
        time.sleep(0.01)
    if "error" in outcome:
        raise ValueError(str(outcome["error"]))
    meta = outcome["meta"]
    source = gui_for(meta, path)

    # sqlite3 releases the GIL on every row, and at the default 5 ms a busy Tk thread
    # would stretch reading one cycle (about 95 rows) to hundreds of ms.
    sys.setswitchinterval(0.0005)

    lab = load_lab(source)
    # sized to the screen, never larger; the lab GUI scrolls inside
    root.geometry("{}x{}+0+0".format(min(LAB_MAX_W, root.winfo_screenwidth() - 20),
                                     root.winfo_screenheight() - 90))
    root.deiconify()
    frame = build_lab_frame(root)
    app = build_app(lab, frame.host, source)
    root.update()
    make_read_only(app, lab)
    return Viewer(root, path, meta, source, app, lab, frame)


def default_log_dir():
    try:
        with open(os.path.join(HERE, "duo_logging_config.json"), encoding="utf-8") as f:
            base = os.path.expanduser(str(json.load(f)["base_dir"]))
        if os.path.isdir(base):
            return base
    except (OSError, ValueError, KeyError):
        pass
    return DEFAULT_LOG_DIR if os.path.isdir(DEFAULT_LOG_DIR) else HERE


def main():
    parser = argparse.ArgumentParser(description="Replay logged duoplasmatron data. Not live.")
    parser.add_argument("--db", help="log database; a file dialog opens without it")
    path = parser.parse_args().db

    install_guards()
    with contextlib.suppress(OSError):
        os.nice(10)         # the live GUI may run on this Pi; it goes first

    root = tk.Tk()
    root.withdraw()
    root.title("HISTORY VIEWER: NOT LIVE")
    if not path:
        path = filedialog.askopenfilename(
            title="Open a log database", initialdir=default_log_dir(),
            filetypes=(("Log databases", "*.db *.backup"), ("All files", "*")))
        if not path:
            return 0
    path = os.path.abspath(path)
    try:
        open_viewer(path, root)
    except (ValueError, OSError) as ex:
        messagebox.showerror("History viewer", str(ex))
        print("Could not open:", ex, file=sys.__stderr__)
        return 1
    root.mainloop()
    print("History viewer closed. Blocked attempts:", len(BLOCKED), file=sys.__stderr__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
