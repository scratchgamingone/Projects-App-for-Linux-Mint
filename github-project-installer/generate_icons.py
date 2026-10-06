#!/usr/bin/env python3
"""
Generate high-resolution SVG and multi-resolution PNG icons for GitHub Project Installer.
Uses Cairo vector graphics to render pixel-perfect icons.
"""

import os
import math
import cairo

ASSETS_DIR = "/home/sam/Projects/github-project-installer/src/github_project_installer/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

SVG_PATH = os.path.join(ASSETS_DIR, "github-project-installer.svg")

# Scalable SVG
SVG_CONTENT = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="60%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0a0e17"/>
    </linearGradient>

    <linearGradient id="mintGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#34d399"/>
      <stop offset="50%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>

    <linearGradient id="cyanGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>
    
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="16" stdDeviation="16" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
  </defs>

  <!-- Squircle Base -->
  <rect x="24" y="24" width="464" height="464" rx="104" fill="url(#bgGrad)" stroke="#334155" stroke-width="6" filter="url(#shadow)"/>
  <rect x="34" y="34" width="444" height="444" rx="94" fill="none" stroke="#ffffff" stroke-width="2" stroke-opacity="0.08"/>

  <!-- Folder Backing -->
  <path d="M 100,165 L 205,165 L 235,195 L 412,195 A 18 18 0 0 1 430,213 L 430,375 A 18 18 0 0 1 412,393 L 100,393 A 18 18 0 0 1 82,375 L 82,183 A 18 18 0 0 1 100,165 Z" fill="#1e293b" stroke="#475569" stroke-width="5"/>

  <!-- GitHub Inverted Mark (White Disc + Dark Octocat) -->
  <circle cx="256" cy="165" r="72" fill="#ffffff" stroke="#38bdf8" stroke-width="4"/>
  <g transform="translate(256, 165) scale(0.48)">
    <path d="M 0,-85 C -55,-85 -100,-40 -100,15 C -100,59 -71,96 -32,109 C -27,110 -25,107 -25,104 L -25,86 C -53,92 -59,72 -59,72 C -63,61 -70,58 -70,58 C -79,52 -69,52 -69,52 C -59,53 -54,62 -54,62 C -45,77 -30,73 -25,70 C -24,63 -21,59 -18,56 C -40,53 -63,44 -63,6 C -63,-5 -59,-14 -52,-21 C -53,-24 -57,-34 -51,-47 C -51,-47 -43,-50 -25,-38 C -17,-40 -9,-41 0,-41 C 9,-41 17,-40 25,-38 C 43,-50 51,-47 51,-47 C 57,-34 53,-24 52,-21 C 59,-14 63,-5 63,6 C 63,44 40,53 18,56 C 22,59 25,65 25,74 L 25,104 C 25,107 27,110 32,109 C 71,96 100,59 100,15 C 100,-40 55,-85 0,-85 Z" fill="#0f172a"/>
  </g>

  <!-- Big Emerald Download Arrow -->
  <path d="M 226,260 L 286,260 L 286,335 L 340,335 L 256,415 L 172,335 L 226,335 Z" fill="url(#mintGrad)" stroke="#6ee7b7" stroke-width="4" stroke-linejoin="round"/>

  <!-- Code Bracket Highlights: < > -->
  <path d="M 150,285 L 115,315 L 150,345" fill="none" stroke="url(#cyanGrad)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M 362,285 L 397,315 L 362,345" fill="none" stroke="url(#cyanGrad)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''

with open(SVG_PATH, "w") as f:
    f.write(SVG_CONTENT)
print(f"✓ Saved SVG: {SVG_PATH}")


