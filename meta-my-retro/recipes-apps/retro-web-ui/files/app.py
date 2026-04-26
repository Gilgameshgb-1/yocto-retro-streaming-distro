from flask import Flask, render_template, request
import json
import os
import socket
import subprocess

template_dir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, template_folder=os.path.join(template_dir, 'templates'))

# Define emulators
EMULATORS = {
    "gba": {"name": "GameBoy Advance", "icon": "gba.png"},
    "n64": {"name": "Nintendo 64", "icon": "n64.png"},
    "ps2": {"name": "Playstation 2", "icon": "ps2.png"},
    "psp": {"name": "PSP", "icon": "psp.png"},
    "gamecube": {"name": "GameCube", "icon": "gamecube.png"},
    "ps1": {"name": "Playstation 1", "icon": "ps1.png"},
    "dreamcast": {"name": "Dreamcast", "icon": "dreamcast.png"},
    "nds": {"name": "Nintendo DS", "icon": "nds.png"}
}

# RPi Retroarch commands

GAMES = {
    "gba": [
        {"id": "yugioh", "name": "Yu-Gi-Oh GX", "image": "GXDuelAcademy.png", 
         "cmd": "retroarch -L /usr/lib/libretro/mgba_libretro.so /usr/games/gba/GXDuelAcademy.gba"},
        {"id": "dragonball", "name": "Dragon Ball 2", "image": "DragonBall2.png",
         "cmd": "retroarch -L /usr/lib/libretro/mgba_libretro.so /usr/games/gba/DragonBall2.gba"},
        {"id": "metroid", "name": "Metroid Fusion", "image": "MetroidFusion.png", 
         "cmd": "retroarch -L /usr/lib/libretro/mgba_libretro.so /usr/games/gba/MetroidFusion.gba"}, 
        {"id": "medabots", "name": "Medabots", "image": "Medabots.png", 
         "cmd": "retroarch -L /usr/lib/libretro/mgba_libretro.so /usr/games/gba/Medabots.gba"}
    ],
    "n64": [
        {"id": "mario64", "name": "Super Mario 64", "image": "SuperMario64.png", 
         "cmd": "retroarch -L /usr/lib/libretro/mupen64plus_next_libretro.so /usr/games/n64/SuperMario64.z64"},
        {"id": "conker", "name": "Conker's Bad Fur Day", "image": "ConkerBadFurDay.png", 
         "cmd": "retroarch -L /usr/lib/libretro/mupen64plus_next_libretro.so /usr/games/n64/ConkerBadFurDay.z64"},
        {"id": "marioparty", "name": "Mario Party 64", "image": "MarioParty.png", 
         "cmd": "retroarch -L /usr/lib/libretro/mupen64plus_next_libretro.so /usr/games/n64/MarioParty3.z64"},
        {"id": "pokemonstadium2", "name": "Pokemon Stadium 2", "image": "PokemonStadium2.png", 
         "cmd": "retroarch -L /usr/lib/libretro/mupen64plus_next_libretro.so /usr/games/n64/PokemonStadium.z64"}
    ],
    "ps2": [
        {"id": "beyondgoodandevil", "name": "Beyond Good and Evil", "image": "BeyondGoodAndEvil.png", 
        "cmd": ""},
        {"id": "devilmaycry3", "name": "Devil May Cry 3", "image": "DevilMayCry3.png", 
        "cmd":""},
        {"id": "ookami", "name": "Ookami", "image":"Ookami.png", 
        "cmd":""},
        {"id": "shadowofthecollosus", "name":"Shadow Of The Collosus", "image": "ShadowOfTheC.png",
        "cmd":""}
    ],
        "psp": [
        {"id": "dbzshinbudokai2", "name": "Dragon Ball Z: Shin Budokai 2", "image": "DBZShinBudokai2.png", 
        "cmd": "retroarch -L /usr/lib/libretro/ppsspp_libretro.so /usr/games/psp/DBZShinBudokai2.iso"},
        {"id": "littlebigplanet", "name": "Little Big Planet", "image": "LittleBigPlanet.png", 
        "cmd": ""},
        {"id": "marvelultimatealliance", "name": "Marvel Ultimate Alliance", "image": "MarvelUltimateAlliance.png", 
        "cmd":""},
        {"id": "mgspeacewalker", "name": "MGS Peace Walker", "image": "MGSPeaceWalker.png", 
        "cmd":"retroarch -L /usr/lib/libretro/ppsspp_libretro.so /usr/games/psp/MGSPeaceWalker.iso"}
    ],
    "gamecube": [
        {"id": "supermariosunshine", "name": "Super Mario Sunshine", "image": "smariosunshine.png", 
         "cmd": "retroarch -L /usr/lib/libretro/dolphin_libretro.so /usr/games/gamecube/SuperMarioSunshine.rvz"},
        {"id": "papermario", "name": "Paper Mario", "image": "papermario.png",
         "cmd": "retroarch -L /usr/lib/libretro/dolphin_libretro.so /usr/games/gamecube/PaperMario.rvz"}
    ],
    "ps1":[
        {"id": "crashbandicoot", "name": "Crash Bandicoot", "image": "crashbandicoot.png",
         "cmd": "retroarch -L /usr/lib/libretro/pcsx_rearmed_libretro.so /usr/games/ps1/CrashBandicoot.bin"},
    ],
    "dreamcast":[
        {"id": "sonicadventure2", "name": "Sonic Adventure 2", "image": ".png",
         "cmd": "retroarch -L /usr/lib/libretro/flycast_libretro.so /usr/games/dreamcast/SonicAdventure2.gdi"}
    ],
    "nds":[
        {"id": "newsupermariobros", "name": "New Super Mario Bros", "image": "NewSuperMarioBros.png",
         "cmd": "retroarch -L /usr/lib/libretro/melonds_libretro.so /usr/games/nds/NewSuperMarioBros.nds"},
        {"id": "aceattorneymiles", "name": "Ace Attorney Miles Edgeworth", "image": "AceAttorneyMiles.png",
         "cmd": "retroarch -L /usr/lib/libretro/melonds_libretro.so /usr/games/nds/AceAttorneyMiles.nds"},
         {"id": "dawnofsorrow", "name": "Dawn of Sorrow", "image": "DawnOfSorrow.png",
         "cmd": "retroarch -L /usr/lib/libretro/melonds_libretro.so /usr/games/nds/DawnOfSorrow.nds"},
         {"id": "partnersintime", "name": "Partners in Time", "image": "PartnersInTime.png",
         "cmd": "retroarch -L /usr/lib/libretro/melonds_libretro.so /usr/games/nds/PartnersInTime.nds"}
    ]
}

