"""
Interactive Squarified Treemap rendered with vector Cairo.
Another visual mode inspired by SquirrelDisk: displays hierarchical space
partitioning with high area efficiency and intuitive drill-down.
"""

import math
import os
import subprocess
from typing import Optional, List, Dict, Tuple, Any, Callable
import cairo
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from statdisk.tree_model import FileNode, format_bytes
from statdisk.ui.sunburst_view import PALETTE


class TreemapRect:
    """Represents a laid-out rectangle in the treemap."""
    __slots__ = ('node', 'x', 'y', 'w', 'h', 'color', 'depth')

    def __init__(self, node: FileNode, x: float, y: float, w: float, h: float,
                 color: Tuple[float, float, float], depth: int):
        self.node = node
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.color = color
        self.depth = depth

    def contains(self, px: float, py: float) -> bool:
        return (self.x <= px <= self.x + self.w) and (self.y <= py <= self.y + self.h)


class TreemapView(Gtk.DrawingArea):
    """Vector Cairo Squarified Treemap Chart."""

    def __init__(self, on_navigate: Callable[[FileNode], None]):
        super().__init__()
        self.on_navigate = on_navigate
        self.current_node: Optional[FileNode] = None
        self.rects: List[TreemapRect] = []
        self.hovered_rect: Optional[TreemapRect] = None

        self.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.LEAVE_NOTIFY_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK
        )

        self.connect('draw', self._on_draw)
        self.connect('motion-notify-event', self._on_motion)
        self.connect('leave-notify-event', self._on_leave)
        self.connect('button-press-event', self._on_button_press)

    def set_node(self, node: Optional[FileNode]) -> None:
        self.current_node = node
        self.hovered_rect = None
        self.queue_draw()

    def _build_layout(self, width: float, height: float) -> None:
        self.rects.clear()
        if not self.current_node or self.current_node.size <= 0:
            return

        padding = 10.0
        x = padding
        y = padding
        w = max(10.0, width - 2 * padding)
        h = max(10.0, height - 2 * padding)

        self._squarify_node(self.current_node, x, y, w, h, depth=0, parent_color=None)

    def _squarify_node(self, node: FileNode, x: float, y: float, w: float, h: float,
                        depth: int, parent_color: Optional[Tuple[float, float, float]]) -> None:
        if w < 10 or h < 10 or node.size <= 0:
            return

        valid_children = [c for c in node.children if c.size > 0]
        if not valid_children:
            return

        total_size = float(sum(c.size for c in valid_children))
        total_area = w * h

        # Normalize sizes to areas
        items = []
        for i, c in enumerate(valid_children):
            c_area = (c.size / total_size) * total_area
            if depth == 0:
                color = PALETTE[i % len(PALETTE)]
            else:
                # Tint parent color
                pr, pg, pb = parent_color if parent_color else (0.4, 0.6, 0.8)
                factor = 0.88
                color = (min(1.0, pr * factor), min(1.0, pg * factor), min(1.0, pb * factor))
            items.append((c, c_area, color))

        # Lay out items using squarified layout
        self._squarify_partition(items, x, y, w, h, depth)

    def _squarify_partition(self, items: List[Tuple[FileNode, float, Tuple[float, float, float]]],
                             x: float, y: float, w: float, h: float, depth: int) -> None:
        if not items:
            return

        if len(items) == 1:
            node, _, color = items[0]
            rect = TreemapRect(node, x, y, w, h, color, depth)
            self.rects.append(rect)
            if depth < 1 and node.is_dir and w > 60 and h > 60:
                self._squarify_node(node, x + 3, y + 20, w - 6, h - 23, depth + 1, color)
            return

        # Determine split orientation (split along shorter dimension)
        total_area = sum(it[1] for it in items)
        if total_area <= 0:
            return

        half_area = total_area / 2.0
        acc = 0.0
        split_idx = 1
        for idx, it in enumerate(items):
            acc += it[1]
            if acc >= half_area:
                split_idx = max(1, idx)
                break

        left_items = items[:split_idx]
        right_items = items[split_idx:]
        left_area = sum(it[1] for it in left_items)
        ratio = left_area / total_area if total_area > 0 else 0.5

        if w >= h:
            # Vertical split
            w_left = max(1.0, w * ratio)
            w_right = max(1.0, w - w_left)
            self._squarify_partition(left_items, x, y, w_left, h, depth)
            self._squarify_partition(right_items, x + w_left, y, w_right, h, depth)
        else:
            # Horizontal split
            h_top = max(1.0, h * ratio)
            h_bot = max(1.0, h - h_top)
            self._squarify_partition(left_items, x, y, w, h_top, depth)
            self._squarify_partition(right_items, x, y + h_top, w, h_bot, depth)

    def _on_draw(self, widget: Gtk.DrawingArea, cr: cairo.Context) -> bool:
        alloc = self.get_allocation()
        width = float(alloc.width)
        height = float(alloc.height)

        # Background
        cr.set_source_rgb(0.12, 0.14, 0.17)
        cr.paint()

        if not self.current_node:
            cr.set_source_rgb(0.6, 0.65, 0.7)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(15)
            msg = "Select a folder or drive to scan..."
            ext = cr.text_extents(msg)
            cr.move_to((width - ext.width) / 2.0, height / 2.0)
            cr.show_text(msg)
            return True

        self._build_layout(width, height)

        # Render rectangles
        for rect in self.rects:
            is_hovered = (rect == self.hovered_rect)
            self._draw_rect(cr, rect, is_hovered)

        # Render HUD if hovered
        if self.hovered_rect:
            self._draw_hud(cr, width, height, self.hovered_rect)

        return True

    def _draw_rect(self, cr: cairo.Context, rect: TreemapRect, is_hovered: bool) -> None:
        r, g, b = rect.color
        cr.rectangle(rect.x + 1, rect.y + 1, max(1, rect.w - 2), max(1, rect.h - 2))

        if is_hovered:
            cr.set_source_rgb(min(1.0, r * 1.3), min(1.0, g * 1.3), min(1.0, b * 1.3))
        else:
            cr.set_source_rgb(r, g, b)
        cr.fill_preserve()

        if is_hovered:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.set_line_width(2.5)
        else:
            cr.set_source_rgba(0.08, 0.10, 0.12, 0.7)
            cr.set_line_width(1.0)
        cr.stroke()

        # Label inside rectangle if space permits
        if rect.w > 48 and rect.h > 26:
            cr.save()
            cr.rectangle(rect.x + 2, rect.y + 2, rect.w - 4, rect.h - 4)
            cr.clip()

            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(min(11, max(9, int(rect.h * 0.2))))
            cr.set_source_rgb(1.0, 1.0, 1.0)
            lbl = rect.node.name
            cr.move_to(rect.x + 6, rect.y + min(18, rect.h * 0.45))
            cr.show_text(lbl)

            if rect.h > 42:
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(9)
                cr.set_source_rgba(0.9, 0.9, 0.9, 0.85)
                cr.move_to(rect.x + 6, rect.y + min(32, rect.h * 0.8))
                cr.show_text(rect.node.human_size)

            cr.restore()

    def _draw_hud(self, cr: cairo.Context, width: float, height: float, rect: TreemapRect) -> None:
        node = rect.node
        total_size = float(self.current_node.size) if self.current_node else 1.0
        pct = (node.size / total_size * 100.0) if total_size > 0 else 0.0

        card_w = 260.0
        card_h = 105.0
        margin = 14.0
        card_x = width - card_w - margin
        card_y = margin

        cr.save()
        cr.set_source_rgba(0.08, 0.10, 0.13, 0.92)
        rad = 8.0
        cr.new_sub_path()
        cr.arc(card_x + card_w - rad, card_y + rad, rad, -math.pi / 2, 0)
        cr.arc(card_x + card_w - rad, card_y + card_h - rad, rad, 0, math.pi / 2)
        cr.arc(card_x + rad, card_y + card_h - rad, rad, math.pi / 2, math.pi)
        cr.arc(card_x + rad, card_y + rad, rad, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.fill_preserve()

        cr.set_source_rgba(rect.color[0], rect.color[1], rect.color[2], 0.8)
        cr.set_line_width(2.0)
        cr.stroke()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        disp_name = node.name
        if len(disp_name) > 28:
            disp_name = disp_name[:26] + "…"
        cr.move_to(card_x + 12.0, card_y + 24.0)
        cr.show_text(disp_name)

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        cr.set_source_rgb(0.35, 0.85, 0.65)
        cr.move_to(card_x + 12.0, card_y + 48.0)
        cr.show_text(f"{node.human_size}  ({pct:.1f}%)")

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.set_source_rgb(0.75, 0.80, 0.85)
        type_str = f"Folder ({node.file_count:,} files, {node.dir_count:,} subdirs)" if node.is_dir else f"File ({node.category})"
        cr.move_to(card_x + 12.0, card_y + 68.0)
        cr.show_text(type_str)

        cr.set_font_size(9)
        cr.set_source_rgb(0.55, 0.60, 0.65)
        short_path = node.path
        if len(short_path) > 38:
            short_path = "…" + short_path[-36:]
        cr.move_to(card_x + 12.0, card_y + 88.0)
        cr.show_text(short_path)

        cr.restore()

    def _find_rect_at(self, px: float, py: float) -> Optional[TreemapRect]:
        # Return innermost matching rect (highest depth first)
        for rect in reversed(self.rects):
            if rect.contains(px, py):
                return rect
        return None

    def _on_motion(self, widget: Gtk.DrawingArea, event: Gdk.EventMotion) -> bool:
        r = self._find_rect_at(event.x, event.y)
        if r != self.hovered_rect:
            self.hovered_rect = r
            self.queue_draw()
        return True

    def _on_leave(self, widget: Gtk.DrawingArea, event: Gdk.EventCrossing) -> bool:
        if self.hovered_rect is not None:
            self.hovered_rect = None
            self.queue_draw()
        return True

    def _on_button_press(self, widget: Gtk.DrawingArea, event: Gdk.EventButton) -> bool:
        r = self._find_rect_at(event.x, event.y)
        if not r:
            return False

        if event.button == 1:
            if r.node.is_dir:
                self.on_navigate(r.node)
            return True
        elif event.button == 3:
            self._show_context_menu(r.node, event)
            return True

        return False

    def _show_context_menu(self, node: FileNode, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()
        item_open = Gtk.MenuItem(label=f"Open {'Folder' if node.is_dir else 'File'}")
        item_open.connect('activate', lambda _: subprocess.Popen(['xdg-open', node.path]))
        menu.append(item_open)

        item_fm = Gtk.MenuItem(label="Open Containing Folder")
        target_dir = node.path if node.is_dir else os.path.dirname(node.path)
        item_fm.connect('activate', lambda _: subprocess.Popen(['xdg-open', target_dir]))
        menu.append(item_fm)

        item_copy = Gtk.MenuItem(label="Copy Path")
        def copy_path(_):
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(node.path, -1)
        item_copy.connect('activate', copy_path)
        menu.append(item_copy)

        menu.append(Gtk.SeparatorMenuItem())

        item_trash = Gtk.MenuItem(label="Move to Trash")
        def trash_item(_):
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                message_format=f"Move '{node.name}' to Trash?"
            )
            dialog.format_secondary_text(f"Path: {node.path}\nSize: {node.human_size}")
            res = dialog.run()
            dialog.destroy()
            if res == Gtk.ResponseType.OK:
                subprocess.Popen(['gio', 'trash', node.path])
        item_trash.connect('activate', trash_item)
        menu.append(item_trash)

        menu.show_all()
        menu.popup_at_pointer(event)
