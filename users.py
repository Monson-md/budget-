import re
import secrets
import hashlib
import hmac
import smtplib
from email.message import EmailMessage
import streamlit as st
import bcrypt
from datetime import datetime, timedelta
from currency import DEFAULT_ALERT_THRESHOLDS

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 5 * 60
RESET_TOKEN_TTL_SECONDS = 30 * 60

# --- "RESTER CONNECTÉ" (JETON PERSISTANT EN COOKIE) ---
REMEMBER_COOKIE_NAME = "pb_remember_token"
REMEMBER_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 jours


def _hash_remember_token(token):
    # Un jeton haute entropie (secrets.token_urlsafe) est vérifié à chaque
    # chargement de page : sha256 suffit ici (contrairement au mot de passe,
    # pas besoin du ralentissement volontaire de bcrypt).
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _compute_uid(email):
    """Identifiant de collection Firestore dérivé de l'email.

    Un hash SHA-256 (plutôt que l'email en clair) évite toute collision entre
    emails différents et tout conflit avec les contraintes de nommage des
    collections Firestore (pas de "/", pas de "." ou ".." seul, etc.) : les
    caractères hexadécimaux sont toujours valides quel que soit le contenu de
    l'email."""
    return hashlib.sha256(email.encode('utf-8')).hexdigest()


def _issue_remember_me_cookie(email, db, cookie_manager):
    """Génère un nouveau jeton, l'enregistre comme un nouveau document d'appareil
    dans users/<email>/remember_tokens/<tokenId> et pose le jeton en clair dans
    un cookie navigateur. Un document par appareil : se connecter sur un
    nouvel appareil ne déconnecte pas les autres."""
    try:
        token = secrets.token_urlsafe(32)
        token_id = _hash_remember_token(token)
        now = datetime.now()
        db.set_remember_token(email, token_id, {
            "hash": token_id,
            "created_at": now.timestamp(),
            "expires_at": now.timestamp() + REMEMBER_TOKEN_TTL_SECONDS,
        })
        cookie_manager.set(
            REMEMBER_COOKIE_NAME,
            f"{email}:{token}",
            expires_at=now + timedelta(seconds=REMEMBER_TOKEN_TTL_SECONDS),
            key="set_remember_cookie",
        )
    except Exception:
        # Le "rester connecté" est une commodité, pas une fonction critique :
        # un échec ici ne doit jamais empêcher la connexion elle-même.
        pass


def _purge_expired_remember_tokens(email, db):
    """Supprime les jetons "rester connecté" expirés d'un utilisateur, pour ne
    pas accumuler indéfiniment de documents dans la sous-collection. Best
    effort : appelé à l'occasion d'une connexion réussie, jamais bloquant."""
    try:
        now_ts = datetime.now().timestamp()
        for token_doc in db.list_remember_tokens(email):
            if token_doc.get('expires_at', 0) < now_ts:
                db.delete_remember_token(email, token_doc['id'])
    except Exception:
        pass


def try_remember_me_login(db, cookie_manager):
    """Reconnecte automatiquement l'utilisateur si un cookie "rester connecté"
    valide est présent. Ne fait jamais échouer l'app ni afficher d'erreur :
    cookie absent, expiré ou invalide => on retombe silencieusement sur
    l'écran de connexion normal."""
    try:
        raw_cookie = cookie_manager.get(cookie=REMEMBER_COOKIE_NAME)
        if not raw_cookie or ':' not in raw_cookie:
            return

        email, token = raw_cookie.split(':', 1)
        email = email.lower().strip()

        user_data = db.get_user(email)
        if not user_data:
            return

        # Un compte verrouillé (échecs de connexion répétés) ne doit pas rester
        # accessible via un cookie émis avant le verrouillage : sinon le
        # lockout ne protège que le formulaire de connexion, pas le compte.
        locked_until = user_data.get('locked_until')
        if locked_until and datetime.now().timestamp() < locked_until:
            return

        token_id = _hash_remember_token(token)
        token_data = db.get_remember_token(email, token_id)
        if not token_data:
            return

        stored_hash = token_data.get('hash')
        expires_at = token_data.get('expires_at', 0)
        if not stored_hash or not expires_at:
            return
        if datetime.now().timestamp() > expires_at:
            return
        if not hmac.compare_digest(stored_hash, token_id):
            return

        base_currency = user_data.get('base_currency', 'XOF')
        st.session_state['user'] = email
        st.session_state['role'] = user_data.get('role', 'user')
        st.session_state['base_currency'] = base_currency
        st.session_state['alert_threshold'] = user_data.get(
            'alert_threshold', DEFAULT_ALERT_THRESHOLDS.get(base_currency, 500)
        )
        st.session_state['uid'] = _compute_uid(email)
    except Exception:
        return

