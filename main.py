"""
Smart Gallery Cleaner - Kivy Version (Android APK ready)
Features: Blurry, Blank, Duplicate, No Person detection
Minimal black/white theme, thumbnails, full preview, select all, confirm delete
"""

import os
import cv2
import numpy as np
from functools import partial
from PIL import Image
import imagehash

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.uix.image import Image as KivyImage
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.clock import Clock

# ── Palette ─────────────────────────────────────────────────────────
BG        = (0.96, 0.96, 0.96, 1)
CARD      = (1.00, 1.00, 1.00, 1)
TEXT_DARK = (0.10, 0.10, 0.10, 1)
TEXT_MID  = (0.50, 0.50, 0.50, 1)
BTN_BLACK = (0.10, 0.10, 0.10, 1)
BTN_RED   = (0.88, 0.18, 0.18, 1)
BTN_GREEN = (0.18, 0.62, 0.38, 1)
BTN_WHITE = (1.00, 1.00, 1.00, 1)
BTN_GREY  = (0.60, 0.60, 0.60, 1)

CAT_COLORS = {
    "Blurry":    (0.91, 0.49, 0.06, 1),
    "Blank":     (0.55, 0.55, 0.55, 1),
    "Duplicate": (0.18, 0.45, 0.90, 1),
    "No Person": (0.60, 0.18, 0.80, 1),
}


def _bg(widget, color, r=8):
    with widget.canvas.before:
        Color(*color)
        widget._bg = RoundedRectangle(
            size=widget.size, pos=widget.pos, radius=[dp(r)])
    widget.bind(
        size=lambda w, v: setattr(w._bg, 'size', v),
        pos =lambda w, v: setattr(w._bg, 'pos',  v))


def _make_btn(text, color, cb, height=dp(44)):
    btn = Button(
        text=text,
        background_normal='',
        background_color=color,
        color=BTN_WHITE,
        bold=True,
        font_size=dp(13),
        size_hint_y=None,
        height=height,
    )
    btn.bind(on_press=cb)
    return btn


# ── Full image preview popup ─────────────────────────────────────────
class PreviewPopup(Popup):
    def __init__(self, path, category, face_count, **kw):
        content = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(8))

        # top bar: badge + close button
        top = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(8))
        cat_color = CAT_COLORS.get(category, BTN_BLACK)
        badge = Label(
            text=f"  {category}  ",
            color=BTN_WHITE, bold=True, font_size=dp(12),
            size_hint=(None, 1), width=dp(100))
        _bg(badge, cat_color, r=10)
        top.add_widget(badge)

        face_lbl = Label(
            text=f"Faces: {face_count}",
            color=TEXT_DARK, font_size=dp(12),
            size_hint=(None, 1), width=dp(80))
        top.add_widget(face_lbl)
        top.add_widget(Label())  # spacer

        close_btn = Button(
            text="✕ Close",
            background_normal='',
            background_color=BTN_BLACK,
            color=BTN_WHITE,
            bold=True,
            font_size=dp(12),
            size_hint=(None, 1),
            width=dp(90))
        top.add_widget(close_btn)
        content.add_widget(top)

        # full image
        img = KivyImage(
            source=path,
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(1, 1))
        content.add_widget(img)

        # filename
        content.add_widget(Label(
            text=os.path.basename(path),
            color=TEXT_MID, font_size=dp(10),
            size_hint=(1, None), height=dp(20)))

        super().__init__(
            title='',
            content=content,
            size_hint=(0.95, 0.92),
            separator_height=0,
            **kw)

        close_btn.bind(on_press=lambda *_: self.dismiss())


