"""
Interactive Sunburst Chart rendered with high performance vector Cairo.
Inspired by SquirrelDisk: multi-level concentric rings, click-to-zoom,
smooth anti-aliased geometry, and hover inspection HUD.
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

# Modern cohesive palette for sunburst sectors
PALETTE = [
    (0.99, 0.42, 0.42),  # Coral
    (0.13, 0.79, 0.59),  # Teal
    (0.30, 0.59, 1.00),  # Royal Blue
    (1.00, 0.72, 0.01),  # Amber
    (0.61, 0.36, 0.90),  # Violet
    (0.18, 0.77, 0.71),  # Emerald
    (0.95, 0.36, 0.71),  # Pink
    (0.00, 0.73, 0.98),  # Cyan
    (0.98, 0.52, 0.00),  # Orange
    (0.50, 0.73, 0.09),  # Lime
    (0.40, 0.49, 0.92),  # Indigo
    (0.85, 0.28, 0.54),  # Magenta
]


class Sector:
    """Represents a drawable sector on the sunburst."""
    __slots__ = ('node', 'ring', 'start_angle', 'end_angle', 'inner_r', 'outer_r', 'color', 'is_center')

    def __init__(self, node: FileNode, ring: int, start_angle: float, end_angle: float,
                 inner_r: float, outer_r: float, color: Tuple[float, float, float], is_center: bool = False):
        self.node = node
        self.ring = ring
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.inner_r = inner_r
        self.outer_r = outer_r
        self.color = color
        self.is_center = is_center

    def contains(self, r: float, theta: float) -> bool:
        if self.is_center:
            return r <= self.outer_r
        if not (self.inner_r <= r <= self.outer_r):
            return False
        # Normalize theta to [0, 2pi)
        while theta < 0:
            theta += 2 * math.pi
        while theta >= 2 * math.pi:
            theta -= 2 * math.pi
        return self.start_angle <= theta <= self.end_angle


class SunburstView(Gtk.DrawingArea):
    """Vector Cairo Sunburst Chart."""

    def __init__(self, on_navigate: Callable[[FileNode], None]):
        super().__init__()
        self.on_navigate = on_navigate
        self.current_node: Optional[FileNode] = None
        self.sectors: List[Sector] = []
        self.hovered_sector: Optional[Sector] = None
        self.cx = 0.0
        self.cy = 0.0
        self.max_radius = 0.0

        # Enable pointer events
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
        """Set the root node to display in the sunburst."""
        self.current_node = node
        self.hovered_sector = None
        self.queue_draw()

    def _build_layout(self, width: float, height: float) -> None:
        self.sectors.clear()
        if not self.current_node or self.current_node.size <= 0:
            return

        self.cx = width / 2.0
        self.cy = height / 2.0
        self.max_radius = min(self.cx, self.cy) - 20.0
        if self.max_radius < 50.0:
            return

        center_r = self.max_radius * 0.24
        ring_thickness = (self.max_radius - center_r) / 3.0

        # Center sector (current node)
        center_sec = Sector(
            node=self.current_node,
            ring=0,
            start_angle=0.0,
            end_angle=2 * math.pi,
            inner_r=0.0,
            outer_r=center_r,
            color=(0.18, 0.22, 0.28),
            is_center=True
        )
        self.sectors.append(center_sec)

        # Allocate sectors for up to 3 levels
        total_size = float(self.current_node.size)
        current_angle = 0.0

        for idx, child in enumerate(self.current_node.children):
            if child.size <= 0:
                continue
            span = (child.size / total_size) * 2 * math.pi
            if span < 0.015:  # Below 0.85 degrees, omit to prevent clutter
                continue

            base_color = PALETTE[idx % len(PALETTE)]
            # Level 1 sector
            sec1 = Sector(
                node=child,
                ring=1,
                start_angle=current_angle,
                end_angle=current_angle + span,
                inner_r=center_r + 3.0,
                outer_r=center_r + ring_thickness,
                color=base_color
            )
            self.sectors.append(sec1)

            # Level 2 sectors
            if child.is_dir and len(child.children) > 0 and child.size > 0:
                self._build_subsectors(
                    parent_node=child,
                    ring=2,
                    start_angle=current_angle,
                    total_span=span,
                    inner_r=center_r + ring_thickness + 3.0,
                    outer_r=center_r + ring_thickness * 2.0,
                    base_color=base_color,
                    max_levels=2
                )

            current_angle += span

    def _build_subsectors(self, parent_node: FileNode, ring: int,
                          start_angle: float, total_span: float,
                          inner_r: float, outer_r: float,
                          base_color: Tuple[float, float, float],
                          max_levels: int) -> None:
        parent_size = float(parent_node.size)
        if parent_size <= 0:
            return

        curr_a = start_angle
        # Vary tint slightly for subsectors
        r, g, b = base_color
        tint_factor = 0.85 if ring == 2 else 0.70
        sub_color = (
            min(1.0, r * tint_factor + (1.0 - tint_factor) * 0.9),
            min(1.0, g * tint_factor + (1.0 - tint_factor) * 0.9),
            min(1.0, b * tint_factor + (1.0 - tint_factor) * 0.9)
        )

        for child in parent_node.children:
            if child.size <= 0:
                continue
            c_span = (child.size / parent_size) * total_span
            if c_span < 0.015:
                continue

            sec = Sector(
                node=child,
                ring=ring,
                start_angle=curr_a,
                end_angle=curr_a + c_span,
                inner_r=inner_r,
                outer_r=outer_r,
                color=sub_color
            )
            self.sectors.append(sec)

            if ring < max_levels and child.is_dir and len(child.children) > 0:
                ring_thickness = (self.max_radius - (self.max_radius * 0.24)) / 3.0
                self._build_subsectors(
                    parent_node=child,
                    ring=ring + 1,
                    start_angle=curr_a,
                    total_span=c_span,
                    inner_r=outer_r + 3.0,
                    outer_r=outer_r + ring_thickness,
                    base_color=base_color,
                    max_levels=max_levels
                )

            curr_a += c_span

    def _on_draw(self, widget: Gtk.DrawingArea, cr: cairo.Context) -> bool:
        alloc = self.get_allocation()
        width = float(alloc.width)
        height = float(alloc.height)

        # Clear background (sleek dark canvas)
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

        # Render all sectors
        for sec in self.sectors:
            is_hovered = (sec == self.hovered_sector)
            self._draw_sector(cr, sec, is_hovered)

        # Render center information
        self._draw_center_info(cr)

        # Render floating inspection HUD if hovered
        if self.hovered_sector and not self.hovered_sector.is_center:
            self._draw_hud(cr, width, height, self.hovered_sector)

        return True

    def _draw_sector(self, cr: cairo.Context, sec: Sector, is_hovered: bool) -> None:
        if sec.is_center:
            cr.arc(self.cx, self.cy, sec.outer_r, 0, 2 * math.pi)
            if is_hovered:
                cr.set_source_rgb(0.24, 0.28, 0.35)
            else:
                cr.set_source_rgb(*sec.color)
            cr.fill_preserve()
            cr.set_source_rgba(0.4, 0.5, 0.6, 0.5)
            cr.set_line_width(1.5)
            cr.stroke()
            return

        cr.new_path()
        cr.arc(self.cx, self.cy, sec.outer_r, sec.start_angle, sec.end_angle)
        cr.arc_negative(self.cx, self.cy, sec.inner_r, sec.end_angle, sec.start_angle)
        cr.close_path()

        r, g, b = sec.color
        if is_hovered:
            # Highlight with increased brightness
            cr.set_source_rgb(min(1.0, r * 1.3), min(1.0, g * 1.3), min(1.0, b * 1.3))
        else:
            cr.set_source_rgb(r, g, b)
        cr.fill_preserve()

        # Sector boundary
        if is_hovered:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
            cr.set_line_width(2.5)
        else:
            cr.set_source_rgba(0.12, 0.14, 0.17, 0.8)
            cr.set_line_width(1.2)
        cr.stroke()

    def _draw_center_info(self, cr: cairo.Context) -> None:
        if not self.current_node:
            return

        cr.save()
        center_r = self.max_radius * 0.24

        # Clip inside center circle
        cr.arc(self.cx, self.cy, center_r - 2.0, 0, 2 * math.pi)
        cr.clip()

        # Current folder title
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.set_source_rgb(0.95, 0.95, 0.98)
        title = self.current_node.name if self.current_node.name else "/"
        if len(title) > 16:
            title = title[:14] + "…"
        ext1 = cr.text_extents(title)
        cr.move_to(self.cx - ext1.width / 2.0, self.cy - 12.0)
        cr.show_text(title)

        # Total size
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(15)
        cr.set_source_rgb(0.35, 0.85, 0.65)  # Mint Green
        sz_text = self.current_node.human_size
        ext2 = cr.text_extents(sz_text)
        cr.move_to(self.cx - ext2.width / 2.0, self.cy + 8.0)
        cr.show_text(sz_text)

        # Sub items count
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.set_source_rgb(0.65, 0.70, 0.75)
        if self.current_node.is_dir:
            cnt_text = f"{self.current_node.file_count:,} files"
        else:
            cnt_text = "File"
        ext3 = cr.text_extents(cnt_text)
        cr.move_to(self.cx - ext3.width / 2.0, self.cy + 24.0)
        cr.show_text(cnt_text)

        # Hint to zoom out
        if self.current_node.parent:
            cr.set_font_size(9)
            cr.set_source_rgba(0.5, 0.6, 0.7, 0.8)
            hint = "▲ Click to Go Up"
            eh = cr.text_extents(hint)
            cr.move_to(self.cx - eh.width / 2.0, self.cy + 38.0)
            cr.show_text(hint)

        cr.restore()

    def _draw_hud(self, cr: cairo.Context, width: float, height: float, sec: Sector) -> None:
        """Render floating inspection card for hovered item."""
        node = sec.node
        total_size = float(self.current_node.size) if self.current_node else 1.0
        pct = (node.size / total_size * 100.0) if total_size > 0 else 0.0

        # Card dimensions
        card_w = 260.0
        card_h = 105.0
        margin = 14.0
        card_x = width - card_w - margin
        card_y = margin

        # Draw card background
        cr.save()
        cr.set_source_rgba(0.08, 0.10, 0.13, 0.92)
        # Rounded rectangle
        rad = 8.0
        cr.new_sub_path()
        cr.arc(card_x + card_w - rad, card_y + rad, rad, -math.pi / 2, 0)
        cr.arc(card_x + card_w - rad, card_y + card_h - rad, rad, 0, math.pi / 2)
        cr.arc(card_x + rad, card_y + card_h - rad, rad, math.pi / 2, math.pi)
        cr.arc(card_x + rad, card_y + rad, rad, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.fill_preserve()

        # Border colored with sector color
        cr.set_source_rgba(sec.color[0], sec.color[1], sec.color[2], 0.8)
        cr.set_line_width(2.0)
        cr.stroke()

        # Text inside HUD
        # Name
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        disp_name = node.name
        if len(disp_name) > 28:
            disp_name = disp_name[:26] + "…"
        cr.move_to(card_x + 12.0, card_y + 24.0)
        cr.show_text(disp_name)

        # Size & Percentage
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        cr.set_source_rgb(0.35, 0.85, 0.65)
        cr.move_to(card_x + 12.0, card_y + 48.0)
        cr.show_text(f"{node.human_size}  ({pct:.1f}%)")

        # Type & Count
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.set_source_rgb(0.75, 0.80, 0.85)
        type_str = f"Folder ({node.file_count:,} files, {node.dir_count:,} subdirs)" if node.is_dir else f"File ({node.category})"
        cr.move_to(card_x + 12.0, card_y + 68.0)
        cr.show_text(type_str)

        # Full path
        cr.set_font_size(9)
        cr.set_source_rgb(0.55, 0.60, 0.65)
        short_path = node.path
        if len(short_path) > 38:
            short_path = "…" + short_path[-36:]
        cr.move_to(card_x + 12.0, card_y + 88.0)
        cr.show_text(short_path)

        cr.restore()

    def _find_sector_at(self, x: float, y: float) -> Optional[Sector]:
        dx = x - self.cx
        dy = y - self.cy
        r = math.sqrt(dx * dx + dy * dy)
        theta = math.atan2(dy, dx)
        if theta < 0:
            theta += 2 * math.pi

        for sec in reversed(self.sectors):
            if sec.contains(r, theta):
                return sec
        return None

    def _on_motion(self, widget: Gtk.DrawingArea, event: Gdk.EventMotion) -> bool:
        sec = self._find_sector_at(event.x, event.y)
        if sec != self.hovered_sector:
            self.hovered_sector = sec
            self.queue_draw()
        return True

    def _on_leave(self, widget: Gtk.DrawingArea, event: Gdk.EventCrossing) -> bool:
        if self.hovered_sector is not None:
            self.hovered_sector = None
            self.queue_draw()
        return True

    def _on_button_press(self, widget: Gtk.DrawingArea, event: Gdk.EventButton) -> bool:
        sec = self._find_sector_at(event.x, event.y)
        if not sec:
            return False

        if event.button == 1:  # Left click
            if sec.is_center:
                # Zoom out to parent
                if self.current_node and self.current_node.parent:
                    self.on_navigate(self.current_node.parent)
            else:
                if sec.node.is_dir:
                    self.on_navigate(sec.node)
            return True

        elif event.button == 3:  # Right click context menu
            self._show_context_menu(sec.node, event)
            return True

        return False

    def _show_context_menu(self, node: FileNode, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        # Open
        item_open = Gtk.MenuItem(label=f"Open {'Folder' if node.is_dir else 'File'}")
        item_open.connect('activate', lambda _: subprocess.Popen(['xdg-open', node.path]))
        menu.append(item_open)

        # Open in File Manager
        item_fm = Gtk.MenuItem(label="Open Containing Folder")
        target_dir = node.path if node.is_dir else os.path.dirname(node.path)
        item_fm.connect('activate', lambda _: subprocess.Popen(['xdg-open', target_dir]))
        menu.append(item_fm)

        # Copy Path
        item_copy = Gtk.MenuItem(label="Copy Path")
        def copy_path(_):
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(node.path, -1)
        item_copy.connect('activate', copy_path)
        menu.append(item_copy)

        menu.append(Gtk.SeparatorMenuItem())

        # Trash
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
