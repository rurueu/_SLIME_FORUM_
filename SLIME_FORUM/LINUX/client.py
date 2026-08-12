import base64
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import time
import threading
import shutil
import re
import hashlib
import getpass
import unicodedata
import uuid
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


def load_server_url():
    env_url = os.environ.get("SLIME_FORUM_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    return base64.b64decode("aHR0cHM6Ly9zbGltZS1mb3J1bS5vbnJlbmRlci5jb20=").decode("utf-8")


SERVER_URL = load_server_url()

ACTIVE_ADMIN_SECRET = None
ACTIVE_ADMIN_ROLE = None

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

CREATOR_TAG = "@C@"
STAFF_TAG = "@S@"
CREATOR_NAME = "CREATEUR"

def rainbow_text(text, phase=None):
    # Effet arc-en-ciel : la phase change régulièrement.
    # À chaque nouvel affichage / rafraîchissement, les couleurs se déplacent.
    colors = [
        "\033[91m",        # rouge
        "\033[38;5;208m", # orange
        "\033[93m",        # jaune
        "\033[92m",        # vert
        "\033[96m",        # cyan
        "\033[94m",        # bleu
        "\033[95m",        # violet
        PINK,
    ]
    if phase is None:
        phase = int(time.time() * 4)
    out = []
    for i, ch in enumerate(text):
        out.append(colors[(i + phase) % len(colors)] + ch)
    return BOLD + "".join(out) + RESET


def staff_diamond_text(text):
    # Bleu diamant : bleu clair + cyan + petits diamants autour du pseudo.
    diamond = "\033[96m◆"
    blue = "\033[94m"
    ice = "\033[38;5;117m"
    out = []
    palette = [blue, ice, CYAN]
    for i, ch in enumerate(text):
        out.append(palette[i % len(palette)] + ch)
    return BOLD + diamond + " " + "".join(out) + " " + diamond + RESET


def display_pseudo(raw_pseudo):
    if raw_pseudo.startswith(CREATOR_TAG):
        name = raw_pseudo[len(CREATOR_TAG):] or CREATOR_NAME
        return rainbow_text(name)

    if raw_pseudo.startswith(STAFF_TAG):
        name = raw_pseudo[len(STAFF_TAG):] or "STAFF"
        return staff_diamond_text(name)

    return WHITE + raw_pseudo + RESET


def normalize_reserved_name(value):
    # Insensible aux majuscules/minuscules, accents, espaces, tirets et underscores.
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    return "".join(ch for ch in value if ch.isalnum())


RESERVED_STAFF_NAMES = {"createur", "admin", "staff"}


def ask_pseudo():
    global ACTIVE_ADMIN_SECRET, ACTIVE_ADMIN_ROLE

    while True:
        raw = input(PINK + "\nPseudo > " + RESET).strip()

        if raw == "0":
            return None

        if not raw:
            print(RED + "Le pseudo est obligatoire." + RESET)
            continue

        normalized = normalize_reserved_name(raw)

        if normalized in RESERVED_STAFF_NAMES:
            print(MAGENTA + "\nAccès personnel protégé" + RESET)
            password = getpass.getpass("Code d'accès > ")

            previous_secret = ACTIVE_ADMIN_SECRET
            previous_role = ACTIVE_ADMIN_ROLE

            ACTIVE_ADMIN_SECRET = password

            if normalized == "createur":
                ACTIVE_ADMIN_ROLE = "creator"
            elif normalized == "admin":
                ACTIVE_ADMIN_ROLE = "admin"
            else:
                ACTIVE_ADMIN_ROLE = "staff"

            status, data = api("/api/admin/auth", admin=True)

            if status != 200 or not data.get("ok"):
                ACTIVE_ADMIN_SECRET = previous_secret
                ACTIVE_ADMIN_ROLE = previous_role
                print(RED + "✗ Code refusé." + RESET)
                time.sleep(1)
                continue

            if normalized == "createur":
                role_pseudo = CREATOR_TAG + CREATOR_NAME
                print(GREEN + "✓ Accès Créateur activé." + RESET)
            elif normalized == "admin":
                role_pseudo = STAFF_TAG + "ADMIN"
                print(CYAN + "✓ Accès Admin activé." + RESET)
            else:
                role_pseudo = STAFF_TAG + "STAFF"
                print(CYAN + "✓ Accès Staff activé." + RESET)

            time.sleep(0.4)
            admin_panel(role_pseudo)

            ACTIVE_ADMIN_SECRET = None
            ACTIVE_ADMIN_ROLE = None
            return None

        return raw


def confidentiality_info():
    clear()
    banner()
    w = inner_width()
    print(MAGENTA + BOLD + "╔" + "═" * w + "╗")
    print("║" + "06 — CONFIDENTIALITÉ ET INFORMATIONS".center(w) + "║")
    print("╚" + "═" * w + "╝" + RESET)
    print()
    paragraphs = ['Bienvenue dans la section Confidentialité et informations de SLIME FORUM.', 'SLIME FORUM est un forum en ligne conçu pour être utilisé directement depuis un terminal Windows, Linux ou macOS.', 'Les trois versions utilisent la même interface générale et communiquent avec le même serveur afin que les publications et les réponses soient visibles par tous les utilisateurs, quel que soit leur système.', "Le fonctionnement repose sur des pseudonymes : au moment de publier ou de répondre, l'utilisateur choisit le nom qui sera affiché avec son message.", "Aucun compte classique avec profil public n'est nécessaire pour utiliser les fonctions principales du forum.", 'Chaque publication reçoit automatiquement un numéro unique précédé du symbole #. Ce numéro sert à identifier précisément un message et permet notamment au système de réponses de rattacher une discussion à la bonne publication.', 'Les réponses apparaissent sous le message auquel elles sont associées afin de rendre les conversations faciles à suivre directement dans le terminal.', "Le menu 01 permet de consulter les publications et leurs réponses. Le menu 02 permet d'écrire une nouvelle publication. Le menu 03 permet de répondre à une publication existante en indiquant son numéro. Le menu 04 ferme le programme.", 'Le menu 06 contient les informations générales concernant le fonctionnement du forum, la confidentialité, les pseudonymes, le personnel et la modération.', "Lors de la rédaction d'un message, Entrée permet de revenir à la ligne. La combinaison Ctrl+Entrée permet d'envoyer le texte lorsque le terminal prend correctement en charge cette combinaison. Ctrl+S est également disponible comme méthode de secours dans le client.", "Les messages envoyés transitent par le serveur du forum. Le serveur enregistre les informations nécessaires au fonctionnement des publications et des réponses afin qu'elles puissent être récupérées lors des prochaines connexions.", 'Fermer le programme sur son ordinateur ne ferme pas le forum : les autres utilisateurs peuvent continuer à publier et consulter les discussions tant que le serveur est disponible.', "Le Créateur possède un pseudo arc-en-ciel animé dont les couleurs se déplacent à chaque rafraîchissement de l'interface. Les membres Staff et Admin disposent d'un pseudo bleu diamant facilement reconnaissable dans les publications et les réponses.", "Le Créateur, les Staff et les Admin disposent des mêmes outils de modération supplémentaires, accessibles après activation de leur statut personnel.", "Les outils de modération permettent notamment de publier normalement, de supprimer une publication et d'empêcher une installation du client d'envoyer ou de consulter de nouveaux messages lorsqu'une mesure de bannissement est appliquée.", "Pour préserver le principe du forum, le bannissement proposé par cette version repose sur un identifiant aléatoire propre à l'installation du client et non sur la collecte du numéro de série du processeur, de la carte mère, du disque ou d'autres composants matériels.", "Cet identifiant d'installation est créé localement lors de la première utilisation et sert uniquement au fonctionnement de la modération du forum.", "Un bannissement peut être appliqué à l'installation ayant créé une publication sélectionnée par le personnel. Le serveur associe alors l'identifiant concerné à la liste de modération.", "Les informations techniques internes utilisées par le programme ne sont pas destinées à être affichées dans l'interface publique du forum.", "SLIME FORUM utilise une connexion Internet pour récupérer les publications, envoyer les nouveaux messages, transmettre les réponses et vérifier l'état nécessaire au fonctionnement du service.", "Les couleurs, cadres et éléments ASCII font partie de l'interface terminal et peuvent légèrement varier selon la police, le terminal et le système d'exploitation utilisés.", "Windows utilise le lanceur .bat, Linux utilise le lanceur .sh et macOS utilise le lanceur .command. Chaque lanceur prépare l'environnement Python nécessaire puis démarre le même client SLIME FORUM.", "Python 3 est nécessaire au fonctionnement du client. Les dépendances complémentaires sont installées à partir du fichier requirements.txt dans l'environnement prévu par le programme.", "Le forum est organisé autour d'un client et d'un serveur : le client gère l'affichage et la saisie dans le terminal, tandis que le serveur centralise les publications, les réponses et les informations nécessaires à la modération.", "Le respect entre utilisateurs reste essentiel au fonctionnement des discussions : les insultes, attaques personnelles et le harcèlement envers les autres utilisateurs n'ont pas leur place dans les échanges.", 'Cette section peut évoluer avec les prochaines versions de SLIME FORUM lorsque de nouvelles fonctions sont ajoutées au client ou aux outils du personnel.']
    for paragraph in paragraphs:
        words = paragraph.split()
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > max(50, terminal_width() - 8):
                print(WHITE + "  " + current + RESET)
                current = word
            else:
                current = word if not current else current + " " + word
        if current:
            print(WHITE + "  " + current + RESET)
        print()
    wait()


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


def installation_id():
    path = Path(__file__).with_name(".slime_installation_id")
    try:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = uuid.uuid4().hex
        path.write_text(value, encoding="utf-8")
        return value
    except Exception:
        return "temporary-" + uuid.uuid4().hex


INSTALLATION_ID = installation_id()


def api(path, method="GET", payload=None, admin=False):
    url = SERVER_URL.rstrip("/") + path
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "SLIME-FORUM/1.0",
        "X-Slime-Client": INSTALLATION_ID,
    }

    if admin and ACTIVE_ADMIN_SECRET:
        headers["X-Slime-Admin-Secret"] = ACTIVE_ADMIN_SECRET
        if ACTIVE_ADMIN_ROLE:
            headers["X-Slime-Admin-Role"] = ACTIVE_ADMIN_ROLE

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=70) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"error": f"Erreur HTTP {e.code}"}
        return e.code, body
    except Exception as e:
        return 0, {"error": f"Serveur inaccessible : {e}"}


