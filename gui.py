from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics import Color, Rectangle
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.core.window import Window
from collections import defaultdict
from datetime import datetime
import csv

from shared_queue import capture_queue

def format_lifespan(seconds):
    try:
        s = int(round(seconds))
        d = s // 86400
        h = (s % 86400) // 3600
        m = (s % 3600) // 60
        s = s % 60
        if d > 0:
            return f"{d}d {h:02d}:{m:02d}:{s:02d}"
        return f"{h:02d}:{m:02d}:{s:02d}"
    except:
        return "N/A"

def convert_id(id_str):
    """
    Show decimal & hex if numeric. No "Converted:" label => just lines.
    """
    if id_str.isdigit():
        try:
            hx = hex(int(id_str))
            return f"Decimal: {id_str}\nHex: {hx}"
        except:
            return id_str
    elif id_str.startswith("0x"):
        try:
            dec = str(int(id_str, 16))
            return f"Hex: {id_str}\nDecimal: {dec}"
        except:
            return id_str
    else:
        # check raw hex
        vv = id_str.lower()
        if len(vv) >= 6 and all(c in "0123456789abcdef" for c in vv):
            try:
                dec = str(int(vv, 16))
                return f"Hex: {id_str}\nDecimal: {dec}"
            except:
                return id_str
        return id_str

