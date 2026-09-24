#!/usr/bin/env python3
"""Generate compa brand SVGs and optional raster app icons.

Run with ``docs/brand/logo-svg/.venv/bin/python docs/brand/logo-svg/build.py``;
the venv provides ``skia-pathops`` and ``fontTools``.
"""
from math import atan2, cos, degrees, radians, sin
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from pathops import Path as BooleanPath, PathOp, PathPen, op

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "frontend/public/brand"
INK, PAPER, MOSS = "#1E1D1B", "#F7F4EF", "#3E5646"
GAP_CENTER = 30.0
GAP_WIDTH = 40.0
MONO_DIAMETER, MONO_STROKE = 84.0, 84.0 * 0.12
ICON_SIDE, ICON_RADIUS, ICON_DIAMETER, ICON_STROKE = 100.0, 22.0, 62.0, 17.0
TRACKING_EM = 0.05
NOTCH_ANGLE, NOTCH_DEPTH = 30.0, 0.75
NOTCH_MOUTH_OVERSHOOT = 1.15  # mouth points sit outside the o so the chord never leaves an ink sliver
NOTCH_HALF_WIDTH = 14.0  # degrees either side of NOTCH_ANGLE at the mouth
WORDMARK_WEIGHT = 450  # Jost wght axis (tuned to p1-a, 2026-09-24)
FONT = Path(__file__).with_name("Jost[wght].ttf")

def polar(cx, cy, r, deg):
    a = radians(deg)
    return cx + r * sin(a), cy - r * cos(a)

def ring(cx, cy, radius, width, start=GAP_CENTER + GAP_WIDTH / 2, end=360.0 + GAP_CENTER - GAP_WIDTH / 2):
    ro, ri = radius + width / 2, radius - width / 2
    a = polar(cx, cy, ro, start); b = polar(cx, cy, ro, end)
    c = polar(cx, cy, ri, end); d = polar(cx, cy, ri, start)
    return f"M {a[0]:.3f},{a[1]:.3f} A {ro:.3f},{ro:.3f} 0 1 1 {b[0]:.3f},{b[1]:.3f} L {c[0]:.3f},{c[1]:.3f} A {ri:.3f},{ri:.3f} 0 1 0 {d[0]:.3f},{d[1]:.3f} Z"

def angle(cx, cy, point):
    return (degrees(atan2(point[0] - cx, cy - point[1])) % 360.0)

def assert_gap(cx, cy, radius):
    ends = [angle(cx, cy, polar(cx, cy, radius, d)) for d in (GAP_CENTER - GAP_WIDTH / 2, GAP_CENTER + GAP_WIDTH / 2)]
    expected = (GAP_CENTER - GAP_WIDTH / 2, GAP_CENTER + GAP_WIDTH / 2)
    assert all(abs(actual - want) <= 0.1 for actual, want in zip(ends, expected)), ends
    return ends

def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y):
            hit_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < hit_x:
                inside = not inside
    return inside