# --- FONCTION DE CONNEXION ---
def login(email, password, db, cookie_manager=None, remember_me=False):
    """Gère la connexion de l'utilisateur avec validation stricte et blocage anti brute-force.

    cookie_manager / remember_me : si un CookieManager est fourni et que
    l'utilisateur a coché "rester connecté", un jeton persistant est émis
    après une connexion réussie (voir _issue_remember_me_cookie)."""
    if not email or not password:
        st.error("Veuillez remplir tous les champs.")
        return

    email = email.lower().strip() # Nettoyage de l'email

    try:
        user_data = db.get_user(email)

        # Blocage temporaire si trop de tentatives échouées récentes sur ce compte
        if user_data:
            locked_until = user_data.get('locked_until')
            if locked_until and datetime.now().timestamp() < locked_until:
                minutes_left = max(1, int((locked_until - datetime.now().timestamp()) // 60) + 1)
                st.error(f"Compte temporairement bloqué suite à plusieurs échecs. Réessayez dans environ {minutes_left} min.")
                return

        # Même message générique dans tous les cas (email inconnu ou mot de passe
        # erroné) pour ne pas laisser un attaquant déduire quels comptes existent.
        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data.get('password_hash', '').encode('utf-8')):
            if user_data.get('failed_attempts'):
                db.update_user(email, {"failed_attempts": 0, "locked_until": None})

            # Entretien opportuniste : purge les jetons "rester connecté"
            # expirés de ce compte à chaque connexion réussie.
            _purge_expired_remember_tokens(email, db)

            base_currency = user_data.get('base_currency', 'XOF')

            st.session_state['user'] = email
            st.session_state['role'] = user_data.get('role', 'user')
            st.session_state['base_currency'] = base_currency
            st.session_state['alert_threshold'] = user_data.get(
                'alert_threshold', DEFAULT_ALERT_THRESHOLDS.get(base_currency, 500)
            )
            # Création d'un UID propre pour les collections Firestore
            st.session_state['uid'] = _compute_uid(email)

            if remember_me and cookie_manager is not None:
                _issue_remember_me_cookie(email, db, cookie_manager)

            st.success(f"Bienvenue, {email} !")
            st.rerun()
        else:
            if user_data:
                attempts = user_data.get('failed_attempts', 0) + 1
                updates = {"failed_attempts": attempts}
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    updates["locked_until"] = datetime.now().timestamp() + LOCKOUT_DURATION_SECONDS
                db.update_user(email, updates)
            st.error("Identifiants incorrects.")
    except Exception:
        # On n'affiche jamais le détail brut de l'exception (elle peut référencer
        # le mot de passe ou les identifiants) : message générique uniquement.
        st.error("Erreur système lors de la connexion. Réessayez plus tard.")

# --- FONCTION D'INSCRIPTION ---
def register(email, password, db, role="user", base_currency="XOF"):
    """Gère l'inscription avec vérification de format."""
    if not email or len(password) < 6:
        st.error("L'email est requis et le mot de passe doit faire 6 caractères min.")
        return False

    email = email.lower().strip()

    if not EMAIL_REGEX.match(email):
        st.error("Format d'email invalide.")
        return False

    if base_currency not in DEFAULT_ALERT_THRESHOLDS:
        base_currency = "XOF"

    try:
        # Vérification si l'utilisateur existe déjà
        if db.get_user(email):
            st.warning("Cet email est déjà utilisé.")
            return False

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # CORRECTION : On utilise une vraie chaîne de date ISO, pas un widget Streamlit !
        new_user_data = {
            "email": email,
            "password_hash": hashed_password,
            "role": role,
            "base_currency": base_currency,
            "alert_threshold": DEFAULT_ALERT_THRESHOLDS.get(base_currency, 500),
            "failed_attempts": 0,
            "locked_until": None,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Date propre pour Firebase
        }

        if db.save_user(email, new_user_data):
            st.success("🎉 Compte créé avec succès ! Basculez sur l'onglet 'Connexion' pour entrer.")
            st.balloons()
            return True
    except Exception:
        # Idem : pas de détail brut d'exception affiché à l'écran.
        st.error("Erreur lors de la création du compte. Réessayez plus tard.")
        return False
    return False

# --- FONCTION DE RÉINITIALISATION DE MOT DE PASSE ---

def _send_reset_email(email, token):
    """Envoie le code de réinitialisation par email via SMTP, configuré dans
    st.secrets["smtp"] (jamais codé en dur). Retourne True si l'email a bien
    été envoyé, False sinon (secrets SMTP absents ou incomplets, erreur
    réseau/authentification...) : l'appelant retombe alors sur le flux manuel
    existant (récupération du code dans la console Firestore) sans planter."""
    try:
        smtp_config = st.secrets["smtp"]
    except (KeyError, FileNotFoundError):
        return False

    required_keys = ("host", "port", "username", "password", "sender")
    if not all(k in smtp_config for k in required_keys):
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = "ProBudget AI - Réinitialisation de votre mot de passe"
        msg["From"] = smtp_config["sender"]
        msg["To"] = email
        msg.set_content(
            "Voici ton code de réinitialisation ProBudget AI :\n\n"
            f"{token}\n\n"
            f"Ce code expire dans {RESET_TOKEN_TTL_SECONDS // 60} minutes. "
            "Si tu n'es pas à l'origine de cette demande, ignore cet email."
        )

        with smtplib.SMTP(smtp_config["host"], int(smtp_config["port"]), timeout=10) as server:
            if smtp_config.get("use_tls", True):
                server.starttls()
            server.login(smtp_config["username"], smtp_config["password"])
            server.send_message(msg)
        return True
    except Exception:
        return False


def request_password_reset(email, db):
    """Génère un token de réinitialisation temporaire stocké dans Firestore et
    tente de l'envoyer automatiquement par email (voir _send_reset_email).

    Si les secrets SMTP sont absents, incomplets, ou si l'envoi échoue, on
    retombe proprement sur le comportement manuel existant : le token doit
    être récupéré dans la console Firestore (document users/<email>, champ
    reset_token) et transmis à l'utilisateur par un canal de confiance.

    Le message affiché ne varie jamais selon que le compte existe ou que
    l'email a réellement été envoyé, pour ne pas laisser un attaquant déduire
    quels comptes existent à partir de la réponse.
    """
    if not email:
        st.error("Veuillez indiquer votre email.")
        return

    email = email.lower().strip()

    try:
        user_data = db.get_user(email)
        if user_data:
            token = secrets.token_urlsafe(24)
            expires_at = datetime.now().timestamp() + RESET_TOKEN_TTL_SECONDS
            db.update_user(email, {"reset_token": token, "reset_token_expires": expires_at})
            _send_reset_email(email, token)
    except Exception:
        pass

    st.info(
        "Si ce compte existe, un code de réinitialisation vient d'être généré. "
        "Il te sera transmis automatiquement par email si l'envoi est configuré ; "
        "sinon, contacte l'administrateur pour le récupérer."
    )

def reset_password(email, token, new_password, db):
    """Réinitialise le mot de passe si le token fourni est valide et non expiré."""
    if not email or not token or len(new_password) < 6:
        st.error("Champs invalides : email, code et mot de passe (6 caractères min.) sont requis.")
        return False

    email = email.lower().strip()

    try:
        user_data = db.get_user(email)
        stored_token = user_data.get('reset_token') if user_data else None
        expires_at = user_data.get('reset_token_expires', 0) if user_data else 0

        if not stored_token or stored_token != token or datetime.now().timestamp() > expires_at:
            st.error("Code de réinitialisation invalide ou expiré.")
            return False

        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db.update_user(email, {
            "password_hash": hashed_password,
            "reset_token": None,
            "reset_token_expires": None,
            "failed_attempts": 0,
            "locked_until": None,
        })
        st.success("Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter.")
        return True
    except Exception:
        st.error("Erreur lors de la réinitialisation du mot de passe. Réessayez plus tard.")
        return False

# --- FONCTION DE DÉCONNEXION ---
def logout(db=None, cookie_manager=None):
    """Nettoyage complet de la session. N'invalide que le jeton "rester
    connecté" de l'appareil courant (lu depuis son propre cookie) : les autres
    appareils connectés avec le même compte restent connectés."""
    if st.sidebar.button("Déconnexion", key="logout_btn"):
        email = st.session_state.get('user')

        if db is not None and email and cookie_manager is not None:
            try:
                raw_cookie = cookie_manager.get(cookie=REMEMBER_COOKIE_NAME)
                if raw_cookie and ':' in raw_cookie:
                    _, token = raw_cookie.split(':', 1)
                    db.delete_remember_token(email, _hash_remember_token(token))
            except Exception:
                pass

        if cookie_manager is not None:
            try:
                if cookie_manager.get(cookie=REMEMBER_COOKIE_NAME):
                    cookie_manager.delete(REMEMBER_COOKIE_NAME, key="delete_remember_cookie")
            except Exception:
                pass

        # On vide tout le dictionnaire de session pour la sécurité
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