def draw_squircle(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw_icon_surface(size):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surface)
    scale = size / 512.0
    cr.scale(scale, scale)

    # 1. Background Squircle
    draw_squircle(cr, 24, 24, 464, 464, 104)
    bg_pat = cairo.LinearGradient(24, 24, 488, 488)
    bg_pat.add_color_stop_rgb(0, 0.06, 0.09, 0.16)   # #0f172a
    bg_pat.add_color_stop_rgb(0.6, 0.12, 0.16, 0.23) # #1e293b
    bg_pat.add_color_stop_rgb(1, 0.04, 0.05, 0.09)   # #0a0e17
    cr.set_source(bg_pat)
    cr.fill_preserve()

    # Border
    cr.set_source_rgb(0.20, 0.25, 0.33)  # #334155
    cr.set_line_width(6)
    cr.stroke()

    # Inner faint border
    if size >= 32:
        draw_squircle(cr, 34, 34, 444, 444, 94)
        cr.set_source_rgba(1, 1, 1, 0.08)
        cr.set_line_width(2)
        cr.stroke()

    # 2. Folder Silhouette
    cr.save()
    cr.move_to(100, 165)
    cr.line_to(205, 165)
    cr.line_to(235, 195)
    cr.line_to(412, 195)
    cr.arc(412, 213, 18, -math.pi / 2, 0)
    cr.line_to(430, 375)
    cr.arc(412, 375, 18, 0, math.pi / 2)
    cr.line_to(100, 393)
    cr.arc(100, 375, 18, math.pi / 2, math.pi)
    cr.line_to(82, 183)
    cr.arc(100, 183, 18, math.pi, 3 * math.pi / 2)
    cr.close_path()

    cr.set_source_rgb(0.12, 0.16, 0.23)
    cr.fill_preserve()
    cr.set_source_rgb(0.28, 0.33, 0.41)
    cr.set_line_width(5)
    cr.stroke()
    cr.restore()

    # 3. GitHub Disc & Octocat Silhouette
    cr.save()
    cr.arc(256, 165, 70, 0, 2 * math.pi)
    cr.set_source_rgb(1, 1, 1)
    cr.fill_preserve()
    cr.set_source_rgb(0.22, 0.74, 0.97)  # #38bdf8
    cr.set_line_width(5)
    cr.stroke()

    # Octocat Head Silhouette
    cr.save()
    cr.translate(256, 165)
    cr.scale(0.48, 0.48)
    cr.arc(0, 10, 48, 0, 2 * math.pi)
    cr.set_source_rgb(0.06, 0.09, 0.16)
    cr.fill()
    # Ears
    cr.move_to(-35, -15)
    cr.line_to(-48, -55)
    cr.line_to(-12, -35)
    cr.close_path()
    cr.fill()
    cr.move_to(35, -15)
    cr.line_to(48, -55)
    cr.line_to(12, -35)
    cr.close_path()
    cr.fill()
    cr.restore()
    cr.restore()

    # 4. Big Download / Install Arrow
    cr.save()
    cr.move_to(226, 260)
    cr.line_to(286, 260)
    cr.line_to(286, 335)
    cr.line_to(340, 335)
    cr.line_to(256, 415)
    cr.line_to(172, 335)
    cr.line_to(226, 335)
    cr.close_path()

    arrow_pat = cairo.LinearGradient(256, 260, 256, 415)
    arrow_pat.add_color_stop_rgb(0, 0.20, 0.83, 0.60)   # #34d399 (Mint)
    arrow_pat.add_color_stop_rgb(0.5, 0.06, 0.73, 0.51) # #10b981
    arrow_pat.add_color_stop_rgb(1, 0.02, 0.59, 0.41)   # #059669
    cr.set_source(arrow_pat)
    cr.fill_preserve()

    cr.set_source_rgb(0.43, 0.91, 0.72)  # #6ee7b7
    cr.set_line_width(4)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.stroke()
    cr.restore()

    # 5. Code Brackets < >
    if size >= 32:
        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_width(12)
        cr.set_source_rgb(0.22, 0.74, 0.97)

        # <
        cr.move_to(150, 285)
        cr.line_to(115, 315)
        cr.line_to(150, 345)
        cr.stroke()

        # >
        cr.move_to(362, 285)
        cr.line_to(397, 315)
        cr.line_to(362, 345)
        cr.stroke()
        cr.restore()

    return surface


sizes = [16, 24, 32, 48, 64, 128, 256, 512]
for s in sizes:
    surf = draw_icon_surface(s)
    out_path = os.path.join(ASSETS_DIR, f"icon-{s}.png")
    surf.write_to_png(out_path)
    print(f"✓ Rendered icon-{s}.png")

# Main 256x256 app png
main_png = os.path.join(ASSETS_DIR, "github-project-installer.png")
surf_main = draw_icon_surface(256)
surf_main.write_to_png(main_png)
print(f"✓ Rendered main application PNG: {main_png}")
