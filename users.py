import re
import secrets
import hashlib
import hmac
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


def _issue_remember_me_cookie(email, db, cookie_manager):
    """Génère un nouveau jeton, stocke son hash+expiration dans Firestore et
    pose le jeton en clair dans un cookie navigateur."""
    try:
        token = secrets.token_urlsafe(32)
        expires_at_ts = datetime.now().timestamp() + REMEMBER_TOKEN_TTL_SECONDS
        db.update_user(email, {
            "remember_token_hash": _hash_remember_token(token),
            "remember_token_expires": expires_at_ts,
        })
        cookie_manager.set(
            REMEMBER_COOKIE_NAME,
            f"{email}:{token}",
            expires_at=datetime.now() + timedelta(seconds=REMEMBER_TOKEN_TTL_SECONDS),
            key="set_remember_cookie",
        )
    except Exception:
        # Le "rester connecté" est une commodité, pas une fonction critique :
        # un échec ici ne doit jamais empêcher la connexion elle-même.
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

        stored_hash = user_data.get('remember_token_hash')
        expires_at = user_data.get('remember_token_expires', 0)
        if not stored_hash or not expires_at:
            return
        if datetime.now().timestamp() > expires_at:
            return
        if not hmac.compare_digest(stored_hash, _hash_remember_token(token)):
            return

        base_currency = user_data.get('base_currency', 'XOF')
        st.session_state['user'] = email
        st.session_state['role'] = user_data.get('role', 'user')
        st.session_state['base_currency'] = base_currency
        st.session_state['alert_threshold'] = user_data.get(
            'alert_threshold', DEFAULT_ALERT_THRESHOLDS.get(base_currency, 500)
        )
        st.session_state['uid'] = email.replace('.', '_').replace('@', '_at_')
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

            base_currency = user_data.get('base_currency', 'XOF')

            st.session_state['user'] = email
            st.session_state['role'] = user_data.get('role', 'user')
            st.session_state['base_currency'] = base_currency
            st.session_state['alert_threshold'] = user_data.get(
                'alert_threshold', DEFAULT_ALERT_THRESHOLDS.get(base_currency, 500)
            )
            # Création d'un UID propre pour les collections Firestore
            st.session_state['uid'] = email.replace('.', '_').replace('@', '_at_')

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
def request_password_reset(email, db):
    """Génère un token de réinitialisation temporaire stocké dans Firestore.

    Aucun service d'email n'est configuré pour l'instant : le token n'est
    jamais renvoyé à l'appelant de ce formulaire (afficher le token à qui le
    demande permettrait à n'importe qui connaissant l'email d'une victime de
    réinitialiser son mot de passe). Il doit être récupéré manuellement dans
    la console Firestore (document users/<email>, champ reset_token) puis
    transmis à l'utilisateur par un canal de confiance (SMS, WhatsApp, etc.).
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
    except Exception:
        pass

    # Message générique dans tous les cas, pour ne pas révéler si l'email existe.
    st.info("Si ce compte existe, une demande de réinitialisation a été enregistrée. Contactez l'administrateur pour récupérer votre code temporaire.")

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
    """Nettoyage complet de la session, y compris le jeton "rester connecté"
    (invalidé côté Firestore et supprimé du cookie navigateur)."""
    if st.sidebar.button("Déconnexion", key="logout_btn"):
        email = st.session_state.get('user')

        if db is not None and email:
            try:
                db.update_user(email, {
                    "remember_token_hash": None,
                    "remember_token_expires": None,
                })
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
