# Shutdown-Planner

Schedule your PC shutdown or disable a network adapter at chosen time

## Features

- **Turn off the PC**
  - CMD schedule: uses `shutdown /s /t <seconds>`
  - App shutdown: counts down in the app, then force shuts down Windows with no "are you sure" prompts
- **Turn off the Internet**: disables the network adapter you pick when the timer ends
- Pick the time and date by selecting or typing (defaults to now)
- Live countdown, Run/Cancel button

## Requirements

- Windows 10/11
- Python 3.9+
- Administrator rights (the app asks on startup)