# ── One image card ────────────────────────────────────────────────────
class ImageCard(BoxLayout):
    def __init__(self, path, category, face_count, on_check, on_preview, **kw):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(82),
            padding=dp(8),
            spacing=dp(8),
            opacity=0,
            **kw)
        _bg(self, CARD, r=10)

        # checkbox
        self.chk = CheckBox(size_hint=(None, 1), width=dp(32))
        self.chk.bind(active=partial(on_check, path))
        self.add_widget(self.chk)

        # thumbnail — tap to preview
        thumb_btn = Button(
            background_normal=path,
            background_down=path,
            size_hint=(None, 1),
            width=dp(68),
            border=(0, 0, 0, 0))
        thumb_btn.bind(on_press=lambda *_: on_preview(path, category, face_count))
        self.add_widget(thumb_btn)

        # info
        info = BoxLayout(orientation='vertical', spacing=dp(2))

        name_lbl = Label(
            text=os.path.basename(path),
            color=TEXT_DARK, bold=True, font_size=dp(13),
            halign='left', valign='middle',
            shorten=True, shorten_from='right',
            size_hint_y=None, height=dp(22))
        name_lbl.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
        info.add_widget(name_lbl)

        # badge + face count row
        badge_row = BoxLayout(
            orientation='horizontal', spacing=dp(6),
            size_hint_y=None, height=dp(24))

        badge_lbl = Label(
            text=f"  {category}  ",
            color=BTN_WHITE, bold=True, font_size=dp(11),
            size_hint=(None, 1), width=dp(90))
        _bg(badge_lbl, CAT_COLORS.get(category, BTN_BLACK), r=10)
        badge_row.add_widget(badge_lbl)

        badge_row.add_widget(Label(
            text=f"Faces: {face_count}",
            color=TEXT_MID, font_size=dp(11),
            size_hint=(None, 1), width=dp(72)))

        badge_row.add_widget(Label(
            text="👁 tap image to preview",
            color=(0.18, 0.45, 0.90, 1), font_size=dp(10)))
        info.add_widget(badge_row)

        path_lbl = Label(
            text=path,
            color=TEXT_MID, font_size=dp(10),
            halign='left', shorten=True, shorten_from='left',
            size_hint_y=None, height=dp(16))
        path_lbl.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
        info.add_widget(path_lbl)

        self.add_widget(info)
        Animation(opacity=1, duration=0.15).start(self)


# ── Stat bar ──────────────────────────────────────────────────────────
class StatBar(BoxLayout):
    def __init__(self, **kw):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(56),
            spacing=dp(4),
            padding=[dp(8), dp(6)], **kw)
        _bg(self, CARD, r=10)
        self._nums = {}
        for cat in ["Blurry", "Duplicate", "Blank", "No Person"]:
            col = BoxLayout(orientation='vertical')
            n = Label(text="0", color=TEXT_DARK, bold=True, font_size=dp(18))
            c = Label(text=cat, color=TEXT_MID, font_size=dp(10))
            col.add_widget(n)
            col.add_widget(c)
            self.add_widget(col)
            self._nums[cat] = n

    def update(self, counts):
        for k, v in counts.items():
            if k in self._nums:
                self._nums[k].text = str(v)


