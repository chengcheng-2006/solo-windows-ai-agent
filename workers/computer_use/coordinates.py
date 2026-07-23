from __future__ import annotations

from .models import Bounds, CoordinateSpace, Point


class CoordinateMapper:
    """Convert logical/physical coordinates relative to one monitor origin."""

    def __init__(self, dpi_scale: float, monitor_bounds: Bounds) -> None:
        if dpi_scale < 0.5 or dpi_scale > 5.0:
            raise ValueError("dpi_scale outside supported range")
        if monitor_bounds.coordinate_space != CoordinateSpace.PHYSICAL:
            raise ValueError("monitor origin must be expressed in physical coordinates")
        self.dpi_scale = dpi_scale
        self.monitor_bounds = monitor_bounds

    def point(self, value: Point, target: CoordinateSpace) -> Point:
        if value.coordinate_space == target:
            return value.model_copy(deep=True)
        origin_x = self.monitor_bounds.left
        origin_y = self.monitor_bounds.top
        if value.coordinate_space == CoordinateSpace.LOGICAL:
            return Point(
                x=origin_x + ((value.x - origin_x) * self.dpi_scale),
                y=origin_y + ((value.y - origin_y) * self.dpi_scale),
                coordinate_space=CoordinateSpace.PHYSICAL,
            )
        return Point(
            x=origin_x + ((value.x - origin_x) / self.dpi_scale),
            y=origin_y + ((value.y - origin_y) / self.dpi_scale),
            coordinate_space=CoordinateSpace.LOGICAL,
        )

    def bounds(self, value: Bounds, target: CoordinateSpace) -> Bounds:
        if value.coordinate_space == target:
            return value.model_copy(deep=True)
        top_left = self.point(
            Point(x=value.left, y=value.top, coordinate_space=value.coordinate_space),
            target,
        )
        factor = self.dpi_scale if target == CoordinateSpace.PHYSICAL else 1 / self.dpi_scale
        return Bounds(
            left=top_left.x,
            top=top_left.y,
            width=value.width * factor,
            height=value.height * factor,
            coordinate_space=target,
        )
