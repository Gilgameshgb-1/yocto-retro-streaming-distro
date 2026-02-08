from flask import Flask, render_template
import subprocess
import os

template_dir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, template_folder=os.path.join(template_dir, 'templates'))

# Define emulators
EMULATORS = {
    "gba": {"name": "GameBoy Advance", "icon": "gba.png"},
    "n64": {"name": "Nintendo 64", "icon": "n64.png"},
    "ps2": {"name": "Playstation 2", "icon": "ps2.png"},
    "psp": {"name": "PSP", "icon": "psp.png"}
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
         "cmd": ""},
        {"id": "conker", "name": "Conker's Bad Fur Day", "image": "ConkerBadFurDay.png", 
         "cmd": ""},
        {"id": "marioparty", "name": "Mario Party 64", "image": "MarioParty.png", 
         "cmd": ""},
        {"id": "pokemonstadium2", "name": "Pokemon Stadium 2", "image": "PokemonStadium2.png", 
         "cmd": ""}
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
        {"id": "godofwarcoo", "name": "God Of War CoO", "image": "GoWCoO.png", 
        "cmd": ""},
        {"id": "littlebigplanet", "name": "Little Big Planet", "image": "LittleBigPlanet.png", 
        "cmd": ""},
        {"id": "marvelultimatealliance", "name": "Marvel Ultimate Alliance", "image": "MarvelUltimateAlliance.png", 
        "cmd":""},
        {"id": "mgspeacewalker", "name": "MGS Peace Walker", "image": "MGSPeaceWalker.png", 
        "cmd":""}
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
    for system in GAMES:
        for game in GAMES[system]:
            if game["id"] == game_id:
                cmd_to_run = game["cmd"]
                break
    
    if cmd_to_run:
        subprocess.Popen(f"{cmd_to_run}", shell=True) 
        return f"<h1>LAUNCHING {game_id}</h1><script>setTimeout(()=>{{window.location.href='/'}}, 2000)</script>"
    
    return "Game Not Found", 404

@app.route('/stop')
def stop():
    # pkill -f kills any process with 'retroarch' in the name
    subprocess.run(["pkill", "-f", "retroarch"])
    return "Stopped"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)