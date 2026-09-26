from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import keyboard
import mss
import numpy as np
import pydirectinput


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
PANIC_KEY = "f10"
PAUSE_KEY = "f9"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        shutil.copyfile(ROOT / "config.example.json", CONFIG_PATH)
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def screenshot(monitor_number: int) -> np.ndarray:
    with mss.mss() as capture:
        monitors = capture.monitors
        if monitor_number < 1 or monitor_number >= len(monitors):
            raise ValueError(
                f"Monitor {monitor_number} is unavailable; found {len(monitors) - 1} monitor(s)."
            )
        image = np.asarray(capture.grab(monitors[monitor_number]))
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)


def choose_roi(image: np.ndarray, title: str) -> np.ndarray:
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title, min(1600, image.shape[1]), min(900, image.shape[0]))
    x, y, width, height = cv2.selectROI(title, image, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(title)
    if width <= 0 or height <= 0:
        raise RuntimeError("No rectangle selected.")
    return image[y : y + height, x : x + width]


def calibrate() -> None:
    config = load_config()
    templates_dir = ROOT / "templates"
    templates_dir.mkdir(exist_ok=True)

    print("\nCALIBRATION 1/2: PLAYER TURN")
    print("Put RDR2 on the blackjack screen where Hit and Stand are available.")
    input("Return here and press Enter to capture the screen... ")
    frame = screenshot(int(config["monitor"]))
    crop = choose_roi(
        frame,
        "Drag a SMALL box around a stable PLAYER TURN prompt; Enter accepts, C cancels",
    )
    cv2.imwrite(str(templates_dir / "player_turn.png"), crop)

    print("\nCALIBRATION 2/2: CONTINUE / PLACE BET")
    print("Finish or leave the current hand until the control used to begin the next hand is visible.")
    input("Return here and press Enter to capture the screen... ")
    frame = screenshot(int(config["monitor"]))
    crop = choose_roi(
        frame,
        "Drag a SMALL box around CONTINUE or PLACE BET; Enter accepts, C cancels",
    )
    cv2.imwrite(str(templates_dir / "continue.png"), crop)

    print("\nSaved both templates.")
    print("Open config.json and set hit, stand, and continue to the keys shown by RDR2.")
    print("Then run run-bot.ps1. F9 pauses; F10 stops immediately.")


@dataclass
class Template:
    name: str
    image: np.ndarray

    @classmethod
    def load(cls, name: str, path: Path) -> "Template":
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f"Missing template: {path}. Run calibration first.")
        return cls(name=name, image=image)

    def score(
        self,
        frame_gray: np.ndarray,
        region: tuple[float, float, float, float] | None = None,
    ) -> float:
        search_image = frame_gray
        if region is not None:
            x1, y1, x2, y2 = region
            frame_height, frame_width = frame_gray.shape[:2]
            search_image = frame_gray[
                int(frame_height * y1) : int(frame_height * y2),
                int(frame_width * x1) : int(frame_width * x2),
            ]
        height, width = self.image.shape[:2]
        if height > search_image.shape[0] or width > search_image.shape[1]:
            return 0.0
        result = cv2.matchTemplate(search_image, self.image, cv2.TM_CCOEFF_NORMED)
        return float(result.max())


def send_key(key: str) -> None:
    # pydirectinput uses Windows SendInput and is more reliable in DirectX games
    # than ordinary GUI automation libraries.
    pydirectinput.press(key)


def crop_normalized(
    frame_gray: np.ndarray, region: tuple[float, float, float, float]
) -> np.ndarray:
    x1, y1, x2, y2 = region
    frame_height, frame_width = frame_gray.shape[:2]
    return frame_gray[
        int(frame_height * y1) : int(frame_height * y2),
        int(frame_width * x1) : int(frame_width * x2),
    ]


