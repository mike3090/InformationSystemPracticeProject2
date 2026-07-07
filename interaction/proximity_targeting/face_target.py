from __future__ import annotations

import argparse
import math
import socket
import struct
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class NameplateCrop:
    image_path: Path
    bbox: tuple[int, int, int, int]
    center_x: float
    center_y: float
    area: int


@dataclass(frozen=True)
class NameCandidate:
    text: str
    confidence: float
    crop: NameplateCrop


class OscInput:
    def __init__(self, host: str, port: int, invert_look: bool = False) -> None:
        self.host = host
        self.port = port
        self.invert_look = invert_look
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def look_horizontal_pulse(self, value: float, pulse_seconds: float) -> None:
        value = max(-1.0, min(1.0, value))
        if self.invert_look:
            value = -value
        self._send_float('/input/LookHorizontal', value)
        time.sleep(max(0.01, pulse_seconds))
        self._send_float('/input/LookHorizontal', 0.0)

    def stop_looking(self) -> None:
        self._send_float('/input/LookHorizontal', 0.0)

    def _send_float(self, address: str, value: float) -> None:
        packet = _osc_string(address) + _osc_string(',f') + struct.pack('>f', float(value))
        self.sock.sendto(packet, (self.host, self.port))


def _osc_string(value: str) -> bytes:
    data = value.encode('utf-8') + b'\0'
    padding = (4 - (len(data) % 4)) % 4
    return data + (b'\0' * padding)


class EasyOcrReader:
    def __init__(self, languages: list[str]) -> None:
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError('easyocr is not installed. Run proximity_targeting\\requirements.txt install first.') from exc
        self.reader = easyocr.Reader(languages, gpu=False)

    def read_crop(self, path: Path) -> list[tuple[str, float]]:
        rows = self.reader.readtext(str(path), detail=1, paragraph=False)
        outputs: list[tuple[str, float]] = []
        for _bbox, text, confidence in rows:
            cleaned = clean_name(text)
            if cleaned:
                outputs.append((cleaned, float(confidence)))
        return outputs


def capture_screen() -> np.ndarray:
    try:
        import mss
    except ImportError as exc:
        raise RuntimeError('mss is not installed. Run proximity_targeting\\requirements.txt install first.') from exc

    with mss.mss() as screen:
        monitor = screen.monitors[1]
        image = screen.grab(monitor)
        array = np.asarray(image, dtype=np.uint8)
        return array[:, :, :3][:, :, ::-1]  # BGRA -> RGB


def rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb_f = rgb.astype(np.float32) / 255.0
    r = rgb_f[:, :, 0]
    g = rgb_f[:, :, 1]
    b = rgb_f[:, :, 2]
    maxc = np.max(rgb_f, axis=2)
    minc = np.min(rgb_f, axis=2)
    delta = maxc - minc

    hue = np.zeros_like(maxc)
    mask = delta > 1e-6
    r_mask = mask & (maxc == r)
    g_mask = mask & (maxc == g)
    b_mask = mask & (maxc == b)
    hue[r_mask] = ((g[r_mask] - b[r_mask]) / delta[r_mask]) % 6
    hue[g_mask] = ((b[g_mask] - r[g_mask]) / delta[g_mask]) + 2
    hue[b_mask] = ((r[b_mask] - g[b_mask]) / delta[b_mask]) + 4
    hue = hue * 30.0  # OpenCV-style 0..180 hue

    sat = np.zeros_like(maxc)
    sat[maxc > 1e-6] = delta[maxc > 1e-6] / maxc[maxc > 1e-6]
    val = maxc
    return hue, sat * 255.0, val * 255.0


def color_mask(rgb: np.ndarray, hue_min: float, hue_max: float, sat_min: float, value_min: float) -> np.ndarray:
    hue, sat, val = rgb_to_hsv(rgb)
    if hue_min <= hue_max:
        hue_ok = (hue >= hue_min) & (hue <= hue_max)
    else:
        hue_ok = (hue >= hue_min) | (hue <= hue_max)
    return hue_ok & (sat >= sat_min) & (val >= value_min)


