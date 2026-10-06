"""
Generate StatDisk SVG and multi-resolution PNG icons using Cairo.
"""

import os
import math
import cairo

ASSETS_DIR = "/home/sam/statdisk/src/statdisk/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

# 1. Write the scalable SVG
SVG_CONTENT = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
    <linearGradient id="curveGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.2"/>
      <stop offset="50%" stop-color="#34d399" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#a855f7" stop-opacity="0.2"/>
    </linearGradient>
    <linearGradient id="curveStroke" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="50%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#c084fc"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>

  <!-- Rounded Squircle Badge -->
  <rect x="24" y="24" width="464" height="464" rx="104" fill="url(#bgGrad)" stroke="#334155" stroke-width="6" filter="url(#shadow)"/>

  <!-- Concentric Sunburst Sectors -->
  <!-- Outer Ring Sectors -->
  <path d="M 256,76 A 180,180 0 0,1 426,200 L 383,212 A 135,135 0 0,0 256,121 Z" fill="#f87171" opacity="0.9"/>
  <path d="M 426,200 A 180,180 0 0,1 410,360 L 371,334 A 135,135 0 0,0 383,212 Z" fill="#fbbf24" opacity="0.9"/>
  <path d="M 410,360 A 180,180 0 0,1 256,436 L 256,391 A 135,135 0 0,0 371,334 Z" fill="#34d399" opacity="0.9"/>
  <path d="M 256,436 A 180,180 0 0,1 102,360 L 141,334 A 135,135 0 0,0 256,391 Z" fill="#2dd4bf" opacity="0.9"/>
  <path d="M 102,360 A 180,180 0 0,1 86,200 L 129,212 A 135,135 0 0,0 141,334 Z" fill="#38bdf8" opacity="0.9"/>
  <path d="M 86,200 A 180,180 0 0,1 256,76 L 256,121 A 135,135 0 0,0 129,212 Z" fill="#a855f7" opacity="0.9"/>

  <!-- Mid Ring Gap / Grooves -->
  <circle cx="256" cy="256" r="135" fill="none" stroke="#0f172a" stroke-width="4"/>

  <!-- Mid Ring Sectors -->
  <path d="M 256,126 A 130,130 0 0,1 368,190 L 333,210 A 90,90 0 0,0 256,166 Z" fill="#f43f5e" opacity="0.95"/>
  <path d="M 368,190 A 130,130 0 0,1 368,322 L 333,302 A 90,90 0 0,0 333,210 Z" fill="#f59e0b" opacity="0.95"/>
  <path d="M 368,322 A 130,130 0 0,1 256,386 L 256,346 A 90,90 0 0,0 333,302 Z" fill="#10b981" opacity="0.95"/>
  <path d="M 256,386 A 130,130 0 0,1 144,322 L 179,302 A 90,90 0 0,0 256,346 Z" fill="#06b6d4" opacity="0.95"/>
  <path d="M 144,322 A 130,130 0 0,1 144,190 L 179,210 A 90,90 0 0,0 179,302 Z" fill="#6366f1" opacity="0.95"/>
  <path d="M 144,190 A 130,130 0 0,1 256,126 L 256,166 A 90,90 0 0,0 179,210 Z" fill="#8b5cf6" opacity="0.95"/>

  <!-- Inner Center Platter Circle -->
  <circle cx="256" cy="256" r="86" fill="#111827" stroke="#475569" stroke-width="3"/>
  <circle cx="256" cy="256" r="32" fill="#1f2937" stroke="#64748b" stroke-width="2"/>

  <!-- Overlaid Statistical Bell Curve / Normal Distribution Wave -->
  <!-- Filled Area Under Curve -->
  <path d="M 80,380
           C 150,380 180,370 210,290
           C 230,230 240,160 256,160
           C 272,160 282,230 302,290
           C 332,370 362,380 432,380
           L 432,380 L 80,380 Z"
        fill="url(#curveGrad)"/>

  <!-- Bell Curve Stroke -->
  <path d="M 80,380
           C 150,380 180,370 210,290
           C 230,230 240,160 256,160
           C 272,160 282,230 302,290
           C 332,370 362,380 432,380"
        fill="none" stroke="url(#curveStroke)" stroke-width="6" stroke-linecap="round"/>

  <!-- Center Statistics Symbol (Sigma / Acorn motif) -->
  <text x="256" y="266" font-family="DejaVu Sans, Arial, sans-serif" font-size="28" font-weight="bold" fill="#38bdf8" text-anchor="middle" dominant-baseline="middle">σ</text>
