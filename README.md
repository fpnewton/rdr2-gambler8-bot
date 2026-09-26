# RDR2 Gambler 8 Bot (experimental)

This Windows helper automates the repetitive part of **Gambler Challenge 8** in
Red Dead Redemption 2 Story Mode. It watches for two screen prompts, takes three
hits, stands if the hand survives, and begins another minimum-bet hand.

It deliberately does not modify the game, read memory, or understand card
values. It only compares screenshots and sends the configured keyboard keys.

## Safety and limitations

- Use this only in **Story Mode**, never Red Dead Online.
- Keep RDR2 in **Borderless Windowed** mode at a fixed resolution.
- Press **F10** at any time for the panic stop. **F9** pauses/resumes.
- Stay nearby for the first several hands. Cutscenes, menus, resolution changes,
  UI scaling changes, or another window covering RDR2 can confuse recognition.
- The challenge is still RNG-driven and may run for hours.

## Install

1. Install 64-bit Python 3.11 or newer from <https://python.org>. During setup,
   enable **Add Python to PATH**.
2. Extract this folder somewhere on the Windows PC that runs RDR2.
3. Right-click `install.ps1` and choose **Run with PowerShell**. If Windows blocks
   it, open PowerShell in this folder and run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\install.ps1
   ```

The dependency versions support current Python releases, including Python 3.14.
The installer stops with an error instead of printing a success message when a
native command fails.

## Current setup

The included templates were captured from 1920×1080 screenshots.
Recognition uses the controller-independent `Your turn` and `Place your bet`
status text. The configured keyboard inputs are:

- Hit: `H`
- Stand: `S`
- Place minimum bet: `Enter`
- Decline insurance: `F`

You can continue playing with a controller. The bot only sends these keyboard
inputs when it recognizes the corresponding game status.

When the dealer shows an ace, the bot recognizes the `Decline` prompt and
presses `F` before continuing the hand.

Recognition is restricted to the screen region where each status belongs. If
more than one template scores above the threshold, only the highest-scoring
state is acted on; this prevents the insurance prompt from being confused with
the ordinary betting UI.

Try the included templates first. Recalibrate only if recognition fails because
the resolution, display mode, HDR state, UI scale, or visual settings differ.

## Optional recalibration

1. Sit at a blackjack table and start a hand.
2. When **Hit** and **Stand** are both available, run `run-calibrate.ps1`.
3. Follow the console instructions. Draw a tight rectangle around a stable part
   of the player-turn UI—ideally the `HIT` label plus its key icon. Avoid cards,
   totals, money, NPCs, and animated backgrounds.
4. Finish the hand and stop on the screen used to begin the next hand. Capture a
   tight rectangle around `PLACE BET`, `DEAL`, or `CONTINUE`.
5. If your bindings later change, open `config.json` and update `hit`, `stand`,
   and `continue`. Key names use values such as `enter`, `space`, `left`,
   `right`, `h`, or `s`.

Calibration templates only work with the same resolution, display, HDR state,
UI scale, and display mode used when they were captured.

## Run

1. Return to the blackjack table at the beginning of a hand.
2. Run `run-bot.ps1` and switch back to RDR2 during the five-second countdown.
3. Observe at least five complete hands. Verify that the console reports one
   input per actual Hit and resets when a hand ends.
4. Press **F10** to stop when Challenge Progress reports 3/3.

After requesting a hit, the bot compares the bottom-left player-hand panel with
the image from immediately before the keypress. It confirms the hit only after
the cards or displayed total visibly change and the input cooldown has elapsed.
This prevents rejected keypresses from being counted toward the requirement.

## Tuning

If it never recognizes a prompt, lower `match_threshold` from `0.84` toward
`0.78`. If it triggers on the wrong screen, recapture a more distinctive prompt
or raise the threshold toward `0.90`.

If one physical input produces multiple logged hits, increase
`input_cooldown_seconds`. If RDR2 ignores inputs, increase it to `1.5` or `2.0`.

## Important first-test note

The default action keys are placeholders because RDR2's displayed bindings can
vary. Do not leave the bot unattended until `config.json` matches your prompts
and a few hands have completed correctly.
