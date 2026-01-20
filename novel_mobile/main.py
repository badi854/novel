from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.widget import Widget

from app.constants import AUTOSAVE_INTERVAL_SECONDS, DEFAULT_PROJECT_NAME, VERSION_SNAPSHOT_MIN_SECONDS
from app.exporters.exporter import ExportContext
from app.exporters.txt_exporter import TxtExporter
from app.models import ChapterNode
from app.storage.knowledge_store import KnowledgeStore
from app.storage.project_store import ProjectStore
from app.storage.stats_store import StatsStore
from app.storage.version_store import VersionEntry, VersionStore
from app.utils.paths import data_root, ensure_dir
from app.utils.text import hex_to_rgba, temperature_to_colors, word_count


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class ThemeState:
    mode: str = "light"  # light/night/eye
    temperature: int = 4500


class BarChart(Widget):
    """非常轻量的柱状图：用于每日进度。"""

    values = ObjectProperty([])
    labels = ObjectProperty([])

    def redraw(self) -> None:
        self.canvas.clear()
        vals = list(self.values or [])
        if not vals:
            return
        max_v = max(vals) or 1

        from kivy.graphics import Color, Rectangle

        w = self.width
        h = self.height
        n = len(vals)
        gap = dp(4)
        bar_w = max(dp(6), (w - gap * (n + 1)) / n)

        with self.canvas:
            Color(0.22, 0.55, 0.85, 0.9)
            for i, v in enumerate(vals):
                bh = (v / max_v) * (h - dp(8))
                x = gap + i * (bar_w + gap)
                y = dp(4)
                Rectangle(pos=(x, y), size=(bar_w, bh))

    def on_size(self, *_):
        self.redraw()


class ChapterTreeView(TreeView):
    """TreeView 节点上挂 meta：node_id/is_folder"""

    selected_node = ObjectProperty(None, allownone=True)

    def clear_tree(self) -> None:
        for n in list(self.iterate_all_nodes()):
            try:
                self.remove_node(n)
            except Exception:
                pass


class RootLayout(BoxLayout):
    focus_mode = BooleanProperty(False)
    status_text = StringProperty("就绪")


class NovelMobileApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme = ThemeState()

        self.project_dir: Path | None = None
        self.store: ProjectStore | None = None
        self.version_store: VersionStore | None = None
        self.stats_store: StatsStore | None = None
        self.knowledge_store: KnowledgeStore | None = None

        self.project_root: ChapterNode | None = None
        self._current_chapter_id: str | None = None
        self._last_version_ts: dict[str, float] = {}
        self._last_stats_ts: float = 0.0
        self._chapter_word_cache: dict[str, int] = {}
        self._total_words_cache: int = 0

        self.root_layout: RootLayout | None = None
        self.tree: ChapterTreeView | None = None
        self.editor: TextInput | None = None
        self.left_panel: BoxLayout | None = None

    def build(self):
        # Android/桌面统一：把数据目录指向 user_data_dir
        os.environ.setdefault("NOVEL_DATA_DIR", self.user_data_dir)

        self._init_project()

        root = RootLayout(orientation="vertical")
        self.root_layout = root

        # 顶部工具栏
        toolbar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6), padding=[dp(6), dp(6), dp(6), dp(6)])

        btn_new_ch = Button(text="新章")
        btn_new_dir = Button(text="新夹")
        btn_rename = Button(text="重命名")
        btn_delete = Button(text="删除")
        btn_up = Button(text="上移")
        btn_down = Button(text="下移")

        btn_timeline = Button(text="时间轴")
        btn_dash = Button(text="仪表盘")
        btn_export = Button(text="导出TXT")
        btn_focus = Button(text="专注")

        toolbar.add_widget(btn_new_ch)
        toolbar.add_widget(btn_new_dir)
        toolbar.add_widget(btn_rename)
        toolbar.add_widget(btn_delete)
        toolbar.add_widget(btn_up)
        toolbar.add_widget(btn_down)
        toolbar.add_widget(btn_timeline)
        toolbar.add_widget(btn_dash)
        toolbar.add_widget(btn_export)
        toolbar.add_widget(btn_focus)

        # 主题控件
        theme_spinner = Spinner(text="明亮", values=["明亮", "夜间", "护眼"], size_hint_x=None, width=dp(90))
        temp_slider = Slider(min=1000, max=9000, value=self.theme.temperature)
        temp_slider.size_hint_x = 1
        temp_slider.width = dp(150)

        toolbar.add_widget(theme_spinner)
        toolbar.add_widget(Label(text="色温", size_hint_x=None, width=dp(42)))
        toolbar.add_widget(temp_slider)

        # 主体：左树 + 右编辑
        body = BoxLayout(orientation="horizontal")

        self.left_panel = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(260))
        self.left_panel.add_widget(Label(text="章节", size_hint_y=None, height=dp(28)))

        self.tree = ChapterTreeView(hide_root=True, indent_level=dp(16))
        self.tree.bind(on_touch_down=self._on_tree_touch)
        scroll = ScrollView()

        scroll.add_widget(self.tree)
        self.left_panel.add_widget(scroll)

        self.editor = TextInput(multiline=True, font_size=dp(16), padding=[dp(10), dp(10), dp(10), dp(10)])
        self.editor.bind(text=self._on_editor_text)

        body.add_widget(self.left_panel)
        body.add_widget(self.editor)

        status = Label(text="就绪", size_hint_y=None, height=dp(28))
        root.add_widget(toolbar)
        root.add_widget(body)
        root.add_widget(status)

        # 绑定
        btn_new_ch.bind(on_release=lambda *_: self._add_node(is_folder=False))
        btn_new_dir.bind(on_release=lambda *_: self._add_node(is_folder=True))
        btn_rename.bind(on_release=lambda *_: self._rename_node())
        btn_delete.bind(on_release=lambda *_: self._delete_node())
        btn_up.bind(on_release=lambda *_: self._move_node(-1))
        btn_down.bind(on_release=lambda *_: self._move_node(1))
        btn_timeline.bind(on_release=lambda *_: self._show_timeline())
        btn_dash.bind(on_release=lambda *_: self._show_dashboard())
        btn_export.bind(on_release=lambda *_: self._export_txt())
        btn_focus.bind(on_release=lambda *_: self._toggle_focus())

        theme_spinner.bind(text=lambda *_: self._on_theme_mode(theme_spinner.text))
        temp_slider.bind(value=lambda *_: self._on_temp(int(temp_slider.value)))

        # 初始树
        self._rebuild_tree()
        self._open_first_chapter()
        self._apply_theme()

        # 定时自动保存
        Clock.schedule_interval(lambda *_: self._autosave_tick(status), AUTOSAVE_INTERVAL_SECONDS)

        return root

    def _init_project(self) -> None:
        base = ensure_dir(data_root() / "projects" / DEFAULT_PROJECT_NAME)
        self.project_dir = base
        self.store = ProjectStore(base)
        self.version_store = VersionStore(base)
        self.stats_store = StatsStore(base)
        self.knowledge_store = KnowledgeStore(base)

        if self.store.exists():
            proj = self.store.load()
        else:
            proj = self.store.create_default(DEFAULT_PROJECT_NAME)

        self.project_root = proj.root
        self._rebuild_word_cache()

    def _rebuild_tree(self) -> None:
        assert self.tree is not None
        assert self.project_root is not None

        self.tree.clear_tree()

        def add(parent_node, n: ChapterNode):
            tv = TreeViewLabel(text=n.title)
            tv.node_id = n.id  # type: ignore[attr-defined]
            tv.is_folder = bool(n.is_folder)  # type: ignore[attr-defined]
            tv.color = (1, 1, 1, 1)
            new_parent = self.tree.add_node(tv, parent_node)
            for c in n.children:
                add(new_parent, c)

        for c in self.project_root.children:
            add(None, c)


    def _on_tree_touch(self, _tree, touch):
        # 只处理点到节点文本的情况
        for node in self.tree.iterate_all_nodes():
            if not hasattr(node, "collide_point"):
                continue
            if node.collide_point(*touch.pos):
                self._select_node(node)
                if not getattr(node, "is_folder", False):
                    self._open_chapter(getattr(node, "node_id"))
                return False
        return False

    def _select_node(self, node):
        if self.tree is None:
            return
        if self.tree.selected_node is node:
            return
        if self.tree.selected_node is not None:
            try:
                self.tree.selected_node.color = (1, 1, 1, 1)
            except Exception:
                pass
        self.tree.selected_node = node
        try:
            node.color = (0.22, 0.55, 0.85, 1)
        except Exception:
            pass


    def _find_node_by_id(self, node_id: str) -> ChapterNode | None:
        assert self.project_root is not None

        def walk(n: ChapterNode) -> ChapterNode | None:
            for c in n.children:
                if c.id == node_id:
                    return c
                r = walk(c)
                if r:
                    return r
            return None

        return walk(self.project_root)

    def _open_first_chapter(self) -> None:
        assert self.project_root is not None

        def first(n: ChapterNode) -> ChapterNode | None:
            for c in n.children:
                if c.is_folder:
                    r = first(c)
                    if r:
                        return r
                else:
                    return c
            return None

        ch = first(self.project_root)
        if ch is None:
            ch = ChapterNode(id=str(uuid.uuid4()), title="第一章", is_folder=False, children=[])
            self.project_root.children.append(ch)
            self._persist_tree()
            self._rebuild_tree()

        self._open_chapter(ch.id)

    def _open_chapter(self, chapter_id: str) -> None:
        if self._current_chapter_id == chapter_id:
            return
        self._save_current_if_any()

        assert self.store is not None
        assert self.editor is not None

        self._current_chapter_id = chapter_id
        txt = self.store.read_chapter(chapter_id)
        self.editor.text = txt

    def _save_current_if_any(self) -> None:
        if not self._current_chapter_id:
            return
        assert self.store is not None
        assert self.editor is not None

        cid = self._current_chapter_id
        txt = self.editor.text or ""
        self.store.write_chapter(cid, txt)

        wc = word_count(txt)
        old = self._chapter_word_cache.get(cid, 0)
        self._chapter_word_cache[cid] = wc
        self._total_words_cache += (wc - old)

    def _persist_tree(self) -> None:
        assert self.store is not None
        assert self.project_dir is not None
        assert self.project_root is not None

        # 只保存 root 到 project.json
        proj = self.store.load() if self.store.exists() else self.store.create_default(DEFAULT_PROJECT_NAME)
        proj.root = self.project_root
        self.store.save(proj)

    def _rebuild_word_cache(self) -> None:
        assert self.project_root is not None
        assert self.store is not None
        self._chapter_word_cache.clear()

        def walk(n: ChapterNode):
            for c in n.children:
                if c.is_folder:
                    walk(c)
                else:
                    self._chapter_word_cache[c.id] = word_count(self.store.read_chapter(c.id))

        walk(self.project_root)
        self._total_words_cache = sum(self._chapter_word_cache.values())

    def _on_editor_text(self, *_):
        # 即时更新状态栏文本在 autosave_tick 里
        pass

    def _autosave_tick(self, status_label: Label) -> None:
        if not self._current_chapter_id:
            return
        assert self.version_store is not None
        assert self.stats_store is not None
        assert self.editor is not None

        self._save_current_if_any()

        cid = self._current_chapter_id
        txt = self.editor.text or ""
        wc = word_count(txt)

        now = datetime.now().timestamp()
        last_v = self._last_version_ts.get(cid, 0.0)
        if now - last_v >= VERSION_SNAPSHOT_MIN_SECONDS and wc > 0:
            self.version_store.snapshot(cid, txt, wc)
            self._last_version_ts[cid] = now

        if now - self._last_stats_ts >= 60:
            self.stats_store.append_total(total_words=self._total_words_cache, ts=now_iso())
            self._last_stats_ts = now

        status_label.text = f"总字数：{self._total_words_cache}    当前章：{wc}"

    def _open_prompt(self, title: str, hint: str, default: str, on_ok) -> None:
        """异步弹窗：避免阻塞 UI（安卓上更稳）。"""
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        ti = TextInput(text=default, multiline=False, size_hint_y=None, height=dp(38))
        box.add_widget(Label(text=hint, size_hint_y=None, height=dp(24)))
        box.add_widget(ti)
        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        ok_btn = Button(text="确定")
        cancel_btn = Button(text="取消")
        btns.add_widget(ok_btn)
        btns.add_widget(cancel_btn)
        box.add_widget(btns)

        popup = Popup(title=title, content=box, size_hint=(0.86, None), height=dp(220))

        def _ok(*_):
            popup.dismiss()
            on_ok((ti.text or "").strip())

        def _cancel(*_):
            popup.dismiss()

        ok_btn.bind(on_release=_ok)
        cancel_btn.bind(on_release=_cancel)
        popup.open()


    def _add_node(self, is_folder: bool) -> None:
        assert self.project_root is not None
        if self.tree is None:
            return

        def _create(title: str) -> None:
            title2 = title or ("新文件夹" if is_folder else "新章节")
            new_node = ChapterNode(id=str(uuid.uuid4()), title=title2, is_folder=is_folder, children=[])

            # 默认加到根；若当前选中的是文件夹则作为其子节点
            parent_id = None
            if self.tree and self.tree.selected_node is not None and getattr(self.tree.selected_node, "is_folder", False):
                parent_id = getattr(self.tree.selected_node, "node_id")

            if parent_id:
                parent_model = self._find_node_by_id(parent_id)
                if parent_model is not None:
                    parent_model.children.append(new_node)
                else:
                    self.project_root.children.append(new_node)
            else:
                self.project_root.children.append(new_node)

            self._persist_tree()
            self._rebuild_tree()

        self._open_prompt("新建", "标题：", "新文件夹" if is_folder else "新章节", _create)


    def _rename_node(self) -> None:
        if self.tree is None or self.tree.selected_node is None:
            return
        node_id = getattr(self.tree.selected_node, "node_id", None)
        if not node_id:
            return
        m = self._find_node_by_id(node_id)
        if m is None:
            return

        def _apply(title: str) -> None:
            m.title = title or m.title
            self._persist_tree()
            self._rebuild_tree()

        self._open_prompt("重命名", "标题：", m.title, _apply)


    def _delete_node(self) -> None:
        if self.tree is None or self.tree.selected_node is None:
            return
        node_id = getattr(self.tree.selected_node, "node_id", None)
        if not node_id:
            return
        assert self.project_root is not None
        assert self.store is not None

        # 简化：直接删除模型树中的节点
        removed_ids: list[str] = []

        def remove_from(parent: ChapterNode) -> bool:
            for i, c in enumerate(list(parent.children)):
                if c.id == node_id:
                    removed_ids.extend(self._collect_leaf_ids(c))
                    parent.children.pop(i)
                    return True
                if remove_from(c):
                    return True
            return False

        remove_from(self.project_root)
        self._persist_tree()
        self._rebuild_tree()

        # 删除章节文件
        for cid in removed_ids:
            try:
                p = self.store.chapter_path(cid)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        if self._current_chapter_id in removed_ids:
            self._current_chapter_id = None
            if self.editor:
                self.editor.text = ""
            self._open_first_chapter()

    def _collect_leaf_ids(self, n: ChapterNode) -> list[str]:
        out: list[str] = []
        if not n.is_folder:
            out.append(n.id)
        for c in n.children:
            out.extend(self._collect_leaf_ids(c))
        return out

    def _move_node(self, delta: int) -> None:
        # 仅支持同一父级内上移/下移
        if self.tree is None or self.tree.selected_node is None:
            return
        node_id = getattr(self.tree.selected_node, "node_id", None)
        if not node_id:
            return
        assert self.project_root is not None

        def move_in(parent: ChapterNode) -> bool:
            for i, c in enumerate(parent.children):
                if c.id == node_id:
                    j = i + delta
                    if j < 0 or j >= len(parent.children):
                        return True
                    parent.children[i], parent.children[j] = parent.children[j], parent.children[i]
                    return True
            for c in parent.children:
                if move_in(c):
                    return True
            return False

        if move_in(self.project_root):
            self._persist_tree()
            self._rebuild_tree()

    def _toggle_focus(self) -> None:
        if self.left_panel is None:
            return
        self.root_layout.focus_mode = not self.root_layout.focus_mode  # type: ignore[union-attr]
        if self.root_layout.focus_mode:  # type: ignore[union-attr]
            self.left_panel.width = dp(0)
            self.left_panel.opacity = 0
        else:
            self.left_panel.width = dp(260)
            self.left_panel.opacity = 1

    def _on_theme_mode(self, text: str) -> None:
        if text == "夜间":
            self.theme.mode = "night"
        elif text == "护眼":
            self.theme.mode = "eye"
        else:
            self.theme.mode = "light"
        self._apply_theme()

    def _on_temp(self, v: int) -> None:
        self.theme.temperature = int(v)
        self._apply_theme()

    def _apply_theme(self) -> None:
        colors = temperature_to_colors(self.theme.temperature, self.theme.mode)
        Window.clearcolor = hex_to_rgba(colors.bg, 1.0)
        if self.editor is not None:
            self.editor.background_color = hex_to_rgba(colors.bg, 1.0)
            self.editor.foreground_color = hex_to_rgba(colors.fg, 1.0)
            self.editor.cursor_color = hex_to_rgba(colors.fg, 1.0)

    def _show_timeline(self) -> None:
        if not self._current_chapter_id:
            return
        assert self.version_store is not None

        entries = self.version_store.list_versions(self._current_chapter_id)

        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(Label(text="时间轴（点选后可预览/回溯）", size_hint_y=None, height=dp(26)))

        list_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        list_box.bind(minimum_height=list_box.setter("height"))

        selected: dict[str, VersionEntry | None] = {"v": None}

        def choose(e: VersionEntry):
            selected["v"] = e

        for e in entries[:50]:
            b = Button(text=f"{e.created_at} · {e.word_count}字", size_hint_y=None, height=dp(42))
            b.bind(on_release=lambda _btn, ee=e: choose(ee))
            list_box.add_widget(b)

        sv = ScrollView()
        sv.add_widget(list_box)
        box.add_widget(sv)

        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        b_prev = Button(text="预览")
        b_restore = Button(text="回溯")
        btns.add_widget(b_prev)
        btns.add_widget(b_restore)
        box.add_widget(btns)

        popup = Popup(title="时间轴", content=box, size_hint=(0.92, 0.92))

        def _preview(*_):
            e = selected["v"]
            if not e:
                return
            txt = self.version_store.read_version(e)  # type: ignore[union-attr]
            prev = "\n".join((txt or "").splitlines()[:200])
            Popup(title="预览", content=Label(text=prev or "（空）"), size_hint=(0.9, 0.9)).open()

        def _restore(*_):
            e = selected["v"]
            if not e:
                return
            txt = self.version_store.read_version(e)  # type: ignore[union-attr]
            if self.editor is not None:
                self.editor.text = txt
            self._save_current_if_any()
            wc = word_count(txt)
            self.version_store.snapshot(self._current_chapter_id, txt, wc)  # type: ignore[arg-type]
            popup.dismiss()

        b_prev.bind(on_release=_preview)
        b_restore.bind(on_release=_restore)

        popup.open()

    def _show_dashboard(self) -> None:
        assert self.stats_store is not None
        daily = self.stats_store.daily_progress()
        days = sorted(daily.keys())[-14:]
        vals = [int(daily[d]) for d in days]

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        box.add_widget(Label(text=f"总字数：{self._total_words_cache}", size_hint_y=None, height=dp(26)))
        box.add_widget(Label(text=f"今日进度：{(vals[-1] if vals else 0)}", size_hint_y=None, height=dp(26)))

        chart = BarChart(size_hint_y=None, height=dp(160))
        chart.values = vals
        chart.labels = [d[5:] for d in days]
        chart.redraw()
        box.add_widget(chart)

        # Top10 章节
        top = sorted(self._chapter_word_cache.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = [f"{i+1}. {cid[:8]}…  {wc}字" for i, (cid, wc) in enumerate(top)]
        box.add_widget(Label(text="Top10 章节（按字数）\n" + "\n".join(lines), halign="left"))

        Popup(title="仪表盘", content=box, size_hint=(0.92, 0.92)).open()

    def _export_txt(self) -> None:
        assert self.store is not None
        assert self.project_dir is not None
        assert self.project_root is not None

        # 导出到 data 目录下 exports
        export_dir = ensure_dir(self.project_dir / "exports")
        out_path = export_dir / f"{DEFAULT_PROJECT_NAME}_{now_iso().replace(':', '-')}.txt"

        proj = self.store.load() if self.store.exists() else self.store.create_default(DEFAULT_PROJECT_NAME)
        proj.root = self.project_root

        try:
            TxtExporter().export(ExportContext(project=proj, store=self.store), out_path)
            Popup(title="导出完成", content=Label(text=f"已导出到：\n{out_path}"), size_hint=(0.9, None), height=dp(220)).open()
        except Exception as e:
            Popup(title="导出失败", content=Label(text=str(e)), size_hint=(0.9, None), height=dp(220)).open()


if __name__ == "__main__":
    NovelMobileApp().run()