def show_ban_screen(data):
    clear()
    banner()
    w = inner_width()

    title = "VOUS AVEZ ÉTÉ BANNI"
    print(RED + BOLD + "╔" + "═" * w + "╗")
    print("║" + title.center(w) + "║")
    print("╠" + "═" * w + "╣")

    duration = str(data.get("remaining", "Durée inconnue"))
    reason = str(data.get("reason", "Bannissement appliqué par le personnel."))

    rows = [
        "",
        "Votre installation SLIME FORUM est actuellement bannie.",
        "",
        f"Temps restant : {duration}",
        f"Information : {reason}",
        "",
    ]

    for row in rows:
        text = row[:max(0, w - 6)]
        print("║   " + WHITE + text + RED + " " * max(0, w - len(text) - 3) + "║")

    print("╚" + "═" * w + "╝" + RESET)
    input(DIM + "\nAppuie sur Entrée pour fermer..." + RESET)


def check_ban():
    status, data = api("/api/status")
    if status == 403 and data.get("banned"):
        show_ban_screen(data)
        return True
    return False


def wait():
    input(CYAN + "\nAppuie sur Entrée pour continuer..." + RESET)


def print_post(post, level=0):
    indent = "    " * min(level, 5)
    prefix = "↳ " if level else ""
    header_color = CYAN if level else PINK

    print()
    print(indent + header_color + f"  {prefix}#{post['id']}  Pseudo : " + display_pseudo(post["pseudo"]))

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
    """
    Affiche les publications avec rafraîchissement automatique.
    L'écran est rechargé toutes les 5 secondes tant qu'on reste dans cette section.
    """
    stop_refresh = threading.Event()
    action_lock = threading.Lock()
    action_state = {"choice": None}

    def render_publications():
        clear()
        banner()
        w = inner_width()

        print(GREEN + BOLD + "╔" + "═" * w + "╗")
        print(GREEN + "║" + MAGENTA + BOLD + "PUBLICATIONS & RÉPONSES".center(w) + GREEN + "║" + RESET)
        print("╠" + "═" * w + "╣")

        refresh_text = "Rafraîchissement automatique : toutes les 5 secondes"
        print("║" + CYAN + refresh_text.center(w) + GREEN + "║" + RESET)
        print("╚" + "═" * w + "╝" + RESET)

        status, data = api("/api/posts")

        if status == 403 and data.get("banned"):
            show_ban_screen(data)
            return False

        if status != 200:
            print(RED + f"\n[ERREUR] {data.get('error', 'Erreur inconnue')}" + RESET)
            return True

        if not data:
            print(YELLOW + "\nAucune publication pour le moment." + RESET)
        else:
            by_parent = {}
            ids = set()

            for post in data:
                ids.add(post["id"])
                by_parent.setdefault(post.get("parent_id"), []).append(post)

            roots = [
                post for post in data
                if not post.get("parent_id") or post.get("parent_id") not in ids
            ]
            roots.sort(key=lambda post: post["id"], reverse=True)

            def render_tree(post, level=0):
                print_post(post, level)
                replies = by_parent.get(post["id"], [])
                replies.sort(key=lambda reply: reply["id"])
                for child in replies:
                    render_tree(child, level + 1)

            for post in roots:
                render_tree(post)

        print()
        print(MAGENTA + BOLD + "╔" + "═" * w + "╗")
        print("║" + "ACTIONS".center(w) + "║")
        print("╠" + "═" * w + "╣")

        actions = [
            ("01", "Répondre à un message"),
            ("02", "Quitter"),
        ]

        for num, label in actions:
            text = f"    {num}    >    {label}"
            print("║" + PINK + BOLD + text + RESET + MAGENTA + " " * max(0, w - len(text)) + "║")
            print("║" + " " * w + "║")

        print("╚" + "═" * w + "╝" + RESET)
        print(DIM + "\nLa page se met à jour automatiquement. Entre 01 ou 02 puis valide avec Entrée." + RESET)
        return True

    def refresh_loop():
        # Attend 5 secondes, puis redessine tant qu'aucune action utilisateur n'est en cours.
        while not stop_refresh.wait(5):
            with action_lock:
                if action_state["choice"] is None:
                    render_publications()
                    # Réaffiche le prompt après chaque rafraîchissement.
                    print(PINK + BOLD + "\nPUBLICATIONS > " + RESET, end="", flush=True)

    if not render_publications():
        return

    refresher = threading.Thread(target=refresh_loop, daemon=True)
    refresher.start()

    try:
        while True:
            choice = input(PINK + BOLD + "\nPUBLICATIONS > " + RESET).strip()

            with action_lock:
                action_state["choice"] = choice

            if choice == "01":
                stop_refresh.set()
                reply()
                # Au retour de la réponse, relance l'affichage automatique.
                action_state["choice"] = None
                stop_refresh = threading.Event()
                if not render_publications():
                    return
                refresher = threading.Thread(target=refresh_loop, daemon=True)
                refresher.start()

            elif choice == "02":
                stop_refresh.set()
                return

            else:
                print(RED + "\nChoix invalide. Utilise 01 ou 02." + RESET)
                time.sleep(1)
                action_state["choice"] = None
                render_publications()

    finally:
        stop_refresh.set()


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

    pseudo = ask_pseudo()
    if pseudo is None:
        return None, None

    print(CYAN + "\nMESSAGE" + RESET)
    print(DIM + "Entrée = nouvelle ligne | Ctrl+Entrée = envoyer | Ctrl+S = envoyer (secours)" + RESET)
    info = multiline_input()

    if not info:
        print(RED + "Le message est obligatoire." + RESET)
        wait()
        return None, None

    return pseudo, info


