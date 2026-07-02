# utils/auth.py — DEMO version (hardcoded users, no Supabase)
DEMO_PASSWORD = "demo1234"

DEMO_USERS = {
    "demo@demo.com":          {"ucm_username": "demo@demo.com",          "email": "demo@demo.com",          "display_name": "Demo User",     "role": "admin",  "password_hash": "demo1234", "must_change_password": False},
    "alex.rivera@demo.com":   {"ucm_username": "alex.rivera@demo.com",   "email": "alex.rivera@demo.com",   "display_name": "Alex Rivera",   "role": "admin",  "password_hash": "demo1234", "must_change_password": False},
    "jordan.kim@demo.com":    {"ucm_username": "jordan.kim@demo.com",    "email": "jordan.kim@demo.com",    "display_name": "Jordan Kim",    "role": "admin",  "password_hash": "demo1234", "must_change_password": False},
    "sam.patel@demo.com":     {"ucm_username": "sam.patel@demo.com",     "email": "sam.patel@demo.com",     "display_name": "Sam Patel",     "role": "admin",  "password_hash": "demo1234", "must_change_password": False},
    "casey.morgan@demo.com":  {"ucm_username": "casey.morgan@demo.com",  "email": "casey.morgan@demo.com",  "display_name": "Casey Morgan",  "role": "viewer", "password_hash": "demo1234", "must_change_password": False},
    "taylor.brooks@demo.com": {"ucm_username": "taylor.brooks@demo.com", "email": "taylor.brooks@demo.com", "display_name": "Taylor Brooks", "role": "viewer", "password_hash": "demo1234", "must_change_password": False},
}

def get_user(ucm_username: str):
    return DEMO_USERS.get(ucm_username.lower().strip())

def verify_password(plain: str, hashed: str) -> bool:
    return plain == hashed

def get_all_users():
    return [{"ucm_username": u["ucm_username"], "email": u["email"],
             "display_name": u["display_name"], "role": u["role"],
             "must_change_password": u["must_change_password"]}
            for u in DEMO_USERS.values()]

def add_user(ucm_username, email, display_name, role): raise RuntimeError("Disabled in demo.")
def update_user(lookup_username, **fields):             raise RuntimeError("Disabled in demo.")
def delete_user(ucm_username):                          raise RuntimeError("Disabled in demo.")
def update_password(ucm_username, new_password):        raise RuntimeError("Disabled in demo.")
def reset_password(ucm_username):                       return False
def hash_password(plain):                               return plain
def generate_temp_password(length=12):                  return DEMO_PASSWORD