def run_bot() -> None:
    config = load_config()
    threshold = float(config["match_threshold"])
    poll_interval = float(config["poll_interval_seconds"])
    cooldown = float(config["input_cooldown_seconds"])
    round_end_grace = float(config["round_end_grace_seconds"])
    diagnostic_interval = float(config.get("diagnostic_interval_seconds", 2.0))
    card_change_threshold = float(config.get("card_change_threshold", 8.0))
    monitor = int(config["monitor"])
    actions = config["actions"]

    templates = {
        name: Template.load(name, ROOT / relative_path)
        for name, relative_path in config["templates"].items()
    }
    if "insurance" not in templates:
        templates["insurance"] = Template.load(
            "insurance", ROOT / "templates" / "insurance.png"
        )

    print("Gambler 8 bot armed. Switch to RDR2 now.")
    print("F9 pauses/resumes. F10 is the panic stop. Starting in 5 seconds...")
    for remaining in range(5, 0, -1):
        print(remaining, flush=True)
        time.sleep(1)

    hits_this_hand = 0
    pending_hit = False
    hit_baseline = None
    last_action_at = 0.0
    turn_last_seen_at = 0.0
    paused = False
    previous_pause_down = False
    last_diagnostic_at = 0.0
    diagnostic_path = ROOT / "debug_capture.png"

    while True:
        if keyboard.is_pressed(PANIC_KEY):
            print("Panic stop pressed. Exiting.")
            return

        pause_down = keyboard.is_pressed(PAUSE_KEY)
        if pause_down and not previous_pause_down:
            paused = not paused
            print("PAUSED" if paused else "RESUMED")
        previous_pause_down = pause_down
        if paused:
            time.sleep(0.1)
            continue

        now = time.monotonic()
        frame = screenshot(monitor)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        player_score = templates["player_turn"].score(
            gray, region=(0.0, 0.80, 0.35, 1.0)
        )
        continue_score = templates["continue"].score(
            gray, region=(0.35, 0.80, 0.65, 1.0)
        )
        insurance_score = templates["insurance"].score(
            gray, region=(0.75, 0.75, 1.0, 1.0)
        )
        state_scores = {
            "player_turn": player_score,
            "continue": continue_score,
            "insurance": insurance_score,
        }
        active_state, active_score = max(state_scores.items(), key=lambda item: item[1])
        if active_score < threshold:
            active_state = "none"

        hand_region = crop_normalized(gray, region=(0.04, 0.82, 0.19, 1.0))
        hand_change = 0.0
        if pending_hit and hit_baseline is not None:
            hand_change = float(
                cv2.absdiff(hand_region, hit_baseline).mean()
            )

        if now - last_diagnostic_at >= diagnostic_interval:
            cv2.imwrite(str(diagnostic_path), frame)
            print(
                f"Watching: your-turn={player_score:.2f}, "
                f"place-bet={continue_score:.2f}, "
                f"insurance={insurance_score:.2f}, "
                f"hand-change={hand_change:.1f}, threshold={threshold:.2f}"
            )
            last_diagnostic_at = now

        if active_state == "insurance" and now - last_action_at >= cooldown:
            send_key(actions.get("decline_insurance", "f"))
            last_action_at = now
            print(f"Declining insurance (match {insurance_score:.2f})")

        elif active_state == "player_turn":
            turn_last_seen_at = now
            if (
                pending_hit
                and hand_change >= card_change_threshold
                and now - last_action_at >= cooldown
            ):
                hits_this_hand += 1
                pending_hit = False
                hit_baseline = None
                last_action_at = now
                print(
                    f"Hit {hits_this_hand}/3 confirmed; "
                    f"hand panel changed by {hand_change:.1f}"
                )

            if not pending_hit and now - last_action_at >= cooldown:
                if hits_this_hand < 3:
                    hit_baseline = hand_region.copy()
                    send_key(actions["hit"])
                    pending_hit = True
                    print(
                        f"Requesting hit {hits_this_hand + 1}/3; "
                        "waiting for the hand panel to change"
                    )
                else:
                    send_key(actions["stand"])
                    print(f"Stand after 3 hits (match {player_score:.2f})")
                last_action_at = now

        elif active_state == "continue" and now - last_action_at >= cooldown:
            send_key(actions["continue"])
            hits_this_hand = 0
            pending_hit = False
            hit_baseline = None
            last_action_at = now
            print(f"Starting next hand (match {continue_score:.2f})")

        if (
            player_score < threshold
            and continue_score < threshold
            and turn_last_seen_at
            and now - turn_last_seen_at >= round_end_grace
        ):
            # Busts and dealer resolution remove the player-turn prompt. Resetting
            # here ensures the next hand starts at hit zero even if Continue was
            # not recognized during an animation.
            hits_this_hand = 0
            pending_hit = False
            hit_baseline = None
            turn_last_seen_at = 0.0

        time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="RDR2 Gambler 8 blackjack helper")
    parser.add_argument("command", choices=("calibrate", "run"))
    args = parser.parse_args()
    if args.command == "calibrate":
        calibrate()
    else:
        run_bot()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