def publish_as_role(role_pseudo):
    clear()
    banner()
    w = inner_width()

    print(MAGENTA + BOLD + "╔" + "═" * w + "╗")
    print("║" + "NOUVELLE PUBLICATION — PERSONNEL".center(w) + "║")
    print("╚" + "═" * w + "╝" + RESET)

    print()
    print(CYAN + "Compte actif : " + RESET + display_pseudo(role_pseudo))
    print(CYAN + "\nMESSAGE" + RESET)
    print(DIM + "Entrée = nouvelle ligne | Ctrl+Entrée = envoyer | Ctrl+S = envoyer (secours)" + RESET)

    info = multiline_input()

    if not info:
        print(RED + "Le message est obligatoire." + RESET)
        wait()
        return

    status, data = api("/api/posts", "POST", {
        "pseudo": role_pseudo,
        "info": info
    })

    if status == 201:
        print(GREEN + f"\n✓ Publication #{data.get('id')} envoyée avec le compte personnel !" + RESET)
        print(CYAN + "Publié en tant que : " + RESET + display_pseudo(role_pseudo))
    else:
        print(RED + f"\n✗ {data.get('error', 'Erreur')}" + RESET)

    wait()


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


def staff_show_posts(role_pseudo):
    clear()
    banner()
    print(CYAN + "Session personnelle active : " + RESET + display_pseudo(role_pseudo))
    print()
    show_posts()