# ── Main UI ───────────────────────────────────────────────────────────
class GalleryCleanerUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(12), **kw)
        _bg(self, BG, r=0)

        # title
        self.add_widget(Label(
            text="Smart Gallery Cleaner",
            font_size=dp(20), bold=True,
            color=TEXT_DARK,
            size_hint=(1, None), height=dp(40)))

        # stat bar
        self.stat_bar = StatBar()
        self.add_widget(self.stat_bar)

        # button row
        row = BoxLayout(
            size_hint=(1, None), height=dp(46), spacing=dp(8))
        self.btn_scan = _make_btn("Scan Folder", BTN_BLACK, self._open_chooser)
        self.btn_sel  = _make_btn("Select All",  BTN_GREEN, self._toggle_all)
        row.add_widget(self.btn_scan)
        row.add_widget(self.btn_sel)
        self.add_widget(row)

        # status
        self.status = Label(
            text="Tap  Scan Folder  to begin.",
            color=TEXT_MID, font_size=dp(12),
            size_hint=(1, None), height=dp(24))
        self.add_widget(self.status)

        # scroll list
        self.scroll = ScrollView(size_hint=(1, 1))
        self.grid = GridLayout(
            cols=1, spacing=dp(8),
            size_hint_y=None, padding=[0, dp(4)])
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        self.add_widget(self.scroll)

        # delete button
        self.btn_del = _make_btn(
            "Delete Selected", BTN_RED, self._confirm_delete, height=dp(50))
        self.btn_del.size_hint_y = None
        self.add_widget(self.btn_del)

        self.selected   = []
        self.checkboxes = []
        self.all_sel    = False
        self._counts    = {k: 0 for k in
                           ["Blurry", "Duplicate", "Blank", "No Person"]}

    # ── folder chooser ─────────────────────────────────────────────
    def _open_chooser(self, *_):
        chooser = FileChooserListView(
            path=os.path.expanduser("~"), dirselect=True)
        content = BoxLayout(orientation='vertical', spacing=dp(8))
        content.add_widget(chooser)
        ok = _make_btn("Open This Folder", BTN_BLACK, lambda *_: None)
        content.add_widget(ok)

        popup = Popup(
            title="Choose Folder",
            content=content,
            size_hint=(0.95, 0.90))

        def _go(*_):
            sel = chooser.selection
            if sel:
                popup.dismiss()
                self.status.text = "Scanning… please wait."
                Clock.schedule_once(lambda *_: self._scan(sel[0]), 0.1)

        ok.bind(on_press=_go)
        popup.open()

    # ── detection ──────────────────────────────────────────────────
    @staticmethod
    def _is_blurry(path, thr=90):
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        return img is not None and cv2.Laplacian(img, cv2.CV_64F).var() < thr

    @staticmethod
    def _is_blank(path, thr=10):
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        return img is not None and float(np.std(img)) < thr

    @staticmethod
    def _phash(path):
        try:
            return imagehash.phash(Image.open(path))
        except Exception:
            return None

    @staticmethod
    def _detect_faces(path):
        det = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        img = cv2.imread(path)
        if img is None:
            return False, 0
        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = det.detectMultiScale(gray, 1.1, 5)
        n = len(faces)
        return n > 0, n

    # ── scan ───────────────────────────────────────────────────────
    def _scan(self, folder):
        self.grid.clear_widgets()
        self.selected.clear()
        self.checkboxes.clear()
        self.all_sel = False
        self.btn_sel.text = "Select All"
        self._counts = {k: 0 for k in self._counts}
        self.stat_bar.update(self._counts)

        exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
        try:
            files = [f for f in os.listdir(folder)
                     if f.lower().endswith(exts)]
        except PermissionError:
            self.status.text = "Permission denied."
            return

        seen  = {}
        found = 0

        for fname in files:
            path = os.path.join(folder, fname)
            try:
                category = None

                h = self._phash(path)
                if h is not None:
                    if h in seen:
                        category = "Duplicate"
                    else:
                        seen[h] = path

                if category is None and self._is_blank(path):
                    category = "Blank"

                if category is None and self._is_blurry(path):
                    category = "Blurry"

                has_face, face_count = self._detect_faces(path)
                if category is None and not has_face:
                    category = "No Person"

                if category is not None:
                    self._counts[category] += 1
                    card = ImageCard(
                        path=path,
                        category=category,
                        face_count=face_count,
                        on_check=self._on_check,
                        on_preview=self._show_preview)
                    self.grid.add_widget(card)
                    self.checkboxes.append(card.chk)
                    found += 1

            except Exception as e:
                print(f"Skip {fname}: {e}")

        self.stat_bar.update(self._counts)
        total = sum(self._counts.values())
        self.status.text = (
            f"Found {total} issue(s) in {len(files)} images." if total
            else "Your gallery looks clean!")

    # ── preview ────────────────────────────────────────────────────
    def _show_preview(self, path, category, face_count):
        PreviewPopup(path=path, category=category,
                     face_count=face_count).open()

    # ── checkbox / select all ──────────────────────────────────────
    def _on_check(self, path, chk, value):
        if value:
            if path not in self.selected:
                self.selected.append(path)
        else:
            if path in self.selected:
                self.selected.remove(path)

    def _toggle_all(self, *_):
        self.all_sel = not self.all_sel
        for c in self.checkboxes:
            c.active = self.all_sel
        self.btn_sel.text = "Deselect All" if self.all_sel else "Select All"

    # ── delete ─────────────────────────────────────────────────────
    def _confirm_delete(self, *_):
        n = len(self.selected)
        if n == 0:
            self._toast("Select images first.")
            return

        box = BoxLayout(orientation='vertical', spacing=dp(14), padding=dp(16))
        box.add_widget(Label(
            text=f"Delete {n} image{'s' if n > 1 else ''}?\nThis cannot be undone.",
            color=TEXT_DARK, halign='center', font_size=dp(14)))

        btns = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        yes = _make_btn("Delete", BTN_RED,   lambda *_: None)
        no  = _make_btn("Cancel", BTN_GREY,  lambda *_: None)
        btns.add_widget(yes)
        btns.add_widget(no)
        box.add_widget(btns)

        popup = Popup(title="Confirm Delete", content=box,
                      size_hint=(0.80, 0.36))
        yes.bind(on_press=lambda *_: (self._do_delete(), popup.dismiss()))
        no.bind( on_press=lambda *_: popup.dismiss())
        popup.open()

    def _do_delete(self):
        fail = 0
        for p in self.selected:
            try:
                os.remove(p)
            except Exception:
                fail += 1
        self.grid.clear_widgets()
        self.selected.clear()
        self.checkboxes.clear()
        self.all_sel = False
        self.btn_sel.text = "Select All"
        self.stat_bar.update({k: 0 for k in self._counts})
        self.status.text = (
            "Deleted! Scan again to refresh." if not fail
            else f"Done. {fail} file(s) failed.")

    def _toast(self, msg):
        p = Popup(title="", content=Label(text=msg, color=TEXT_DARK),
                  size_hint=(0.6, 0.18))
        p.open()
        Clock.schedule_once(lambda *_: p.dismiss(), 1.5)


# ── App ────────────────────────────────────────────────────────────
class SmartGalleryApp(App):
    def build(self):
        self.title = "Smart Gallery Cleaner"
        return GalleryCleanerUI()


if __name__ == "__main__":
    SmartGalleryApp().run()