def svg(viewbox, title, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"><title>{title}</title>{body}</svg>\n'

def monogram():
    path = ring(50, 50, MONO_DIAMETER/2, MONO_STROKE)
    assert_gap(50, 50, MONO_DIAMETER/2 + MONO_STROKE/2)
    x, y = polar(50, 50, MONO_DIAMETER/2, GAP_CENTER)
    return svg("0 0 100 100", "compa monogram", f'<path fill="{INK}" d="{path}"/><circle fill="{MOSS}" cx="{x:.3f}" cy="{y:.3f}" r="{MONO_STROKE*.7:.3f}"/>')

def app_icon():
    path = ring(50, 50, ICON_DIAMETER/2, ICON_STROKE)
    assert_gap(50, 50, ICON_DIAMETER/2 + ICON_STROKE/2)
    return svg("0 0 100 100", "compa app icon", f'<rect width="100" height="100" rx="{ICON_RADIUS}" fill="{INK}"/><path fill="{PAPER}" d="{path}"/>')

def wordmark():
    font = instantiateVariableFont(TTFont(str(FONT)), {"wght": WORDMARK_WEIGHT})
    glyph_set, cmap = font.getGlyphSet(), font.getBestCmap()
    upm = font["head"].unitsPerEm
    asc = font["hhea"].ascent
    tracking = upm * TRACKING_EM
    paths, x, min_x, max_x = [], 0.0, float("inf"), float("-inf")
    min_y, max_y = float("inf"), float("-inf")
    for char in "compa":
        glyph = glyph_set[cmap[ord(char)]]
        pen = SVGPathPen(glyph_set)
        tpen = TransformPen(pen, (1, 0, 0, -1, 0, asc))
        glyph.draw(tpen)
        d = pen.getCommands()
        paths.append((d, x, char))
        bpen = BoundsPen(glyph_set)
        glyph.draw(bpen)
        bounds = bpen.bounds
        if bounds:
            min_x, min_y = min(min_x, x + bounds[0]), min(min_y, asc - bounds[3])
            max_x, max_y = max(max_x, x + bounds[2]), max(max_y, asc - bounds[1])
        x += glyph.width + tracking
    pad = (max_y - min_y) * 0.04
    parts = []
    ty = pad - min_y
    for d, offset, char in paths:
        transform = f"translate({offset - min_x + pad:.3f},{ty:.3f})"
        parts.append(f'<path fill="{INK}" d="{d}" transform="{transform}"/>')
    # Paper-colored wedge cuts the OUTER edge of the o in final SVG coordinates.
    o_glyph = glyph_set[cmap[ord("o")]]
    o_bounds = BoundsPen(glyph_set)
    o_glyph.draw(o_bounds)
    ob0, ob1, ob2, ob3 = o_bounds.bounds
    o_left = next(offset for _, offset, char in paths if char == "o") - min_x + pad + ob0
    o_right = next(offset for _, offset, char in paths if char == "o") - min_x + pad + ob2
    o_top, o_bottom = ty + (asc - ob3), ty + (asc - ob1)
    ocx, ocy = (o_left + o_right) / 2, (o_top + o_bottom) / 2
    outer_r = min(o_right - o_left, o_bottom - o_top) / 2
    stroke_r = outer_r * 0.36
    notch_depth = stroke_r * NOTCH_DEPTH
    mouth_a = polar(ocx, ocy, outer_r * NOTCH_MOUTH_OVERSHOOT, NOTCH_ANGLE - NOTCH_HALF_WIDTH)
    mouth_b = polar(ocx, ocy, outer_r * NOTCH_MOUTH_OVERSHOOT, NOTCH_ANGLE + NOTCH_HALF_WIDTH)
    apex = polar(ocx, ocy, outer_r - notch_depth, NOTCH_ANGLE)
    centroid = ((mouth_a[0] + mouth_b[0] + apex[0]) / 3, (mouth_a[1] + mouth_b[1] + apex[1]) / 3)
    assert centroid[0] > ocx and centroid[1] < ocy, (centroid, (ocx, ocy))
    assert ((centroid[0] - ocx) ** 2 + (centroid[1] - ocy) ** 2) ** 0.5 > outer_r - stroke_r, centroid
    wedge = [mouth_a, apex, mouth_b]
    assert point_in_polygon(centroid, wedge), (centroid, wedge)
    # Subtract the wedge from the actual o outline.  The boolean result is
    # emitted as a standalone path, so no outside portion can become ink.
    o_index = next(i for i, (_, _, char) in enumerate(paths) if char == "o")
    o_offset = paths[o_index][1]
    o_transform = f"translate({o_offset - min_x + pad:.3f},{ty:.3f})"
    tx = o_offset - min_x + pad
    local_wedge = [(x - tx, y - ty) for x, y in wedge]
    glyph_path = BooleanPath()
    glyph_pen = TransformPen(PathPen(glyph_path), (1, 0, 0, -1, 0, asc))
    o_glyph.draw(glyph_pen)
    wedge_path = BooleanPath()
    wedge_pen = PathPen(wedge_path)
    wedge_pen.moveTo(local_wedge[0])
    for point in local_wedge[1:]:
        wedge_pen.lineTo(point)
    wedge_pen.closePath()
    original_area = abs(glyph_path.area)
    result_path = op(glyph_path, wedge_path, PathOp.DIFFERENCE)
    assert abs(result_path.area) < original_area, (result_path.area, original_area)
    result_pen = SVGPathPen(glyph_set)
    result_path.draw(result_pen)
    result_d = result_pen.getCommands()
    local_probe = lambda radius, deg: tuple(v - w for v, w in zip(polar(ocx, ocy, radius, deg), (tx, ty)))
    assert not result_path.contains(local_probe(outer_r - 0.2 * notch_depth, NOTCH_ANGLE))
    assert not result_path.contains(local_probe(outer_r + notch_depth, NOTCH_ANGLE))
    assert result_path.contains(local_probe(outer_r - stroke_r * 0.5, 210.0))
    parts[o_index] = f'<path fill="{INK}" d="{result_d}" transform="{o_transform}"/>'
    return svg(f"0 0 {max_x-min_x+2*pad:.3f} {max_y-min_y+2*pad:.3f}", "compa wordmark", "".join(parts))

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")

def main():
    write(PUBLIC / "compa-wordmark.svg", wordmark())
    mono = monogram(); write(PUBLIC / "compa-monogram.svg", mono)
    write(PUBLIC / "compa-app-icon.svg", app_icon()); write(ROOT / "frontend/public/favicon.svg", mono)
    print("gap-ends=10.0°,50.0° gap-center=30.0° notch-angle=30.0° rasters=skipped")

if __name__ == "__main__": main()