def choose_ban_duration():
    clear()
    banner()
    w = inner_width()
    print(RED + BOLD + "╔" + "═" * w + "╗")
    print("║" + "CHOISIR LA DURÉE DU BANNISSEMENT".center(w) + "║")
    print("╠" + "═" * w + "╣")

    options = [
        ("01", "1 jour", "1d"),
        ("02", "1 semaine", "1w"),
        ("03", "1 mois", "1m"),
        ("04", "1 an", "1y"),
        ("05", "À vie", "forever"),
    ]

    for num, label, value in options:
        text = f"    {num}    >    {label}"
        print("║" + PINK + text + RED + " " * max(0, w - len(text)) + "║")
        print("║" + " " * w + "║")

    print("╚" + "═" * w + "╝" + RESET)
    choice = input(PINK + BOLD + "\nDURÉE > " + RESET).strip()

    mapping = {num: (label, value) for num, label, value in options}
    return mapping.get(choice)


def creator_password_manager():
    while True:
        clear()
        banner()
        w = inner_width()

        print(MAGENTA + BOLD + "╔" + "═" * w + "╗")
        print("║" + "GESTION DES MOTS DE PASSE".center(w) + "║")
        print("╠" + "═" * w + "╣")

        options = [
            ("01", "Voir l'état des mots de passe"),
            ("02", "Réinitialiser / changer un mot de passe"),
            ("03", "Retour à l'espace Créateur"),
        ]

        for num, label in options:
            text = f"    {num}    >    {label}"
            print("║" + PINK + BOLD + text + RESET + MAGENTA + " " * max(0, w - len(text)) + "║")
            print("║" + " " * w + "║")

        print("╚" + "═" * w + "╝" + RESET)
        choice = input(PINK + BOLD + "\nGESTION > " + RESET).strip()

        if choice == "01":
            status, data = api("/api/admin/passwords", admin=True)
            if status != 200:
                print(RED + "\n" + data.get("error", "Erreur serveur") + RESET)
                wait()
                continue

            clear()
            banner()
            print(MAGENTA + BOLD + "ÉTAT DES MOTS DE PASSE\n" + RESET)
            print(CYAN + "Créateur : " + (GREEN + "CONFIGURÉ" if data.get("creator") else RED + "NON CONFIGURÉ") + RESET)
            print(CYAN + "Staff/Admin : " + (GREEN + "CONFIGURÉ" if data.get("staff") else RED + "NON CONFIGURÉ") + RESET)
            print(CYAN + "Codage : " + (GREEN + "CONFIGURÉ" if data.get("coding") else RED + "NON CONFIGURÉ") + RESET)
            print(DIM + "\nLes mots de passe eux-mêmes ne sont pas affichés en clair." + RESET)
            wait()

        elif choice == "02":
            clear()
            banner()
            print(MAGENTA + BOLD + "RÉINITIALISER UN MOT DE PASSE\n" + RESET)
            print(PINK + "01  >  Mot de passe Créateur" + RESET)
            print(CYAN + "02  >  Mot de passe Staff/Admin" + RESET)
            print(YELLOW + "03  >  Mot de passe Codage" + RESET)
            print(WHITE + "04  >  Retour" + RESET)

            sub = input(PINK + BOLD + "\nCHOIX > " + RESET).strip()
            mapping = {
                "01": ("creator", "Créateur"),
                "02": ("staff", "Staff/Admin"),
                "03": ("coding", "Codage"),
            }

            if sub == "04":
                continue

            if sub not in mapping:
                print(RED + "Choix invalide." + RESET)
                wait()
                continue

            key, label = mapping[sub]

            new1 = getpass.getpass(f"Nouveau mot de passe {label} > ")
            new2 = getpass.getpass("Confirmer le nouveau mot de passe > ")

            if new1 != new2:
                print(RED + "\nLes deux mots de passe ne correspondent pas." + RESET)
                wait()
                continue

            status, data = api(
                f"/api/admin/passwords/{key}",
                "POST",
                {"new_password": new1},
                admin=True
            )

            if status == 200:
                print(GREEN + "\n✓ " + data.get("message", "Mot de passe mis à jour.") + RESET)

                # Si le Créateur vient de changer SON mot de passe,
                # la session actuelle garde l'ancien secret et doit être refermée.
                if key == "creator":
                    print(YELLOW + "Le mot de passe Créateur a changé. Reconnecte-toi avec le nouveau code." + RESET)
                    wait()
                    return "creator_changed"
            else:
                print(RED + "\n" + data.get("error", "Erreur serveur") + RESET)

            wait()

        elif choice == "03":
            return None

        else:
            print(RED + "\nChoix invalide." + RESET)
            time.sleep(1)


