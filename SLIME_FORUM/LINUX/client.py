import base64
import os
import json
import urllib.request
import urllib.error
import time
import shutil
import re

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


def load_server_url():
    env_url = os.environ.get("SLIME_FORUM_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
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
    try:
        return max(90, os.get_terminal_size().columns)
    except Exception:
        try:
            return max(90, shutil.get_terminal_size((120, 35)).columns)
        except Exception:
            return 120


def inner_width():
    return max(88, terminal_width() - 2)


def center_ansi(text, visible_text=None, width=None):
    if width is None:
        width = terminal_width()
    if visible_text is None:
        visible_text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    left = max(0, (width - len(visible_text)) // 2)
    return " " * left + text


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def enable_terminal():
    if os.name == "nt":
        os.system("color")
        os.system("chcp 65001 > nul")


def line(char="═", n=None):
    return char * (terminal_width() if n is None else n)


def banner():
    width = terminal_width()
    logo = [
        "███████╗ ██╗      ██╗ ███╗   ███╗ ███████╗",
        "██╔════╝ ██║      ██║ ████╗ ████║ ██╔════╝",
        "███████╗ ██║      ██║ ██╔████╔██║ █████╗  ",
        "╚════██║ ██║      ██║ ██║╚██╔╝██║ ██╔══╝  ",
        "███████║ ███████╗ ██║ ██║ ╚═╝ ██║ ███████╗",
        "╚══════╝ ╚══════╝ ╚═╝ ╚═╝     ╚═╝ ╚══════╝",
    ]

    print()
    print()
    for row in logo:
        print(center_ansi(LIME + BOLD + row + RESET, row, width))
    print()

    title = "[  F O R U M  ]"
    subtitle = "~ slime terminal edition ~"
    print(center_ansi(PINK + BOLD + title + RESET, title, width))
    print(center_ansi(MAGENTA + subtitle + RESET, subtitle, width))
    print()
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
        with urllib.request.urlopen(req, timeout=70) as response:
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


def print_post(post, level=0):
    indent = "    " * min(level, 5)
    prefix = "↳ " if level else ""
    header_color = CYAN if level else PINK

    print()
    print(indent + header_color + f"  {prefix}#{post['id']}  Pseudo : " + WHITE + post["pseudo"] + RESET)

    if post.get("parent_id"):
        print(indent + DIM + f"  Réponse à #{post['parent_id']}" + RESET)

    rule_len = max(18, terminal_width() - len(indent) - 13)
    print(indent + CYAN + "  ┌─ INFO " + "─" * rule_len + RESET)

    max_text = max(20, terminal_width() - len(indent) - 6)
    for text in post["info"].replace("\r", "").split("\n"):
        if not text:
            print(indent + WHITE + "  │ " + RESET)
            continue
        while len(text) > max_text:
            print(indent + WHITE + "  │ " + text[:max_text] + RESET)
            text = text[max_text:]
        print(indent + WHITE + "  │ " + text + RESET)

    print(indent + CYAN + "  └" + "─" * max(20, terminal_width() - len(indent) - 3) + RESET)


def show_posts():
    clear()
    banner()
    w = inner_width()
    print(GREEN + BOLD + "╔" + "═" * w + "╗")
    print(GREEN + "║" + MAGENTA + BOLD + "PUBLICATIONS & RÉPONSES".center(w) + GREEN + "║" + RESET)
    print("╚" + "═" * w + "╝" + RESET)

    status, data = api("/api/posts")
    if status != 200:
        print(RED + f"\n[ERREUR] {data.get('error', 'Erreur inconnue')}" + RESET)
        wait()
        return

    if not data:
        print(YELLOW + "\nAucune publication pour le moment." + RESET)
        wait()
        return

    by_parent = {}
    ids = set()
    for post in data:
        ids.add(post["id"])
        by_parent.setdefault(post.get("parent_id"), []).append(post)

    # Les publications principales les plus récentes d'abord.
    roots = [p for p in data if not p.get("parent_id") or p.get("parent_id") not in ids]
    roots.sort(key=lambda p: p["id"], reverse=True)

    def render_tree(post, level=0):
        print_post(post, level)
        replies = by_parent.get(post["id"], [])
        replies.sort(key=lambda p: p["id"])
        for reply in replies:
            render_tree(reply, level + 1)

    for post in roots:
        render_tree(post)

    print(DIM + "\nPour répondre à quelqu'un : menu 03 puis entre le numéro # du message." + RESET)
    wait()


def multiline_input():
    kb = KeyBindings()

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


def ask_message(title):
    clear()
    banner()
    w = inner_width()
    print(MAGENTA + BOLD + "╔" + "═" * w + "╗")
    print("║" + title.center(w) + "║")
    print("╚" + "═" * w + "╝" + RESET)
    print(DIM + "Aucune identité réelle n'est demandée." + RESET)

    pseudo = input(PINK + "\nPseudo : " + RESET).strip()
    if pseudo == "0":
        return None, None
    if not pseudo:
        print(RED + "Le pseudo est obligatoire." + RESET)
        wait()
        return None, None

    print(CYAN + "\nMESSAGE" + RESET)
    print(DIM + "Entrée = nouvelle ligne | Ctrl+Entrée = envoyer | Ctrl+S = envoyer (secours)" + RESET)
    info = multiline_input()

    if not info:
        print(RED + "Le message est obligatoire." + RESET)
        wait()
        return None, None

    return pseudo, info


def publish():
    pseudo, info = ask_message("NOUVELLE PUBLICATION")
    if not pseudo:
        return

    status, data = api("/api/posts", "POST", {"pseudo": pseudo, "info": info})
    if status == 201:
        print(GREEN + f"\n✓ Publication #{data.get('id')} envoyée !" + RESET)
    else:
        print(RED + f"\n✗ {data.get('error', 'Erreur')}" + RESET)
    wait()


def reply():
    clear()
    banner()
    w = inner_width()
    print(CYAN + BOLD + "╔" + "═" * w + "╗")
    print(CYAN + "║" + MAGENTA + BOLD + "RÉPONDRE À UNE PUBLICATION".center(w) + CYAN + "║" + RESET)
    print("╚" + "═" * w + "╝" + RESET)

    raw = input(PINK + "\nNuméro du message (#) : " + RESET).strip().lstrip("#")
    if raw == "0":
        return
    try:
        parent_id = int(raw)
        if parent_id <= 0:
            raise ValueError
    except ValueError:
        print(RED + "\nNuméro de message invalide." + RESET)
        wait()
        return

    status, posts = api("/api/posts")
    if status != 200:
        print(RED + f"\n✗ {posts.get('error', 'Impossible de charger les publications')}" + RESET)
        wait()
        return

    target = next((p for p in posts if p.get("id") == parent_id), None)
    if not target:
        print(RED + f"\nLa publication #{parent_id} n'existe pas." + RESET)
        wait()
        return

    print(DIM + f"\nTu réponds à #{parent_id} de {target['pseudo']}" + RESET)
    preview = target["info"].replace("\n", " ")
    print(WHITE + "« " + preview[:100] + ("..." if len(preview) > 100 else "") + " »" + RESET)

    pseudo = input(PINK + "\nPseudo : " + RESET).strip()
    if not pseudo:
        print(RED + "Le pseudo est obligatoire." + RESET)
        wait()
        return

    print(CYAN + "\nTA RÉPONSE" + RESET)
    print(DIM + "Entrée = nouvelle ligne | Ctrl+Entrée = envoyer | Ctrl+S = envoyer (secours)" + RESET)
    info = multiline_input()
    if not info:
        print(RED + "La réponse est obligatoire." + RESET)
        wait()
        return

    status, data = api("/api/posts", "POST", {
        "pseudo": pseudo,
        "info": info,
        "parent_id": parent_id
    })

    if status == 201:
        print(GREEN + f"\n✓ Réponse envoyée sous #{parent_id} !" + RESET)
    else:
        print(RED + f"\n✗ {data.get('error', 'Erreur')}" + RESET)
    wait()


def menu():
    while True:
        clear()
        banner()
        w = inner_width()
        print(GREEN + "╔" + "═" * w + "╗")
        print(GREEN + "║" + MAGENTA + BOLD + "MENU".center(w) + GREEN + "║" + RESET)
        print("╠" + "═" * w + "╣")

        def menu_line(num, text, color):
            content = f"    {num}    >    {text}"
            right = max(0, w - len(content))
            print("║" + color + BOLD + content + RESET + GREEN + " " * right + "║")

        print("║" + " " * w + "║")
        menu_line("01", "Voir les publications et réponses", PINK)
        print("║" + " " * w + "║")
        menu_line("02", "Publier une information", CYAN)
        print("║" + " " * w + "║")
        menu_line("03", "Répondre à une publication", MAGENTA)
        print("║" + " " * w + "║")
        menu_line("04", "Quitter", YELLOW)
        print("║" + " " * w + "║")
        print("╚" + "═" * w + "╝" + RESET)

        choice = input(PINK + "\nFORUM > " + RESET).strip()

        if choice == "01":
            show_posts()
        elif choice == "02":
            publish()
        elif choice == "03":
            reply()
        elif choice == "04":
            clear()
            print(LIME + "\nMerci d'avoir utilisé SLIME FORUM !" + RESET)
            time.sleep(1)
            break
        else:
            print(RED + "\nChoix invalide. Utilise 01, 02, 03 ou 04." + RESET)
            time.sleep(1)


def main():
    enable_terminal()
    menu()


if __name__ == "__main__":
    main()