def connected_components(mask: np.ndarray, min_area: int, max_area: int) -> list[tuple[int, int, int, int, int]]:
    height, width = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    boxes: list[tuple[int, int, int, int, int]] = []

    ys, xs = np.nonzero(mask)
    for start_x, start_y in zip(xs, ys):
        if visited[start_y, start_x]:
            continue
        stack = [(int(start_x), int(start_y))]
        visited[start_y, start_x] = True
        min_x = max_x = int(start_x)
        min_y = max_y = int(start_y)
        area = 0

        while stack:
            x, y = stack.pop()
            area += 1
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    stack.append((nx, ny))

        if min_area <= area <= max_area:
            boxes.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return boxes


def extract_nameplate_crops(rgb: np.ndarray, args) -> list[NameplateCrop]:
    from PIL import Image

    mask = color_mask(rgb, args.hue_min, args.hue_max, args.sat_min, args.value_min)
    height, width = mask.shape
    boxes = connected_components(mask, args.min_component_area, args.max_component_area)
    crops: list[NameplateCrop] = []
    args.crop_dir.mkdir(parents=True, exist_ok=True)

    for index, (x1, y1, x2, y2, area) in enumerate(boxes[: args.max_crops]):
        box_w = x2 - x1
        box_h = y2 - y1
        aspect = box_w / max(box_h, 1)
        if not (args.min_aspect <= aspect <= args.max_aspect):
            continue
        pad_x = int(box_w * args.pad_x)
        pad_y = int(box_h * args.pad_y)
        cx1 = max(0, x1 - pad_x)
        cy1 = max(0, y1 - pad_y)
        cx2 = min(width, x2 + pad_x)
        cy2 = min(height, y2 + pad_y)
        crop = rgb[cy1:cy2, cx1:cx2]
        path = args.crop_dir / f'crop-{int(time.time() * 1000)}-{index}.png'
        center_x = ((cx1 + cx2) / 2) / width
        center_y = ((cy1 + cy2) / 2) / height
        if not (args.min_center_y <= center_y <= args.max_center_y):
            continue
        Image.fromarray(crop).save(path)
        crops.append(NameplateCrop(path, (cx1, cy1, cx2, cy2), center_x, center_y, area))
    return crops


def clean_name(text: str) -> str | None:
    text = ' '.join(text.replace('\n', ' ').split()).strip(' :|[](){}<>')
    if len(text) < 2 or len(text) > 32:
        return None
    if sum(ch.isalnum() for ch in text) < 2:
        return None
    blocked = {'voice', 'mic', 'menu', 'settings', 'avatar', 'world', 'debug'}
    if text.casefold() in blocked:
        return None
    return text


def choose_target(candidates: list[NameCandidate], screen_center: float = 0.5) -> NameCandidate | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (abs(item.crop.center_x - screen_center), -item.confidence))[0]


def choose_crop_target(crops: list[NameplateCrop], screen_center: float = 0.5) -> NameplateCrop | None:
    if not crops:
        return None
    return sorted(crops, key=lambda crop: (abs(crop.center_x - screen_center), -crop.area))[0]


def compute_turn(target_x: float, deadzone: float, gain: float, max_value: float) -> float:
    error = target_x - 0.5
    if abs(error) <= deadzone:
        return 0.0
    return max(-max_value, min(max_value, error * gain))