def admin_panel(role_pseudo):
    while True:
        clear()
        banner()
        w = inner_width()

        print(MAGENTA + BOLD + "╔" + "═" * w + "╗")
        print("║" + "ESPACE PERSONNEL".center(w) + "║")
        print("╠" + "═" * w + "╣")
        print("║" + " " * w + "║")

        active_label = "Compte actif : "
        print("║    " + CYAN + active_label + RESET + display_pseudo(role_pseudo) + MAGENTA)
        print("║" + " " * w + "║")

        options = [
            ("01", "Voir les publications et réponses"),
            ("02", "Envoyer un message avec ce compte"),
            ("03", "Supprimer un message"),
            ("04", "Bannir l'installation liée à un message"),
            ("05", "Retour au forum"),
        ]

        if ACTIVE_ADMIN_ROLE == "creator":
            options.insert(4, ("07", "Gestion des mots de passe"))
        options.insert(-1, ("08", "Modération & gestion avancée"))

        for num, label in options:
            text = f"    {num}    >    {label}"
            print("║" + PINK + BOLD + text + RESET + MAGENTA + " " * max(0, w - len(text)) + "║")
            print("║" + " " * w + "║")

        print("╚" + "═" * w + "╝" + RESET)
        choice = input(PINK + BOLD + "\nPERSONNEL > " + RESET).strip()

        if choice == "01":
            staff_show_posts(role_pseudo)

        elif choice == "02":
            publish_as_role(role_pseudo)

        elif choice == "03":
            raw = input(PINK + "\nNuméro du message à supprimer (#) > " + RESET).strip().lstrip("#")
            try:
                post_id = int(raw)
            except ValueError:
                print(RED + "Numéro invalide." + RESET)
                wait()
                continue

            status, data = api(f"/api/admin/posts/{post_id}", "DELETE", admin=True)
            if status == 200:
                print(GREEN + "\n" + data.get("message", "Message supprimé.") + RESET)
            else:
                print(RED + "\n" + data.get("error", f"Erreur HTTP {status}") + RESET)
            wait()

        elif choice == "04":
            raw = input(PINK + "\nNuméro du message dont l'auteur doit être banni (#) > " + RESET).strip().lstrip("#")
            try:
                post_id = int(raw)
            except ValueError:
                print(RED + "Numéro invalide." + RESET)
                wait()
                continue

            selected = choose_ban_duration()
            if not selected:
                print(RED + "\nDurée invalide." + RESET)
                wait()
                continue

            label, duration = selected

            status, data = api(
                f"/api/admin/ban-by-post/{post_id}",
                "POST",
                {"duration": duration},
                admin=True
            )

            if status == 200:
                print(GREEN + f"\n✓ {data.get('message', 'Bannissement appliqué.')}" + RESET)
                print(CYAN + f"Durée : {label}" + RESET)
            else:
                print(RED + "\n" + data.get("error", f"Erreur HTTP {status}") + RESET)
            wait()

        elif choice == "07" and ACTIVE_ADMIN_ROLE == "creator":
            result = creator_password_manager()
            if result == "creator_changed":
                return

        elif choice == "08":
            personnel_extra_tools(role_pseudo)

        elif choice == "05":
            return

        else:
            print(RED + "\nChoix invalide." + RESET)