</svg>
'''

with open(os.path.join(ASSETS_DIR, "statdisk.svg"), "w", encoding="utf-8") as f:
    f.write(SVG_CONTENT)

print("Created statdisk.svg")

# 2. Render multi-resolution PNGs using Cairo
def draw_icon_surface(size: int) -> cairo.ImageSurface:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surface)
    scale = size / 512.0
    cr.scale(scale, scale)

    # 1. Background squircle
    cr.save()
    x, y, w, h, r = 24, 24, 464, 464, 104
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()

    pat = cairo.LinearGradient(0, 0, 512, 512)
    pat.add_color_stop_rgb(0, 0.06, 0.09, 0.16)
    pat.add_color_stop_rgb(1, 0.12, 0.16, 0.23)
    cr.set_source(pat)
    cr.fill_preserve()

    cr.set_source_rgb(0.20, 0.25, 0.33)
    cr.set_line_width(6.0)
    cr.stroke()
    cr.restore()

    # Center
    cx, cy = 256.0, 256.0

    # 2. Outer Ring Sectors
    sectors = [
        (-math.pi/2, -math.pi/6, (0.97, 0.44, 0.44)),
        (-math.pi/6, math.pi/6, (0.98, 0.75, 0.14)),
        (math.pi/6, math.pi/2, (0.20, 0.83, 0.60)),
        (math.pi/2, 5*math.pi/6, (0.18, 0.83, 0.75)),
        (5*math.pi/6, 7*math.pi/6, (0.22, 0.74, 0.97)),
        (7*math.pi/6, 3*math.pi/2, (0.66, 0.33, 0.97)),
    ]

    for a1, a2, col in sectors:
        cr.new_path()
        cr.arc(cx, cy, 180, a1 + 0.04, a2 - 0.04)
        cr.arc_negative(cx, cy, 135, a2 - 0.04, a1 + 0.04)
        cr.close_path()
        cr.set_source_rgba(col[0], col[1], col[2], 0.9)
        cr.fill()

    # 3. Inner Ring Sectors
    inner_sectors = [
        (-math.pi/2, -math.pi/6, (0.96, 0.25, 0.37)),
        (-math.pi/6, math.pi/6, (0.96, 0.62, 0.04)),
        (math.pi/6, math.pi/2, (0.06, 0.73, 0.51)),
        (math.pi/2, 5*math.pi/6, (0.02, 0.71, 0.83)),
        (5*math.pi/6, 7*math.pi/6, (0.39, 0.40, 0.95)),
        (7*math.pi/6, 3*math.pi/2, (0.55, 0.36, 0.96)),
    ]
    for a1, a2, col in inner_sectors:
        cr.new_path()
        cr.arc(cx, cy, 128, a1 + 0.05, a2 - 0.05)
        cr.arc_negative(cx, cy, 90, a2 - 0.05, a1 + 0.05)
        cr.close_path()
        cr.set_source_rgba(col[0], col[1], col[2], 0.95)
        cr.fill()

    # 4. Center Platter
    cr.arc(cx, cy, 84, 0, 2 * math.pi)
    cr.set_source_rgb(0.07, 0.10, 0.15)
    cr.fill_preserve()
    cr.set_source_rgb(0.28, 0.33, 0.41)
    cr.set_line_width(3.0)
    cr.stroke()

    # Inner spindle
    cr.arc(cx, cy, 32, 0, 2 * math.pi)
    cr.set_source_rgb(0.12, 0.16, 0.22)
    cr.fill_preserve()
    cr.set_source_rgb(0.39, 0.45, 0.55)
    cr.set_line_width(2.0)
    cr.stroke()

    # 5. Overlaid Statistical Bell Curve
    cr.save()
    cr.move_to(80, 380)
    cr.curve_to(150, 380, 180, 370, 210, 290)
    cr.curve_to(230, 230, 240, 160, 256, 160)
    cr.curve_to(272, 160, 282, 230, 302, 290)
    cr.curve_to(332, 370, 362, 380, 432, 380)

    # Stroke curve
    c_pat = cairo.LinearGradient(80, 256, 432, 256)
    c_pat.add_color_stop_rgb(0, 0.22, 0.74, 0.97)
    c_pat.add_color_stop_rgb(0.5, 0.20, 0.83, 0.60)
    c_pat.add_color_stop_rgb(1, 0.75, 0.52, 0.99)
    cr.set_source(c_pat)
    cr.set_line_width(max(2.0, 7.0 * (size / 512.0)))
    cr.stroke()
    cr.restore()

    # 6. Sigma Symbol
    if size >= 32:
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(26)
        cr.set_source_rgb(0.22, 0.74, 0.97)
        ext = cr.text_extents("σ")
        cr.move_to(cx - ext.width / 2.0, cy + ext.height / 2.0)
        cr.show_text("σ")

    return surface

sizes = [16, 24, 32, 48, 64, 128, 256, 512]
for sz in sizes:
    surf = draw_icon_surface(sz)
    out_path = os.path.join(ASSETS_DIR, f"icon-{sz}.png")
    surf.write_to_png(out_path)

# Also create statdisk.png for pixmaps (256x256)
surf_main = draw_icon_surface(256)
surf_main.write_to_png(os.path.join(ASSETS_DIR, "statdisk.png"))

print(f"Generated PNG icons for sizes: {sizes}")
