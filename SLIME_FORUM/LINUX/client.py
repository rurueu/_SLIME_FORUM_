import base64
import os
import json
import urllib.request
import urllib.error
import time
import shutil

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

def load_server_url():
    env_url = os.environ.get("SLIME_FORUM_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_url.txt")
    try:
        value = open(config_path, "r", encoding="utf-8").read().strip()
        if value:
            return value.rstrip("/")
    except OSError:
        pass
    return base64.b64decode("aHR0cHM6Ly9zbGltZS1mb3J1bS5vbnJlbmRlci5jb20=").decode("utf-8")

SERVER_URL = load_server_url()

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
LIME = "\033[38;5;154m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
PINK = "\033[38;5;213m"
YELLOW = "\033[93m"
WHITE = "\033[97m"
DIM = "\033[2m"
RED = "\033[91m"


def terminal_width():
    # Utilise toute la largeur disponible, avec une taille minimale raisonnable.
    try:
        return max(64, shutil.get_terminal_size((100, 30)).columns - 2)
    except Exception:
        return 98

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def enable_terminal():
    if os.name == "nt":
        os.system("color")
        os.system("chcp 65001 > nul")


def line(char="═", n=None):
    if n is None:
        n = terminal_width()
    return char * n


def box_inner_width():
    return max(62, terminal_width() - 2)

def banner():
    print(LIME + BOLD)
    print(r"""
███████╗██╗     ██╗███╗   ███╗███████╗
██╔════╝██║     ██║████╗ ████║██╔════╝
███████╗██║     ██║██╔████╔██║█████╗
╚════██║██║     ██║██║╚██╔╝██║██╔══╝
███████║███████╗██║██║ ╚═╝ ██║███████╗
╚══════╝╚══════╝╚═╝╚═╝     ╚═╝╚══════╝
""")
    print(PINK + "                 [  F O R U M  ]" + RESET)
    print(MAGENTA + "             ~ slime terminal edition ~" + RESET)
    print()


def api(path, method="GET", payload=None):
    url = SERVER_URL.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json", "User-Agent": "SLIME-FORUM/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"error": f"Erreur HTTP {e.code}"}
        return e.code, body
    except Exception as e:
        return 0, {"error": f"Serveur inaccessible : {e}"}


def wait():
    input(CYAN + "\nAppuie sur Entrée pour continuer..." + RESET)


def show_posts():
    clear()
    banner()
    print(GREEN + BOLD + "╔" + line("═", box_inner_width()) + "╗")
    print("║" + "              PUBLICATIONS".center(box_inner_width()) + "║")
    print("╚" + line("═", box_inner_width()) + "╝" + RESET)

    status, data = api("/api/posts")
    if status != 200:
        print(RED + f"\n[ERREUR] {data.get('error', 'Erreur inconnue')}" + RESET)
        wait()
        return

    if not data:
        print(YELLOW + "\nAucune publication pour le moment." + RESET)
        wait()
        return

    for post in data:
        print()
        print(PINK + f"  #{post['id']}  Pseudo : " + WHITE + post["pseudo"] + RESET)
        print(CYAN + "  ┌─ INFO " + "─" * max(1, terminal_width() - 12) + RESET)
        for text in post["info"].replace("\r", "").split("\n"):
            print(WHITE + "  │ " + text[:max(20, terminal_width() - 6)] + RESET)
        print(CYAN + "  └" + "─" * max(1, terminal_width() - 3) + RESET)

    wait()


def multiline_input():
    kb = KeyBindings()

    # Dans beaucoup de terminaux : Entrée = Ctrl+M, Ctrl+Entrée = Ctrl+J.
    # Certains terminaux ne distinguent pas les deux. Ctrl+S est donc un secours fiable.
    @kb.add(Keys.ControlM)
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add(Keys.ControlJ)
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-s")
    def _(event):
        event.current_buffer.validate_and_handle()

    session = PromptSession(multiline=True, key_bindings=kb)
    return session.prompt("> ").strip()


def publish():
    clear()
    banner()
    print(MAGENTA + BOLD + "╔" + line("═", box_inner_width()) + "╗")
    print("║" + "             NOUVELLE PUBLICATION".center(box_inner_width()) + "║")
    print("╚" + line("═", box_inner_width()) + "╝" + RESET)
    print(DIM + "Aucune identité réelle n'est demandée." + RESET)

    pseudo = input(PINK + "\nPseudo : " + RESET).strip()
    if pseudo == "0":
        return
    if not pseudo:
        print(RED + "Le pseudo est obligatoire." + RESET)
        wait()
        return

    print(CYAN + "\nINFO (texte uniquement)" + RESET)
    print(DIM + "Entrée = nouvelle ligne | Ctrl+Entrée = envoyer | Ctrl+S = envoyer (secours)" + RESET)
    info = multiline_input()

    if not info:
        print(RED + "L'info est obligatoire." + RESET)
        wait()
        return

    status, data = api("/api/posts", "POST", {"pseudo": pseudo, "info": info})
    if status == 201:
        print(GREEN + "\n✓ Publication envoyée !" + RESET)
    else:
        print(RED + f"\n✗ {data.get('error', 'Erreur')}" + RESET)
    wait()


def menu():
    while True:
        clear()
        banner()
        print(GREEN + "╔" + line("═", box_inner_width()) + "╗")
        print("║" + "                 MENU".center(box_inner_width()) + "║")
        print("╠" + line("═", box_inner_width()) + "╣")
        print("║  " + PINK + "01" + GREEN + "  > Voir les infos d'autres utilisateurs".ljust(52) + "║")
        print("║  " + CYAN + "02" + GREEN + "  > Publier une information".ljust(52) + "║")
        print("║  " + YELLOW + "03" + GREEN + "  > Quitter".ljust(52) + "║")
        print("╚" + line("═", box_inner_width()) + "╝" + RESET)

        choice = input(PINK + "\nFORUM > " + RESET).strip()
        if choice == "01":
            show_posts()
        elif choice == "02":
            publish()
        elif choice == "03":
            clear()
            print(LIME + "\nMerci d'avoir utilisé SLIME FORUM !" + RESET)
            time.sleep(1)
            break
        else:
            print(RED + "\nChoix invalide. Utilise 01, 02 ou 03." + RESET)
            time.sleep(1)


def main():
    enable_terminal()
    menu()


if __name__ == "__main__":
    main()
