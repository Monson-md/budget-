import re
import secrets
import streamlit as st
import bcrypt
from datetime import datetime
from currency import DEFAULT_ALERT_THRESHOLDS

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 5 * 60
RESET_TOKEN_TTL_SECONDS = 30 * 60

# --- FONCTION DE CONNEXION ---
def login(email, password, db):
    """Gère la connexion de l'utilisateur avec validation stricte et blocage anti brute-force."""
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
def logout():
    """Nettoyage complet de la session."""
    if st.sidebar.button("Déconnexion", key="logout_btn"):
        # On vide tout le dictionnaire de session pour la sécurité
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