@app.route('/')
def index():
    return render_template('index.html', emulators=EMULATORS)

@app.route('/emulator/<emu_id>')
def select_game(emu_id):
    emu_name = EMULATORS.get(emu_id, {}).get('name', 'Unknown')
    games_list = GAMES.get(emu_id, [])
    return render_template('games.html', games=games_list, emu_name=emu_name, emu_id=emu_id)

@app.route('/launch/<game_id>')
def launch(game_id):
    cmd_to_run = None
    emu_id = None
    for system in GAMES:
        for game in GAMES[system]:
            if game["id"] == game_id:
                cmd_to_run = game["cmd"]
                emu_id = system
                break

    if cmd_to_run:
        subprocess.Popen(f"{cmd_to_run}", shell=True)
        return (
            f"<h1>LAUNCHING {game_id}</h1>"
            f"<script>setTimeout(()=>{{window.location.href='/play/{emu_id}'}}, 1500)</script>"
        )

    return "Game Not Found", 404


@app.route('/play/<emu_id>')
def play(emu_id):
    return render_template('play.html', emu_id=emu_id)


@app.route('/controller')
def controller():
    return render_template('controller.html')


@app.route('/input', methods=['POST'])
def pad_input():
    data = request.get_json(silent=True) or {}
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        sock.connect('/tmp/retro-pad.sock')
        sock.sendall(json.dumps(data).encode('utf-8'))
        sock.close()
    except Exception:
        pass
    return '', 204

@app.route('/stop')
def stop():
    # pkill -f kills any process with 'retroarch' in the name
    subprocess.run(["pkill", "-f", "retroarch"])
    return "Stopped"

@app.route('/pair')
def pair_controller():
    try:
        # Runs your script from the Yocto bindir
        subprocess.run(["python3", "/usr/bin/auto-pair.py"], check=True)
        return "Pairing Started..."
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    app.run(host=host, port=port, debug=False)