def forum_extra_tools():
    while True:
        clear()
        banner()
        print(MAGENTA + BOLD + "\nOUTILS DU FORUM\n" + RESET)
        print(PINK + "01  >  Rechercher un message / pseudo" + RESET)
        print(PINK + "02  >  Réagir à un message" + RESET)
        print(PINK + "03  >  Statistiques et utilisateurs actifs" + RESET)
        print(PINK + "04  >  Voir les salons" + RESET)
        print(PINK + "05  >  Modifier un de mes messages" + RESET)
        print(PINK + "06  >  Retour" + RESET)
        ch=input(PINK+BOLD+"\nOUTILS > "+RESET).strip()

        if ch=="01":
            q=input("Recherche > ").strip()
            status,data=api("/api/search?q="+urllib.parse.quote(q))
            clear(); banner()
            if status==200:
                for x in data:
                    print(f"#{x.get('id')}  {display_pseudo(x.get('pseudo','?'))}")
                    print("   "+str(x.get("info","")).replace("\n","\n   "))
                    print()
            else: print(RED+data.get("error","Erreur")+RESET)
            wait()

        elif ch=="02":
            raw=input("Numéro du message (#) > ").strip().lstrip("#")
            print("01 > +1   02 > ❤️   03 > 😂   04 > 👍")
            rc=input("Réaction > ").strip()
            mapping={"01":"+1","02":"❤️","03":"😂","04":"👍"}
            if rc in mapping:
                status,data=api(f"/api/posts/{raw}/react","POST",{"reaction":mapping[rc]})
                print((GREEN if status in (200,201) else RED)+data.get("message",data.get("error","Erreur"))+RESET)
            wait()

        elif ch=="03":
            status,data=api("/api/stats")
            clear(); banner()
            if status==200:
                print(CYAN+f"Messages : {data.get('messages',0)}"+RESET)
                print(CYAN+f"Réponses : {data.get('reponses',0)}"+RESET)
                print(CYAN+f"Messages aujourd'hui : {data.get('aujourdhui',0)}"+RESET)
                print(CYAN+f"Installations actives (5 min) : {data.get('actifs_5min',0)}"+RESET)
            else: print(RED+data.get("error","Erreur")+RESET)
            wait()

        elif ch=="04":
            status,data=api("/api/channels")
            clear(); banner()
            if status==200:
                for x in data:
                    suffix=" [OFFICIEL]" if x.get("official_only") else ""
                    print(f"{x.get('id'):02} > {x.get('name')}{suffix}")
            else: print(RED+data.get("error","Erreur")+RESET)
            wait()

        elif ch=="05":
            raw=input("Numéro de TON message (#) > ").strip().lstrip("#")
            print("Nouveau texte :")
            info=multiline_input()
            status,data=api(f"/api/posts/{raw}/edit","POST",{"info":info})
            print((GREEN if status==200 else RED)+data.get("message",data.get("error","Erreur"))+RESET)
            wait()

        elif ch=="06":
            return


