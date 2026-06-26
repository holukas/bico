"""Tiny dependency-free terminal line plot.

Renders a sequence of y-values as a braille-dot line plot inside a
``rich.text.Text``. Each braille cell packs a 2x4 dot grid, so a ``width`` x
``height`` grid of cells gives an effective resolution of ``2*width`` by
``4*height`` dots. Used by the TUI to show a live plot of the first N values of
one variable as each file finishes converting.

Kept free of any Textual or numpy dependency so it is trivially testable and
never touches the conversion engine's pinned numpy (textual-plot, the obvious
off-the-shelf widget, requires numpy>=2.2.1 which bico does not allow).
"""
import math

from rich.text import Text

# Braille dot bit for a (dx, dy) position within a cell: dx in {0, 1}, dy in
# {0, 1, 2, 3}. Unicode braille patterns start at U+2800; these bits OR together
# to pick which of the eight dots in a cell are lit.
_BRAILLE_BITS = {
    (0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (0, 3): 0x40,
    (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (1, 3): 0x80,
}

# Sentinel for missing data in the converted output; dropped so it never blows
# up the plotted y-range.
_MISSING = -9999

# Distinct colours for the overlaid series, by position. The TUI uses the same
# order to colour the variable names in the plot title (which acts as a legend).
PLOT_COLORS = ('bright_cyan', 'bright_magenta', 'bright_yellow')


def _fmt(value: float) -> str:
    """Compact number label for an axis tick."""
    if value == 0:
        return '0'
    av = abs(value)
    if av >= 1000 or av < 0.01:
        return f'{value:.3g}'
    return f'{value:.2f}'


def _finite_points(ys):
    """(index, value) pairs for finite, non-missing values only.

    The index is the original position, so missing/non-finite values show up as
    gaps in the line rather than shifting later points to the left.
    """
    points = []
    for i, v in enumerate(ys):
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(fv) or math.isinf(fv) or fv == _MISSING:
            continue
        points.append((i, fv))
    return points


def _draw_segment(x0, y0, x1, y1, set_dot):
    """Light the dots along the line between two dot coordinates (Bresenham)."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_dot(x0, y0)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def render_braille_plot(series, *, width: int = 50, height: int = 8,
                        axis_style: str = 'grey50', connect: bool = False) -> Text:
    """Render several series overlaid on shared axes, each in its own colour.

    ``series`` is a list of dicts ``{'y': [floats], 'color': str (optional)}``;
    colours default to :data:`PLOT_COLORS` by position. All series share one
    auto-scaled y-axis (the combined min/max), so this is meant for variables on
    a comparable scale (e.g. the sonic's U/V/W). A braille cell holds a single
    colour, so where series overlap in a cell the last one drawn wins.

    Returns a multi-line ``rich.text.Text``: a y-axis gutter (max label on the
    top row, min on the bottom), the dot canvas, and an x-axis footer with the
    index span. Missing (-9999) and non-finite values are skipped. Only the data
    points are drawn unless ``connect=True``. When no series has finite data, a
    short dim note is returned. The default ``width=50`` gives 100 dot columns,
    so 100 values map one-per-column.
    """
    plots = []  # (color, [(x, y), ...]) for each series with finite data
    for i, s in enumerate(series or []):
        points = _finite_points(s.get('y', []))
        if points:
            plots.append((s.get('color') or PLOT_COLORS[i % len(PLOT_COLORS)], points))
    if not plots:
        return Text('  (no finite values to plot)', style='dim')

    all_x = [x for _, pts in plots for x, _ in pts]
    all_y = [y for _, pts in plots for _, y in pts]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    # Pad a flat range so it draws as a centred line rather than dividing by zero.
    if ymax == ymin:
        ymax += 1.0
        ymin -= 1.0
    xspan = (xmax - xmin) or 1
    yspan = ymax - ymin

    dot_w = width * 2
    dot_h = height * 4
    bits = [[0] * width for _ in range(height)]
    colors = [[None] * width for _ in range(height)]

    def set_dot(dx_abs: int, dy_abs: int, color: str) -> None:
        if not (0 <= dx_abs < dot_w and 0 <= dy_abs < dot_h):
            return
        cell_x, in_x = divmod(dx_abs, 2)
        cell_y, in_y = divmod(dy_abs, 4)
        bits[cell_y][cell_x] |= _BRAILLE_BITS[(in_x, in_y)]
        colors[cell_y][cell_x] = color  # last writer wins on overlap

    def to_dot(x: float, y: float):
        dx = round((x - xmin) / xspan * (dot_w - 1))
        dy = round((ymax - y) / yspan * (dot_h - 1))
        return dx, dy

    for color, points in plots:
        prev = None
        for x, y in points:
            dot = to_dot(x, y)
            if connect and prev is not None:
                _draw_segment(prev[0], prev[1], dot[0], dot[1],
                              lambda dx, dy, c=color: set_dot(dx, dy, c))
            set_dot(dot[0], dot[1], color)
            prev = dot

    label_w = max(len(_fmt(ymax)), len(_fmt(ymin)))
    out = Text()
    for row in range(height):
        if row == 0:
            gutter = _fmt(ymax).rjust(label_w)
        elif row == height - 1:
            gutter = _fmt(ymin).rjust(label_w)
        else:
            gutter = ' ' * label_w
        out.append(gutter + ' ', style=axis_style)
        out.append('│', style=axis_style)
        for cell_x in range(width):
            ch = chr(0x2800 + bits[row][cell_x])
            color = colors[row][cell_x]
            out.append(ch, style=color if color else None)
        out.append('\n')
    out.append(' ' * (label_w + 1), style=axis_style)
    out.append('└' + '─' * width + '\n', style=axis_style)
    out.append(' ' * (label_w + 2), style=axis_style)
    npts = max(len(pts) for _, pts in plots)
    out.append(f'{xmin} … {xmax}   ({npts} pts)', style='dim')
    return out
