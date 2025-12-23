import pyqtgraph as pg

class SpectroViewBox(pg.ViewBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hard_xmin = None
        self.hard_xmax = None
        self.hard_ymin = None
        self.hard_ymax = None

    def set_hard_limits(self, xmin: float, xmax: float, ymin: float, ymax: float):
        self.hard_xmin, self.hard_xmax = float(xmin), float(xmax)
        self.hard_ymin, self.hard_ymax = float(ymin), float(ymax)

    def clamp_view(self):
        if None in (self.hard_xmin, self.hard_xmax, self.hard_ymin, self.hard_ymax):
            return
        (xr, yr) = self.viewRange()
        x0, x1 = float(xr[0]), float(xr[1])
        y0, y1 = float(yr[0]), float(yr[1])

        w = max(1e-6, x1 - x0)
        h = max(1e-6, y1 - y0)

        if x0 < self.hard_xmin:
            x0 = self.hard_xmin
            x1 = x0 + w
        if x1 > self.hard_xmax:
            x1 = self.hard_xmax
            x0 = x1 - w
        x0 = max(self.hard_xmin, x0)
        x1 = min(self.hard_xmax, x1)

        if y0 < self.hard_ymin:
            y0 = self.hard_ymin
            y1 = y0 + h
        if y1 > self.hard_ymax:
            y1 = self.hard_ymax
            y0 = y1 - h
        y0 = max(self.hard_ymin, y0)
        y1 = min(self.hard_ymax, y1)

        self.setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0.0, update=True)

    def zoom_by_xy(self, factor_x: float, factor_y: float, center):
        if factor_x <= 0 or factor_y <= 0:
            return
        sx = 1.0 / factor_x
        sy = 1.0 / factor_y
        self.scaleBy((sx, sy), center=center)
        self.clamp_view()

    def pan_by_pixels(self, dx_px: float, dy_px: float):
        px = self.viewPixelSize()
        dx = -dx_px * px[0]
        dy = +dy_px * px[1]
        self.translateBy(x=dx, y=dy)
        self.clamp_view()
