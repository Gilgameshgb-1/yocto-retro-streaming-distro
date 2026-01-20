from flask import Flask, render_template
import subprocess
import os

template_dir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, template_folder=os.path.join(template_dir, 'templates'))

GAMES = {
    "YuGiOh": "retroarch -L /usr/lib/libretro/mgba_libretro.so /usr/games/GXDuelAcademy.gba"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/launch/<game_id>')
def launch(game_id):
    if game_id in GAMES:
        cmd = GAMES[game_id]
        # Launching the process
        subprocess.Popen(cmd, shell=True)
        return f"<h1>INITIALIZING {game_id}...</h1><a href='/'>BACK TO MENU</a>"
    
    # If it fails, show why
    return f"<h1>ERROR: {game_id} NOT FOUND</h1><a href='/'>BACK</a>", 404

@app.route('/exit')
def exit_game():
    try:
        # pkill -f looks for any process with 'retroarch' in the name and kills it
        subprocess.run(["pkill", "-f", "retroarch"])
        return "<h1>SYSTEM SHUTDOWN: SUCCESS</h1><a href='/'>BACK TO MENU</a>"
    except Exception as e:
        return f"<h1>SHUTDOWN FAILED</h1><p>{str(e)}</p><a href='/'>BACK</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)