class UEConnectedRow(BoxLayout):
    def __init__(self, data, columns, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 40
        self.padding = (5, 2, 5, 2)
        self.spacing = 5
        with self.canvas.before:
            Color(0, 0, 0, 0)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        for col in columns:
            val = data.get(col.lower().replace(" ", "_"), "")
            text_val = str(val if val is not None else "")
            lbl = Label(
                text=text_val,
                color=(1, 1, 1, 1),
                halign='left',  # Ensure left alignment
                valign='middle'
            )
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            self.add_widget(lbl)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

class TableRow(ButtonBehavior, BoxLayout):
    def __init__(
        self,
        id_type,
        identifier,
        info,
        lifespan_str,
        show_details_callback,
        selection_mode_ref,
        track_mode_ref,
        selected_ids_ref,
        col_keys,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 35
        self.padding = (5, 0, 5, 0)

        self.id_type = id_type
        self.identifier = identifier
        self.info = info
        self.lifespan_str = lifespan_str
        self.show_details_callback = show_details_callback
        self.selection_mode_ref = selection_mode_ref
        self.track_mode_ref = track_mode_ref
        self.selected_ids_ref = selected_ids_ref
        self.col_keys = col_keys

        with self.canvas.before:
            self.bg_color = Color(0, 0, 0, 0)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        row_vals = self._make_values()
        for val in row_vals:
            text_val = str(val if val is not None else "")
            lbl = Label(
                text=text_val,
                color=(1, 1, 1, 1),
                halign='left',  # consistent left alignment
                valign='middle'
            )
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            self.add_widget(lbl)

        if (self.id_type, self.identifier) in self.selected_ids_ref:
            self.bg_color.rgba = (0, 0.5, 1, 0.3)

    def _make_values(self):
        vals = []
        for k in self.col_keys:
            if k == "id_type":
                raw = self.id_type
            elif k == "identifier":
                raw = self.identifier
            elif k == "count":
                raw = self.info["count"]
            elif k == "last_seen":
                ls = self.info["last_seen"]
                if ls and len(ls) >= 19:
                    raw = ls[11:19]  # HH:MM:SS
                else:
                    raw = ls or ""
            elif k == "lifespan":
                raw = self.lifespan_str
            elif k == "tracking_area_code":
                raw = self.info.get("tracking_area_code", "")
            elif k == "cell_identity":
                raw = self.info.get("cell_identity", "")
            elif k == "active":
                raw = self._compute_active()
            else:
                raw = ""
            if raw is None:
                raw = ""
            vals.append(raw)
        return vals

    def _compute_active(self):
        ls = self.info["last_seen"]
        if not ls:
            return "N/A"
        try:
            now = datetime.now()
            dt2 = datetime.strptime(ls, "%Y-%m-%d %H:%M:%S")
            diff = (now - dt2).total_seconds()
            if diff < 3600:
                return "<1h"
            hrs = int(diff // 3600)
            if hrs >= 24:
                return f"{hrs // 24}d {hrs % 24}h"
            return f"{hrs}h"
        except:
            return "N/A"

    def on_release(self):
        key = (self.id_type, self.identifier)
        if self.selection_mode_ref():
            if key in self.selected_ids_ref:
                self.selected_ids_ref.remove(key)
                self.bg_color.rgba = (0, 0, 0, 0)
            else:
                self.selected_ids_ref.add(key)
                self.bg_color.rgba = (0, 0.5, 1, 0.3)
        else:
            if self.show_details_callback:
                self.show_details_callback(self.id_type, self.identifier, self.info, self.lifespan_str)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

class TestPanel(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = 0
        self.padding = (10, 10, 10, 0)
        with self.canvas.before:
            Color(0.105, 0.168, 0.247, 1)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # 6 tests + 2 placeholders
        self.tests = [
            {
                "name": "ID frequently updated",
                "description": "Fail if any m-TMSI lifespan>2h.",
                "result": "Pending",
                "info": ""
            },
            {
                "name": "No IMSI sent in Paging",
                "description": "Fail if IMSI found in paging.",
                "result": "Pending",
                "info": ""
            },
            {
                "name": "No IMSI in Attach/Reg",
                "description": "Fail if IMSI used in attach/reg or identity resp.",
                "result": "Pending",
                "info": ""
            },
            {
                "name": "Only SUCI/GUTI sent",
                "description": "Fail if non-SUCI/GUTI in paging.",
                "result": "Pending",
                "info": ""
            },
            {
                "name": "No IMEISV seen",
                "description": "Fail if any IMEISV is found at all.",
                "result": "Pending",
                "info": ""
            },
            {
                "name": "No IMSI in Identity Response",
                "description": "Fail if IMSI is found in Identity Response message.",
                "result": "Pending",
                "info": ""
            }
        ]
        for i in range(6, 8):
            self.tests.append({
                "name": f"Test {i + 1}",
                "description": "Not implemented.",
                "result": "Pending",
                "info": ""
            })
        self.test_rows = []
        for tdef in self.tests:
            row = self._build_test_row(tdef)
            self.add_widget(row)
            self.add_widget(BoxLayout(size_hint_y=None, height=1))

        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))
        self.bind(children=self._update_min_height)

    def _build_test_row(self, tdef):
        row = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=5, padding=(5, 0, 20, 0))
        name_lbl = Label(text=tdef["name"], size_hint_x=0.5, color=(1, 1, 1, 1))
        result_layout = BoxLayout(orientation='horizontal', size_hint_x=0.5, spacing=5)
        result_lbl = Label(text="Pending", size_hint_x=0.7, color=(1, 1, 0, 1))
        more_btn = Button(
            text="More Info",
            size_hint_x=0.3,
            font_size=12,
            background_normal='',
            background_color=(0.2, 0.3, 0.4, 1),
            color=(1, 1, 1, 1)
        )
        def on_more(_):
            self.show_more_info(tdef)
        more_btn.bind(on_release=on_more)
        result_layout.add_widget(result_lbl)
        result_layout.add_widget(more_btn)
        row.add_widget(name_lbl)
        row.add_widget(result_layout)
        self.test_rows.append({
            "row": row,
            "test": tdef,
            "result_label": result_lbl,
            "more_btn": more_btn
        })
        return row

    def _update_min_height(self, *args):
        self.do_layout()

    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def show_more_info(self, test):
        popup = Popup(
            title=f"{test['name']} Details",
            content=Label(text=test["info"], color=(1, 1, 1, 1)),
            size_hint=(0.6, 0.4)
        )
        popup.open()

    def update_tests(self, ids_dict):
        from datetime import datetime
        #1 => ID frequently updated => fail if m-TMSI>2h
        failing_mt = []
        for ((filt, ident), info) in ids_dict.items():
            if info["display_type"] == "m-TMSI" and info["first_seen"] and info["last_seen"]:
                try:
                    t1 = datetime.strptime(info["first_seen"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(info["last_seen"], "%Y-%m-%d %H:%M:%S")
                    life = (t2 - t1).total_seconds()
                    if life < 0:
                        life += 86400
                    if life > 7200:
                        failing_mt.append(ident)
                except:
                    pass
        if failing_mt:
            self.tests[0]["result"] = "Fail"
            show3 = failing_mt[:3]
            self.tests[0]["info"] = "Failing m-TMSI:\n" + "\n".join(show3) + f"\nTotal= {len(failing_mt)}"
        else:
            any_mt = any(info["display_type"] == "m-TMSI" for (_,_), info in ids_dict.items())
            if any_mt:
                self.tests[0]["result"] = "Pass"
                self.tests[0]["info"] = "No m-TMSI>2h"
            else:
                self.tests[0]["result"] = "Pending"
                self.tests[0]["info"] = "No m-TMSI data yet"

        #2 => no IMSI in paging
        paging_imsi = []
        for ((filt, ident), info) in ids_dict.items():
            if info["display_type"] == "IMSI" and ("Paging" in info["sources"]):
                paging_imsi.append(ident)
        if paging_imsi:
            self.tests[1]["result"] = "Fail"
            self.tests[1]["info"] = "IMSI in Paging:\n" + "\n".join(paging_imsi)
        else:
            self.tests[1]["result"] = "Pass"
            self.tests[1]["info"] = "No IMSI found in Paging."

        #3 => no IMSI in attach/reg
        attach_imsi = []
        for ((filt, ident), info) in ids_dict.items():
            if info["display_type"] == "IMSI":
                for src in info["sources"]:
                    s_low = src.lower()
                    if ("attach" in s_low) or ("registration" in s_low) or ("identity response" in s_low):
                        attach_imsi.append(ident)
                        break
        if attach_imsi:
            self.tests[2]["result"] = "Fail"
            self.tests[2]["info"] = "IMSI used:\n" + "\n".join(attach_imsi)
        else:
            self.tests[2]["result"] = "Pass"
            self.tests[2]["info"] = "No IMSI found in Attach/Reg"

        #4 => only SUCI/GUTI => fail if we see other ID in paging
        non_target = []
        for ((filt, ident), info) in ids_dict.items():
            if "Paging" in info["sources"]:
                dt = info["display_type"]
                if dt not in ("m-TMSI", "5G-TMSI", "SUCI", "GUTI"):
                    non_target.append(f"{dt}:{ident}")
        if ids_dict:
            if non_target:
                self.tests[3]["result"] = "Fail"
                self.tests[3]["info"] = "Non-SUCI/GUTI in paging:\n" + "\n".join(non_target)
            else:
                self.tests[3]["result"] = "Pass"
                self.tests[3]["info"] = "All SUCI/GUTI in paging"
        else:
            self.tests[3]["result"] = "Pending"
            self.tests[3]["info"] = "No paging events."

        #5 => no IMEISV => fail if any IMEISV found
        imeisv_ids = []
        for ((filt, ident), info) in ids_dict.items():
            if info["display_type"] == "IMEISV":
                imeisv_ids.append(ident)
        if imeisv_ids:
            self.tests[4]["result"] = "Fail"
            self.tests[4]["info"] = "IMEISV found:\n" + "\n".join(imeisv_ids)
        else:
            self.tests[4]["result"] = "Pass"
            self.tests[4]["info"] = "No IMEISV found."

        #6 => No IMSI in Identity Response => fail if IMSI + "Identity Response"
        identity_imsi = []
        for ((filt, ident), info) in ids_dict.items():
            if info["display_type"] == "IMSI":
                for src in info["sources"]:
                    if "identity response" in src.lower():
                        identity_imsi.append(ident)
                        break
        if identity_imsi:
            self.tests[5]["result"] = "Fail"
            self.tests[5]["info"] = "IMSI in Identity Response:\n" + "\n".join(identity_imsi)
        else:
            self.tests[5]["result"] = "Pass"
            self.tests[5]["info"] = "No IMSI in Identity Response."

        #7..8 => pending
        for i in range(6, 8):
            self.tests[i]["result"] = "Pending"
            self.tests[i]["info"] = ""

        # update row colors
        for idx, td in enumerate(self.test_rows):
            st = self.tests[idx]["result"]
            td["result_label"].text = st
            c = (1, 1, 1, 1)
            if st == "Pass":
                c = (0, 1, 0, 1)
            elif st == "Fail":
                c = (1, 0, 0, 1)
            elif st == "Pending":
                c = (1, 1, 0, 1)
            td["result_label"].color = c
            td["more_btn"].disabled = False
            td["more_btn"].opacity = 1.0

class IdentifierDisplayMain(TabbedPanel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0.2, 0.3, 0.4, 1)
        self.do_default_tab = False
        self.tab_height = 40
        self.tab_pos = 'top_left'
        self.tab_width = 120

        # store keyed by (filter_type, identifier)
        self.ids_dict = defaultdict(lambda: {
            "count": 0,
            "first_seen": None,
            "last_seen": None,
            "tracking_area_code": None,
            "cell_identity": None,
            "mcc": None,
            "mnc": None,
            "sources": set(),
            "display_type": "",
            "mme_group_id": "",
            "mme_code": ""
        })
        self.ue_events = []
        self.selection_mode = False
        self.track_mode = False
        self.selected_ids = set()
        self.sort_column = "last_seen"
        self.sort_ascending = True
        self.show_all = False

        self._build_ue_tab()
        self._build_tests_tab()
        self._build_details_tab()

    def _build_ue_tab(self):
        self.ue_tab = TabbedPanelItem(text="UE connected")
        cont = BoxLayout(orientation='vertical', spacing=2, padding=2)
        with cont.canvas.before:
            Color(0.105, 0.168, 0.247, 1)
            self.ue_bg = Rectangle(pos=cont.pos, size=cont.size)
        cont.bind(pos=self._update_ue_bg, size=self._update_ue_bg)

        self.ue_header = BoxLayout(orientation='horizontal', size_hint_y=None, height=30, padding=(5, 0, 5, 0))
        self.ue_columns = [
            "Timestamp", "ID Type", "ID", "Packet Info", "TAC",
            "CID", "MCC", "MNC", "MME Group ID", "MME Code"
        ]
        for col in self.ue_columns:
            lbl = Label(
                text=col,
                color=(1, 1, 1, 1),
                halign='left',   # left align
                valign='middle'
            )
            lbl.bind(size=lambda w, _: setattr(w, 'text_size', w.size))
            self.ue_header.add_widget(lbl)
        cont.add_widget(self.ue_header)

        self.ue_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=True,
            do_scroll_y=True,
            bar_width=20,
            scroll_type=['bars']
        )
        self.ue_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=1)
        self.ue_box.bind(minimum_height=self.ue_box.setter('height'))
        self.ue_scroll.add_widget(self.ue_box)
        cont.add_widget(self.ue_scroll)

        self.ue_tab.add_widget(cont)
        self.add_widget(self.ue_tab)

    def _update_ue_bg(self, layout, _):
        self.ue_bg.pos = layout.pos
        self.ue_bg.size = layout.size

    def _refresh_ue_table(self):
        self.ue_box.clear_widgets()
        for ev in self.ue_events:
            row = UEConnectedRow(ev, self.ue_columns)
            self.ue_box.add_widget(row)
            self.ue_box.add_widget(BoxLayout(size_hint_y=None, height=1))

    def update_ue_info(self, data):
        self.ue_events.append(data)
        self._refresh_ue_table()

    def _build_tests_tab(self):
        tests_tab = TabbedPanelItem(text="Tests")
        tests_container = AnchorLayout(anchor_x='left', anchor_y='top', padding=0)
        with tests_container.canvas.before:
            Color(0.105, 0.168, 0.247, 1)
            self.tests_bg = Rectangle(pos=tests_container.pos, size=tests_container.size)
        tests_container.bind(pos=self._update_tests_bg, size=self._update_tests_bg)

        self.test_panel = TestPanel()
        self.test_panel.size_hint_y = None
        self.test_panel.bind(minimum_height=self.test_panel.setter('height'))
        tests_container.add_widget(self.test_panel)
        tests_tab.add_widget(tests_container)
        self.add_widget(tests_tab)

    def _update_tests_bg(self, layout, _):
        self.tests_bg.pos = layout.pos
        self.tests_bg.size = layout.size

    def _build_details_tab(self):
        details_tab = TabbedPanelItem(text="Details")
        details_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        with details_layout.canvas.before:
            Color(0.105, 0.168, 0.247, 1)
            self.bg_rect = Rectangle(pos=details_layout.pos, size=details_layout.size)
        details_layout.bind(pos=self._update_bg_rect, size=self._update_bg_rect)

        filter_bar = BoxLayout(size_hint_y=None, height=50, spacing=10)
        self.filter_spinner = Spinner(
            text="All",
            values=(
                "All", "NAS-EPS", "NAS-5GS", "CELL", "IMSI", "GUTI",
                "s-TMSI", "SUPI", "SUCI", "MSIN", "m-TMSI", "5G-TMSI", "IMEISV"
            ),
            size_hint_x=0.3,
            background_normal='',
            background_color=(0.2, 0.3, 0.4, 1),
            color=(1, 1, 1, 1)
        )
        self.filter_spinner.bind(text=self._on_spinner_select)
        filter_bar.add_widget(self.filter_spinner)

        self.top_bar_buttons = BoxLayout(size_hint_x=0.7, spacing=5)
        self._update_top_bar_buttons()
        filter_bar.add_widget(self.top_bar_buttons)
        details_layout.add_widget(filter_bar)

        self.header_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=35, padding=(5, 0, 5, 0))
        details_layout.add_widget(self.header_layout)

        self.scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=True, bar_width=20, scroll_type=['bars'])
        self.identifier_grid = BoxLayout(orientation='vertical', padding=(0, 0, 0, 0), spacing=0, size_hint_y=None)
        self.identifier_grid.bind(minimum_height=self.identifier_grid.setter('height'))
        self.scroll_view.add_widget(self.identifier_grid)
        details_layout.add_widget(self.scroll_view)

        self.show_all_btn = Button(
            text="Show All",
            size_hint_y=None,
            height=40,
            background_normal='',
            background_color=(0.2, 0.3, 0.4, 1),
            color=(1, 1, 1, 1)
        )
        self.show_all_btn.bind(on_release=self._toggle_show_all)
        details_layout.add_widget(self.show_all_btn)

        self.counter_label = Label(
            text="Total Unique IDs Captured: 0",
            font_size=16,
            size_hint_y=None,
            height=30,
            color=(1, 1, 1, 1)
        )
        details_layout.add_widget(self.counter_label)

        details_tab.add_widget(details_layout)
        self.add_widget(details_tab)

    def _update_bg_rect(self, *args):
        self.bg_rect.pos = args[0].pos
        self.bg_rect.size = args[0].size

    def _on_spinner_select(self, spinner, text):
        self.selection_mode = False
        self._refresh_display()
        self._update_top_bar_buttons()

    def _toggle_show_all(self, _btn):
        if not self.show_all:
            box = BoxLayout(orientation='vertical', spacing=10, padding=10)
            lbl = Label(
                text="Are you sure you want to show all IDs? This may cause lag.",
                color=(1, 1, 1, 1)
            )
            box.add_widget(lbl)
            row = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=40)
            b_yes = Button(text="Yes", background_color=(0.8, 0, 0, 1), color=(1, 1, 1, 1))
            b_no = Button(text="No", background_color=(0, 0.6, 0, 1), color=(1, 1, 1, 1))
            row.add_widget(b_yes)
            row.add_widget(b_no)
            box.add_widget(row)
            popup = Popup(title="Show All?", content=box, size_hint=(0.5, 0.3), auto_dismiss=False)

            def do_yes(*_):
                popup.dismiss()
                self.show_all = True
                self.show_all_btn.text = "Show Top 50"
                self._refresh_display()

            def do_no(*_):
                popup.dismiss()

            b_yes.bind(on_release=do_yes)
            b_no.bind(on_release=do_no)
            popup.open()
        else:
            self.show_all = False
            self.show_all_btn.text = "Show All"
            self._refresh_display()

    def _update_top_bar_buttons(self):
        self.top_bar_buttons.clear_widgets()
        if self.selection_mode:
            b_apply = Button(
                text="Apply",
                size_hint_x=0.3,
                font_size=14,
                background_normal='',
                background_color=(0.4, 0.6, 0.4, 1),
                color=(1, 1, 1, 1)
            )
            b_apply.bind(on_release=lambda *_: self._apply_tracking())

            b_cancel = Button(
                text="Cancel",
                size_hint_x=0.3,
                font_size=14,
                background_normal='',
                background_color=(0.8, 0.4, 0.4, 1),
                color=(1, 1, 1, 1)
            )
            b_cancel.bind(on_release=lambda *_: self._cancel_selection())

            self.top_bar_buttons.add_widget(b_apply)
            self.top_bar_buttons.add_widget(b_cancel)
        else:
            if self.track_mode:
                b_add = Button(
                    text="Add More IDs",
                    size_hint_x=0.3,
                    font_size=14,
                    background_normal='',
                    background_color=(0.4, 0.6, 0.4, 1),
                    color=(1, 1, 1, 1)
                )
                b_add.bind(on_release=lambda *_: self._enter_selection_mode())

                b_stop = Button(
                    text="Stop Tracking",
                    size_hint_x=0.3,
                    font_size=14,
                    background_normal='',
                    background_color=(0.6, 0.4, 0.4, 1),
                    color=(1, 1, 1, 1)
                )
                b_stop.bind(on_release=lambda *_: self._stop_tracking())

                self.top_bar_buttons.add_widget(b_add)
                self.top_bar_buttons.add_widget(b_stop)
            else:
                b_track = Button(
                    text="Track",
                    size_hint_x=0.3,
                    font_size=14,
                    background_normal='',
                    background_color=(0.4, 0.6, 0.4, 1),
                    color=(1, 1, 1, 1)
                )
                b_track.bind(on_release=lambda *_: self._enter_selection_mode())
                self.top_bar_buttons.add_widget(b_track)

            b_export = Button(
                text="Export",
                size_hint_x=0.3,
                font_size=14,
                background_normal='',
                background_color=(0.2, 0.3, 0.4, 1),
                color=(1, 1, 1, 1)
            )
            b_export.bind(on_release=lambda *_: self.export_to_csv())
            self.top_bar_buttons.add_widget(b_export)

    def _enter_selection_mode(self):
        self.selection_mode = True
        self._refresh_display()
        self._update_top_bar_buttons()

    def _apply_tracking(self):
        if self.selected_ids:
            self.track_mode = True
        self.selection_mode = False
        self._refresh_display()
        self._update_top_bar_buttons()

    def _cancel_selection(self):
        self.selection_mode = False
        self.selected_ids.clear()
        self._refresh_display()
        self._update_top_bar_buttons()

    def _stop_tracking(self):
        self.track_mode = False
        self.selected_ids.clear()
        self._refresh_display()
        self._update_top_bar_buttons()

    def add_table_header(self):
        self.header_layout.clear_widgets()
        arrow_up = "^"
        arrow_down = "v"
        if self.filter_spinner.text == "All":
            headers = ["ID Type", "Identifier", "Count", "Last Seen", "Lifespan", "TAC", "CID", "Active"]
            keys = ["id_type", "identifier", "count", "last_seen", "lifespan", "tracking_area_code", "cell_identity", "active"]
        else:
            headers = ["Identifier", "Count", "Last Seen", "Lifespan", "TAC", "CID", "Active"]
            keys = ["identifier", "count", "last_seen", "lifespan", "tracking_area_code", "cell_identity", "active"]

        for h, k in zip(headers, keys):
            lbl_txt = h
            if k == self.sort_column:
                lbl_txt = f"{h} {arrow_up}" if self.sort_ascending else f"{h} {arrow_down}"
            btn = Button(
                text=lbl_txt,
                font_size=14,
                background_normal='',
                background_color=(0.2, 0.3, 0.4, 1),
                color=(1, 1, 1, 1),
                halign='left',  # left alignment
                valign='middle'
            )
            btn.bind(size=lambda inst, val: setattr(inst, 'text_size', val))

            def closure(col):
                return lambda *_: self._on_header_click(col)
            btn.bind(on_release=closure(k))
            self.header_layout.add_widget(btn)

    def _on_header_click(self, sort_key):
        if sort_key == self.sort_column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = sort_key
            self.sort_ascending = True
        self._refresh_display()

    def _get_sort_key(self, item):
        (filt, ident), info = item
        from datetime import datetime
        if self.sort_column == "id_type":
            return filt or ""
        elif self.sort_column == "identifier":
            return ident or ""
        elif self.sort_column == "count":
            return info["count"]
        elif self.sort_column == "last_seen":
            ls = info["last_seen"]
            if not ls:
                return datetime.min
            try:
                return datetime.strptime(ls, "%Y-%m-%d %H:%M:%S")
            except:
                return datetime.min
        elif self.sort_column == "lifespan":
            if info["first_seen"] and info["last_seen"]:
                try:
                    t1 = datetime.strptime(info["first_seen"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(info["last_seen"], "%Y-%m-%d %H:%M:%S")
                    sec = (t2 - t1).total_seconds()
                    if sec < 0:
                        sec += 86400
                    return sec
                except:
                    return 0
            return 0
        elif self.sort_column == "tracking_area_code":
            return info.get("tracking_area_code", "")
        elif self.sort_column == "cell_identity":
            return info.get("cell_identity", "")
        elif self.sort_column == "active":
            ls = info["last_seen"]
            if not ls:
                return 999999
            try:
                now = datetime.now()
                dt2 = datetime.strptime(ls, "%Y-%m-%d %H:%M:%S")
                return (now - dt2).total_seconds()
            except:
                return 999999
        return 0

    def _refresh_display(self):
        self.header_layout.clear_widgets()
        self.add_table_header()
        self.identifier_grid.clear_widgets()

        items = []
        for (filt, ident), info in self.ids_dict.items():
            # filter the display
            if self.filter_spinner.text != "All" and self.filter_spinner.text != filt:
                continue
            items.append(((filt, ident), info))

        pinned = []
        normal = []
        for (filt, ident), info in items:
            if (filt, ident) in self.selected_ids:
                pinned.append(((filt, ident), info))
            else:
                normal.append(((filt, ident), info))

        pinned.sort(key=self._get_sort_key, reverse=not self.sort_ascending)
        normal.sort(key=self._get_sort_key, reverse=not self.sort_ascending)
        final_list = pinned + normal

        if not self.show_all:
            final_list = final_list[:50]

        if self.filter_spinner.text == "All":
            col_keys = ["id_type", "identifier", "count", "last_seen", "lifespan", "tracking_area_code", "cell_identity", "active"]
        else:
            col_keys = ["identifier", "count", "last_seen", "lifespan", "tracking_area_code", "cell_identity", "active"]

        for (filt, ident), info in final_list:
            sec = 0
            if info["first_seen"] and info["last_seen"]:
                try:
                    t1 = datetime.strptime(info["first_seen"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(info["last_seen"], "%Y-%m-%d %H:%M:%S")
                    sec = (t2 - t1).total_seconds()
                    if sec < 0:
                        sec += 86400
                except:
                    pass
            life_str = format_lifespan(sec)
            row = TableRow(
                filt, ident, info, life_str,
                self._show_detail_popup,
                selection_mode_ref=lambda: self.selection_mode,
                track_mode_ref=lambda: self.track_mode,
                selected_ids_ref=self.selected_ids,
                col_keys=col_keys
            )
            self.identifier_grid.add_widget(row)
            self.identifier_grid.add_widget(BoxLayout(size_hint_y=None, height=1))

        self.test_panel.update_tests(self.ids_dict)
        self.counter_label.text = f"Total Unique IDs Captured: {len(self.ids_dict)}"

    def _show_detail_popup(self, idtype, ident, info, life):
        srclist = ", ".join(sorted(info["sources"])) or "N/A"
        conv = convert_id(ident)
        # If the real type is different, show it
        real_type_line = ""
        if idtype != info["display_type"]:
            real_type_line = f"\nReal ID Type: {info['display_type']}"

        dtxt = (
            f"ID Type: {idtype}\n"
            f"Identifier: {ident}\n"
            f"{conv}{real_type_line}\n"
            f"First Seen: {info.get('first_seen','N/A')}\n"
            f"Last Seen: {info.get('last_seen','N/A')}\n"
            f"Count: {info['count']}\n"
            f"Lifespan: {life}\n"
            f"TAC: {info.get('tracking_area_code','')}\n"
            f"CID: {info.get('cell_identity','')}\n"
            f"MCC: {info.get('mcc','')}\n"
            f"MNC: {info.get('mnc','')}\n"
            f"MME Group ID: {info.get('mme_group_id','')}\n"
            f"MME Code: {info.get('mme_code','')}\n"
            f"Message Types: {srclist}\n"
        )
        box = BoxLayout(orientation='vertical', spacing=10, padding=10)
        txt = TextInput(
            text=dtxt,
            readonly=True,
            font_size=14,
            background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1)
        )
        box.add_widget(txt)

        btnbox = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=40)
        b_track = Button(
            text="Track This ID",
            background_normal='',
            background_color=(0.4, 0.6, 0.4, 1),
            color=(1, 1, 1, 1),
            size_hint=(0.5, 1)
        )
        b_close = Button(
            text="Close",
            background_normal='',
            background_color=(0.2, 0.4, 0.6, 1),
            color=(1, 1, 1, 1),
            size_hint=(0.5, 1)
        )
        popup = Popup(title="Details", content=box, size_hint=(0.7, 0.7), auto_dismiss=False)

        def do_track(_):
            if not self.selection_mode and not self.track_mode:
                self.selection_mode = True
                self.selected_ids.clear()
            self.selected_ids.add((idtype, ident))
            popup.dismiss()
            self._refresh_display()
            self._update_top_bar_buttons()

        b_track.bind(on_release=do_track)
        b_close.bind(on_release=lambda *_: popup.dismiss())
        btnbox.add_widget(b_track)
        btnbox.add_widget(b_close)
        box.add_widget(btnbox)
        popup.open()

    def export_to_csv(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
        row1.add_widget(Label(text="Filename:", size_hint_x=0.3, color=(1, 1, 1, 1)))
        filename_input = TextInput(text="exported_identifiers.csv")
        row1.add_widget(filename_input)
        content.add_widget(row1)

        row2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
        b_save = Button(text="Save")
        b_cancel = Button(text="Cancel")
        row2.add_widget(b_save)
        row2.add_widget(b_cancel)
        content.add_widget(row2)

        popup = Popup(title="Export CSV", content=content, size_hint=(0.8, 0.3), auto_dismiss=False)
        def do_save(_):
            fname = filename_input.text.strip() or "exported_identifiers.csv"
            try:
                with open(fname, "w", newline="") as csvf:
                    w = csv.writer(csvf)
                    w.writerow([
                        "Filter Type","Identifier","Count","First Seen","Last Seen",
                        "TAC","CID","MCC","MNC","MME Group ID","MME Code","Message Types"
                    ])
                    for (filt, ident), info in self.ids_dict.items():
                        srcs = ",".join(sorted(info["sources"]))
                        w.writerow([
                            filt,
                            ident,
                            info["count"],
                            info.get("first_seen",""),
                            info.get("last_seen",""),
                            info.get("tracking_area_code",""),
                            info.get("cell_identity",""),
                            info.get("mcc",""),
                            info.get("mnc",""),
                            info.get("mme_group_id",""),
                            info.get("mme_code",""),
                            srcs
                        ])
            except Exception as e:
                print("[DEBUG] Error writing CSV:", e)
            popup.dismiss()
        b_save.bind(on_release=do_save)
        b_cancel.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

from kivy.clock import Clock


class IdentifierApp(App):
    def build(self):
        Window.bind(on_keyboard=self._on_keyboard)
        Window.bind(on_request_close=self.on_request_close)
        # remember last UE event to skip identical repeats
        self._last_ue_event = None

        root = BoxLayout(orientation='vertical')
        self.disp = IdentifierDisplayMain()
        root.add_widget(self.disp)
        Clock.schedule_interval(self.update_gui, 1.0)
        return root

    def update_gui(self, dt):
        while not capture_queue.empty():
            item = capture_queue.get()

            # new-style tuples with 11 items
            if isinstance(item, tuple) and len(item) == 11:
                (filt, ident, ts, mcc, mnc, tac, cid,
                 packet_info, disp_type, mme_grp, mme_cd) = item

                # non-paging => candidate for UE-connected
                if "Paging" not in packet_info:
                    ue_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ue_data = {
                        "timestamp": ue_ts,
                        "id_type": disp_type,
                        "id": ident,
                        "packet_info": packet_info,
                        "tac": tac,
                        "cid": cid,
                        "mcc": mcc,
                        "mnc": mnc,
                        "mme_group_id": mme_grp,
                        "mme_code": mme_cd
                    }
                    # skip if identical to last
                    if ue_data != self._last_ue_event:
                        self.disp.update_ue_info(ue_data)
                        self._last_ue_event = ue_data.copy()

                info = self.disp.ids_dict[(filt, ident)]
                if not info["first_seen"]:
                    info["first_seen"] = ts
                info["last_seen"] = ts
                info["count"] += 1
                info["display_type"] = disp_type
                if mcc: info["mcc"] = mcc
                if mnc: info["mnc"] = mnc
                if tac: info["tracking_area_code"] = tac
                if cid: info["cell_identity"] = cid
                info["mme_group_id"] = mme_grp
                info["mme_code"] = mme_cd
                info["sources"].add(packet_info)

            # old-style tuples with 9 items
            elif isinstance(item, tuple) and len(item) == 9:
                (filt, ident, ts, mcc, mnc, tac, cid, packet_info, disp_type) = item

                if "Paging" not in packet_info:
                    ue_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ue_data = {
                        "timestamp": ue_ts,
                        "id_type": disp_type,
                        "id": ident,
                        "packet_info": packet_info,
                        "tac": tac,
                        "cid": cid,
                        "mcc": mcc,
                        "mnc": mnc,
                        "mme_group_id": "",
                        "mme_code": ""
                    }
                    if ue_data != self._last_ue_event:
                        self.disp.update_ue_info(ue_data)
                        self._last_ue_event = ue_data.copy()

                info = self.disp.ids_dict[(filt, ident)]
                if not info["first_seen"]:
                    info["first_seen"] = ts
                info["last_seen"] = ts
                info["count"] += 1
                info["display_type"] = disp_type
                if mcc: info["mcc"] = mcc
                if mnc: info["mnc"] = mnc
                if tac: info["tracking_area_code"] = tac
                if cid: info["cell_identity"] = cid
                info["sources"].add(packet_info)

        if not self.disp.selection_mode:
            self.disp._refresh_display()

    def _on_keyboard(self, window, key, scancode, codepoint, modifiers):
        if key == 27:
            self.show_exit_confirmation()
            return True
        return False

    def on_request_close(self, *args):
        self.show_exit_confirmation()
        return True

    def show_exit_confirmation(self):
        box = BoxLayout(orientation='vertical', spacing=10, padding=10)
        lbl = Label(text="Are you sure you want to exit?", color=(1,1,1,1), font_size=16)
        box.add_widget(lbl)
        row = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=40)
        b_yes = Button(text="Yes", background_color=(0.8,0,0,1), color=(1,1,1,1))
        b_no  = Button(text="No",  background_color=(0,0.6,0,1), color=(1,1,1,1))
        row.add_widget(b_yes);  row.add_widget(b_no)
        box.add_widget(row)
        self.exit_popup = Popup(title="Confirm Exit", content=box,
                                size_hint=(0.5,0.3), auto_dismiss=False)
        b_yes.bind(on_release=lambda *_: self.exit_app())
        b_no .bind(on_release=lambda *_: self.dismiss_exit_popup())
        self.exit_popup.open()

    def dismiss_exit_popup(self):
        if getattr(self, 'exit_popup', None):
            self.exit_popup.dismiss()
            self.exit_popup = None

    def exit_app(self):
        self.dismiss_exit_popup()
        self.stop()
