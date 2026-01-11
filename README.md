# My Retro OS (Pi 5)

A custom Yocto-based Linux distribution for the Raspberry Pi 5 for future emulation and streaming platform.

## Repository Structure
* **`meta-my-retro/`**: My custom Yocto layer
* **`kas-project.yml`**: Build file

## Prerequisites

1.  **System Dependencies**: Ensure your host machine (Ubuntu 24.04 recommended) has the standard Yocto dependencies installed.
2.  **Install Kas**:
    ```bash
    sudo apt update && sudo apt install pipx
    pipx install kas
    ```
## Build image
    kas build kas-project.yml

## Running emu

Currently you can run emu by using this command (also you need to copy your ROM files)
     ```
     retroarch -L mgba_libretro.so /home/root/games/your_game.gba
     ```