def print_candidates(candidates: list[NameCandidate]) -> None:
    for candidate in candidates[:10]:
        x1, y1, x2, y2 = candidate.crop.bbox
        print(
            f'candidate name={candidate.text!r} conf={candidate.confidence:.2f} '
            f'x={candidate.crop.center_x:.2f} y={candidate.crop.center_y:.2f} bbox=({x1},{y1},{x2},{y2})'
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Face the local VRChat account toward a nearby player nameplate.')
    parser.add_argument('--once', action='store_true', help='Run one screenshot/OCR pass and exit.')
    parser.add_argument('--save-debug', action='store_true', help='Keep crop images for inspection.')
    parser.add_argument('--interval', type=float, default=0.6)
    parser.add_argument('--osc-host', default='127.0.0.1')
    parser.add_argument('--osc-port', type=int, default=9000)
    parser.add_argument('--invert-look', action='store_true')
    parser.add_argument('--deadzone', type=float, default=0.08)
    parser.add_argument('--look-gain', type=float, default=1.4)
    parser.add_argument('--max-look', type=float, default=0.35)
    parser.add_argument('--pulse-seconds', type=float, default=0.08)
    parser.add_argument('--ocr-langs', default='en,ja')
    parser.add_argument('--crop-dir', type=Path, default=Path('.tmp/proximity_targeting/crops'))
    parser.add_argument('--hue-min', type=float, default=85.0, help='OpenCV-style HSV hue min, 0..180.')
    parser.add_argument('--hue-max', type=float, default=140.0, help='OpenCV-style HSV hue max, 0..180. Use min>max for wraparound.')
    parser.add_argument('--sat-min', type=float, default=35.0)
    parser.add_argument('--value-min', type=float, default=80.0)
    parser.add_argument('--min-component-area', type=int, default=80)
    parser.add_argument('--max-component-area', type=int, default=25000)
    parser.add_argument('--min-aspect', type=float, default=1.2)
    parser.add_argument('--max-aspect', type=float, default=18.0)
    parser.add_argument('--pad-x', type=float, default=2.4)
    parser.add_argument('--pad-y', type=float, default=2.0)
    parser.add_argument('--min-center-y', type=float, default=0.08)
    parser.add_argument('--max-center-y', type=float, default=0.90)
    parser.add_argument('--max-crops', type=int, default=30)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        reader: EasyOcrReader | None = EasyOcrReader([lang.strip() for lang in args.ocr_langs.split(',') if lang.strip()])
    except Exception as exc:
        print(f'ocr unavailable; falling back to color-crop targeting only: {exc}', flush=True)
        reader = None
    osc = OscInput(args.osc_host, args.osc_port, args.invert_look)
    recent_targets: deque[str] = deque(maxlen=5)

    try:
        while True:
            rgb = capture_screen()
            crops = extract_nameplate_crops(rgb, args)
            candidates: list[NameCandidate] = []
            if reader is not None:
                for crop in crops:
                    for text, confidence in reader.read_crop(crop.image_path):
                        candidates.append(NameCandidate(text, confidence, crop))

            print_candidates(candidates)
            target = choose_target(candidates)
            if target is not None:
                recent_targets.append(target.text)
                stable_name = max(set(recent_targets), key=list(recent_targets).count)
                turn = compute_turn(target.crop.center_x, args.deadzone, args.look_gain, args.max_look)
                print(f'target={stable_name!r} x={target.crop.center_x:.2f} turn={turn:.3f}')
                if not args.once and turn != 0.0:
                    osc.look_horizontal_pulse(turn, args.pulse_seconds)
                else:
                    osc.stop_looking()
            else:
                crop_target = choose_crop_target(crops)
                if crop_target is None:
                    print('target=- no nameplate color crop')
                    osc.stop_looking()
                else:
                    turn = compute_turn(crop_target.center_x, args.deadzone, args.look_gain, args.max_look)
                    print(f'target=unknown x={crop_target.center_x:.2f} turn={turn:.3f} source=color-crop')
                    if not args.once and turn != 0.0:
                        osc.look_horizontal_pulse(turn, args.pulse_seconds)
                    else:
                        osc.stop_looking()

            if args.once:
                break
            if not args.save_debug:
                for crop in crops:
                    try:
                        crop.image_path.unlink(missing_ok=True)
                    except OSError:
                        pass
            time.sleep(args.interval)
    finally:
        osc.stop_looking()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