def personnel_extra_tools(role_pseudo):
    while True:
        clear(); banner()
        print(MAGENTA+BOLD+"\nMODÉRATION & GESTION\n"+RESET)
        options=[
            ("01","Épingler un message"),("02","Désépingler un message"),
            ("03","Liste des bannissements / débannir"),("04","Journal de modération"),
            ("05","Corbeille / restaurer"),("06","Créer un salon"),
            ("07","Statistiques"),("08","Retour")
        ]
        if ACTIVE_ADMIN_ROLE=="creator":
            options.insert(7,("09","Paramètres Créateur / maintenance"))
        for n,l in options: print(PINK+f"{n}  >  {l}"+RESET)
        ch=input(PINK+BOLD+"\nGESTION > "+RESET).strip()

        if ch in ("01","02"):
            pid=input("Message # > ").strip().lstrip("#")
            method="POST" if ch=="01" else "DELETE"
            status,data=api(f"/api/admin/posts/{pid}/pin",method,admin=True)
            print((GREEN if status==200 else RED)+data.get("message",data.get("error","Erreur"))+RESET); wait()

        elif ch=="03":
            status,data=api("/api/admin/bans",admin=True)
            clear(); banner()
            if status==200:
                if not data: print(YELLOW+"Aucun bannissement."+RESET)
                for i,b in enumerate(data,1):
                    print(f"{i:02} > {b.get('client_id','')[:12]}… | fin: {b.get('expires_at') or 'À VIE'} | {b.get('reason','')}")
                if data:
                    x=input("\nNuméro à débannir, ou Entrée pour retour > ").strip()
                    if x.isdigit() and 1<=int(x)<=len(data):
                        cid=data[int(x)-1]["client_id"]
                        st,dt=api("/api/admin/bans/"+urllib.parse.quote(cid,safe=""),"DELETE",admin=True)
                        print((GREEN if st==200 else RED)+dt.get("message",dt.get("error","Erreur"))+RESET); wait()
            else: print(RED+data.get("error","Erreur")+RESET); wait()

        elif ch=="04":
            status,data=api("/api/admin/log",admin=True)
            clear(); banner()
            if status==200:
                for x in data:
                    print(f"#{x.get('id')} [{x.get('actor_role')}] {x.get('action')} — {x.get('target','')} — {x.get('created_at','')}")
            else: print(RED+data.get("error","Erreur")+RESET)
            wait()

        elif ch=="05":
            status,data=api("/api/admin/trash",admin=True)
            clear(); banner()
            if status==200:
                for x in data:
                    print(f"#{x.get('id')} {x.get('pseudo')} > {str(x.get('info',''))[:80]}")
                if data:
                    pid=input("\n# à restaurer, ou Entrée > ").strip().lstrip("#")
                    if pid:
                        st,dt=api(f"/api/admin/trash/{pid}/restore","POST",{},admin=True)
                        print((GREEN if st==200 else RED)+dt.get("message",dt.get("error","Erreur"))+RESET)
            else: print(RED+data.get("error","Erreur")+RESET)
            wait()

        elif ch=="06":
            name=input("Nom du nouveau salon > ").strip()
            official=input("Salon officiel réservé au personnel ? (o/n) > ").strip().lower()=="o"
            status,data=api("/api/admin/channels","POST",{"name":name,"official_only":official},admin=True)
            print((GREEN if status==201 else RED)+data.get("message",data.get("error","Erreur"))+RESET); wait()

        elif ch=="07":
            status,data=api("/api/stats")
            if status==200:
                print(CYAN+f"\nMessages: {data.get('messages')} | Réponses: {data.get('reponses')} | Actifs: {data.get('actifs_5min')} | Aujourd'hui: {data.get('aujourdhui')}"+RESET)
            else: print(RED+data.get("error","Erreur")+RESET)
            wait()

        elif ch=="09" and ACTIVE_ADMIN_ROLE=="creator":
            status,current=api("/api/settings")
            clear(); banner()
            print(MAGENTA+BOLD+"PARAMÈTRES CRÉATEUR"+RESET)
            print(f"Maintenance actuelle : {current.get('maintenance','0')}")
            print(f"Rafraîchissement : {current.get('refresh_seconds','5')} s")
            print(f"Message d'accueil : {current.get('welcome_message','')}")
            print("\n01 > Basculer maintenance\n02 > Changer délai rafraîchissement\n03 > Changer message d'accueil\n04 > Retour")
            sc=input("> ").strip()
            payload={}
            if sc=="01": payload={"maintenance":"0" if current.get("maintenance")=="1" else "1"}
            elif sc=="02": payload={"refresh_seconds":input("Secondes > ").strip()}
            elif sc=="03": payload={"welcome_message":input("Nouveau message > ").strip()}
            if payload:
                st,dt=api("/api/admin/settings","POST",payload,admin=True)
                print((GREEN if st==200 else RED)+dt.get("message",dt.get("error","Erreur"))+RESET); wait()

        elif ch=="08":
            return


    time.sleep(1)


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
        menu_line("06", "Confidentialité et informations", MAGENTA)
        print("║" + " " * w + "║")
        print("╚" + "═" * w + "╝" + RESET)

        print()
        choice = input(PINK + BOLD + "FORUM > " + RESET).strip()

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
        elif choice == "06":
            confidentiality_info()
        else:
            print(RED + "\nChoix invalide. Utilise 01, 02, 03, 04 ou 06." + RESET)
            time.sleep(1)


def main():
    enable_terminal()

    if check_ban():
        return

    menu()


if __name__ == "__main__":
    main()
