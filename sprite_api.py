# sprite_api.py
import time
import json
import displayio

def _safe_refresh(display, fps=30):
    try:
        display.refresh(minimum_frames_per_second=0, target_frames_per_second=fps)
    except TypeError:
        display.refresh()

class Sprite:
    """
    Minimal sprite helper for CircuitPython displayio TileGrid sprite sheets.

    - One sprite sheet (OnDiskBitmap)
    - One TileGrid (width=1,height=1)
    - Clips defined as start/count/fps/loop
    - Blocking convenience methods:
        tgmove(clip, dx, dy)
        tgwait(clip, seconds)
    """

    def __init__(
        self,
        screen,
        sheet_path,
        frame_w,
        frame_h,
        cols,
        x=0,
        y=0,
        group=None,
        insert_at=None,
        manual_refresh=True,
    ):
        self.screen = screen
        self.display = screen.display
        self.manual_refresh = manual_refresh and hasattr(self.display, "auto_refresh")

        self.sheet_path = sheet_path
        self.frame_w = int(frame_w)
        self.frame_h = int(frame_h)
        self.cols = int(cols)

        self.clips = {}
        self.clip = None
        self.frame = 0
        self._last_frame_t = time.monotonic()

        self.odb = displayio.OnDiskBitmap(sheet_path)
        self.tg = displayio.TileGrid(
            self.odb,
            pixel_shader=self.odb.pixel_shader,
            width=1,
            height=1,
            tile_width=self.frame_w,
            tile_height=self.frame_h,
            x=int(x),
            y=int(y),
        )

        if group is None:
            # default: attach to your existing splash group
            group = screen.splash

        if insert_at is None:
            group.append(self.tg)
        else:
            group.insert(int(insert_at), self.tg)

        self.x = int(x)
        self.y = int(y)

    # ---------- clip setup ----------
    def add_clip(self, name, *, start=None, row=None, count=1, fps=8, loop=True):
        if start is None:
            if row is None:
                raise ValueError("add_clip needs start= or row=")
            start = int(row) * self.cols
        self.clips[name] = {
            "start": int(start),
            "count": int(count),
            "fps": float(fps),
            "loop": bool(loop),
        }
        if self.clip is None:
            self.set_clip(name)

    def set_clip(self, name):
        if name not in self.clips:
            raise KeyError(f"Unknown clip '{name}'. Defined: {list(self.clips.keys())}")
        self.clip = name
        self.frame = 0
        self._last_frame_t = time.monotonic()
        self._apply_frame()

    def _apply_frame(self):
        c = self.clips[self.clip]
        self.tg[0] = c["start"] + self.frame

    def _step_anim(self, now):
        if self.clip is None:
            return
        c = self.clips[self.clip]
        if c["fps"] <= 0:
            return
        frame_dt = 1.0 / c["fps"]
        if now - self._last_frame_t >= frame_dt:
            self._last_frame_t += frame_dt
            self.frame += 1
            if self.frame >= c["count"]:
                self.frame = 0 if c["loop"] else (c["count"] - 1)
            self._apply_frame()

    # ---------- movement / facing ----------
    def set_pos(self, x, y, auto_face_dx=None):
        x = int(x)
        y = int(y)
        if auto_face_dx is not None:
            if auto_face_dx < 0:
                self.tg.flip_x = True
            elif auto_face_dx > 0:
                self.tg.flip_x = False

        self.x, self.y = x, y
        self.tg.x = x
        self.tg.y = y

    # ---------- “simple API” blocking helpers ----------
    def tgwait(self, clip, seconds, fps=30):
        """Play a clip for N seconds (blocking)."""
        self.set_clip(clip)
        end_t = time.monotonic() + float(seconds)

        old_auto = getattr(self.display, "auto_refresh", None)
        if self.manual_refresh:
            self.display.auto_refresh = False

        try:
            while time.monotonic() < end_t:
                now = time.monotonic()
                self._step_anim(now)
                if self.manual_refresh:
                    _safe_refresh(self.display, fps=fps)
                time.sleep(0.01)
        finally:
            if self.manual_refresh and old_auto is not None:
                self.display.auto_refresh = old_auto

    def tgmove(self, clip, dx, dy, speed=60, fps=30, auto_face=True):
        """
        Move by dx/dy while animating clip (blocking).
        speed is pixels/second (applies to total distance).
        """
        self.set_clip(clip)

        dx = float(dx)
        dy = float(dy)
        dist = (dx * dx + dy * dy) ** 0.5
        if dist == 0:
            return

        duration = dist / float(speed) if speed > 0 else 0.0
        if duration <= 0:
            self.set_pos(self.x + dx, self.y + dy, auto_face_dx=dx if auto_face else None)
            return

        start_x, start_y = float(self.x), float(self.y)
        end_x, end_y = start_x + dx, start_y + dy
        start_t = time.monotonic()

        if auto_face:
            # Mirror based on horizontal intent
            if dx < 0:
                self.tg.flip_x = True
            elif dx > 0:
                self.tg.flip_x = False

        old_auto = getattr(self.display, "auto_refresh", None)
        if self.manual_refresh:
            self.display.auto_refresh = False

        try:
            while True:
                now = time.monotonic()
                t = (now - start_t) / duration
                if t >= 1.0:
                    self.set_pos(end_x, end_y)
                    break

                # linear interpolation
                cur_x = start_x + (end_x - start_x) * t
                cur_y = start_y + (end_y - start_y) * t
                self.set_pos(cur_x, cur_y)

                self._step_anim(now)

                if self.manual_refresh:
                    _safe_refresh(self.display, fps=fps)
                time.sleep(0.01)
        finally:
            if self.manual_refresh and old_auto is not None:
                self.display.auto_refresh = old_auto

    # ---------- config loader for “people uploading sprites” ----------
    @classmethod
    def from_config(cls, screen, config_path, x=0, y=0, group=None, insert_at=None):
        """
        Config schema:
        {
          "sheet": "/bitmaps/pebbleSpriteSheet.bmp",
          "frame_w": 20,
          "frame_h": 20,
          "cols": 8,
          "clips": {
            "sit":  {"row":0,"count":8,"fps":6,"loop":true},
            "idle": {"row":1,"count":8,"fps":8,"loop":true},
            "walk": {"row":2,"count":8,"fps":10,"loop":true}
          }
        }
        """
        with open(config_path, "r") as f:
            cfg = json.load(f)

        spr = cls(
            screen,
            cfg["sheet"],
            cfg["frame_w"],
            cfg["frame_h"],
            cfg["cols"],
            x=x,
            y=y,
            group=group,
            insert_at=insert_at,
        )
        for name, c in cfg.get("clips", {}).items():
            spr.add_clip(
                name,
                start=c.get("start"),
                row=c.get("row"),
                count=c.get("count", 1),
                fps=c.get("fps", 8),
                loop=c.get("loop", True),
            )
        return spr
