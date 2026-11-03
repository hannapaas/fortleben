"""Accounts: an email address and a password, with their own key (docs/STEERING.md, "Paying: bring your own key").

Anyone can sign up with a name, an email address, a password and their own Meta Model API key, and
has a desk with no allowance: their runs spend their key, capped by the run cap only. The key is
stored encrypted with KEIKAKU_SECRET (Fernet, the key derived with SHA-256), never logged or shown,
and read back only by key_for, for the client a run of theirs builds. The desk shows its last four
characters, can forget it and can take a new one.

The password is kept as an scrypt hash with a salt of its own. Signing in makes a session: a random
id in the fl_session cookie, of which only a hash is stored, for 90 days. Invited editors come in
through their links (house/desk.py), which make the same session, and can add an email address and
password from the desk. A forgotten password gets a reset link by mail, good for an hour and once.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections import defaultdict, deque

from cryptography.fernet import Fernet, InvalidToken

from house.comments import digest

MAX_KEY = 200
SIGNUPS_PER_HOUR = int(os.environ.get("SIGNUPS_PER_HOUR", 5))
LOGINS_PER_HOUR = 10  # attempts, per address and per email address
RESETS_PER_HOUR = 5  # reset mails asked for, per address and per email address
SESSION_DAYS = 90
RESET_HOURS = 1
MIN_PASSWORD, MAX_PASSWORD = 8, 200
TAKEN = "There's already an account with that email address. Sign in instead."
NO_MATCH = "That email and password don't match."
RESET_DEAD = "That reset link has expired or has been used."
RESET_GONE = RESET_DEAD + " Ask for a new one."
WRONG_CURRENT = "That isn't your current password."
MIN_KEY = 12  # no Meta key is shorter; a shorter one is a slip, and its four-character tail would be most of it


class Refused(Exception):
    """A sign-up that can't go ahead; the message is for the person signing up."""


def _fernet(secret: str) -> Fernet:
    if not secret:
        raise RuntimeError("KEIKAKU_SECRET isn't set, so keys can't be stored.")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt(secret: str, text: str) -> str:
    return _fernet(secret).encrypt(text.encode()).decode()


def decrypt(secret: str, token: str) -> str:
    """The text, or InvalidToken if it was encrypted with another secret or altered."""
    return _fernet(secret).decrypt(token.encode()).decode()


def _secret() -> str:
    return os.environ.get("KEIKAKU_SECRET", "")


def _clean_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if not key:
        raise Refused("Paste your key first.")
    if len(key) > MAX_KEY:
        raise Refused("That's longer than any Meta key. Check what you pasted.")
    if not key.isprintable() or any(c.isspace() for c in key):
        raise Refused("That doesn't look like a key: it has spaces or odd characters in it.")
    if len(key) < MIN_KEY:
        raise Refused("That's too short to be a Meta key. Check you pasted all of it.")
    return key


def _clean_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email:
        raise Refused("Give an email address: it's how you sign in.")
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise Refused("That doesn't look like an email address.")
    return email


def _clean_password(password: str) -> str:
    password = password or ""
    if len(password) < MIN_PASSWORD:
        raise Refused(f"Use a password of at least {MIN_PASSWORD} characters.")
    if not password.strip():
        raise Refused("A password of only spaces is too easy to guess. Use another.")
    if len(password) > MAX_PASSWORD:
        raise Refused(f"That password is longer than {MAX_PASSWORD} characters. Use a shorter one.")
    return password


# scrypt's cost: 16 MB and a few tens of milliseconds a try, so a stolen table is slow to guess at.
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${h.hex()}"


def check_password(stored: str | None, password: str) -> bool:
    """True if the password matches the stored hash. Takes as long with no hash as with one."""
    try:
        _, n, r, p, salt, want = (stored or "").split("$")
        n, r, p, salt, want = int(n), int(r), int(p), bytes.fromhex(salt), bytes.fromhex(want)
    except ValueError:
        n, r, p, salt, want = _N, _R, _P, b"\0" * 16, b""
    got = hashlib.scrypt((password or "").encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return bool(want) and hmac.compare_digest(got, want)


def _email_taken(conn, email: str, but: int | None = None) -> bool:
    return bool(conn.execute("SELECT 1 FROM person WHERE email=? AND id IS NOT ?", (email, but)).fetchone())


def signup(conn, name: str, email: str, password: str, api_key: str) -> int:
    """A new person with their own key and a way to sign in. Returns their id."""
    from house import desk  # desk imports this module

    try:
        name = desk._credit(name)
    except desk.Refused as e:
        raise Refused(str(e)) from None
    if not name:
        raise Refused("Give a name: it goes on what you translate.")
    email = _clean_email(email)
    password = _clean_password(password)
    key = _clean_key(api_key)
    if not _secret():
        raise Refused("This copy of the site can't hold keys: it has no secret set.")
    if _email_taken(conn, email):
        raise Refused(TAKEN)
    person = conn.execute("INSERT INTO person (name, trust, api_key, key_tail, email, password_hash) "
                          "VALUES (?, 'editor', ?, ?, ?, ?)",
                          (name, encrypt(_secret(), key), key[-4:], email, hash_password(password))).lastrowid
    conn.commit()
    return person


def set_login(conn, person_id: int, email: str, password: str, current: str | None = None) -> None:
    """Give a person (an invited editor) an email address and password to sign in with, or change
    them. A person who already has a password must give it, so a stolen session can't take the account."""
    row = conn.execute("SELECT password_hash FROM person WHERE id=?", (person_id,)).fetchone()
    if row and row["password_hash"] and not check_password(row["password_hash"], current or ""):
        raise Refused(WRONG_CURRENT)
    email = _clean_email(email)
    password = _clean_password(password)
    if _email_taken(conn, email, but=person_id):
        raise Refused(TAKEN)
    conn.execute("UPDATE person SET email=?, password_hash=? WHERE id=?", (email, hash_password(password), person_id))
    conn.execute("UPDATE reset SET used_at=datetime('now') WHERE person_id=? AND used_at IS NULL", (person_id,))
    conn.commit()


def set_key(conn, person_id: int, api_key: str) -> None:
    """A new key for a person whose key was forgotten."""
    key = _clean_key(api_key)
    if not _secret():
        raise Refused("This copy of the site can't hold keys: it has no secret set.")
    conn.execute("UPDATE person SET api_key=?, key_tail=? WHERE id=?", (encrypt(_secret(), key), key[-4:], person_id))
    conn.commit()


def authenticate(conn, email: str, password: str) -> int | None:
    """The id of the person this email and password belong to, or None. Every miss costs the same scrypt."""
    row = conn.execute("SELECT id, password_hash FROM person WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    ok = check_password(row["password_hash"] if row else None, password)
    return row["id"] if row and ok else None


# --- sessions and resets ------------------------------------------------------------------------

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(conn, person_id: int) -> str:
    """A signed-in session for this person. Returns the id for the cookie: only its hash is stored."""
    sid = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM session WHERE expires_at < datetime('now')")
    conn.execute("INSERT INTO session (id_hash, person_id, expires_at) VALUES (?, ?, datetime('now', ?))",
                 (_hash(sid), person_id, f"+{SESSION_DAYS} days"))
    conn.commit()
    return sid


def session_person(conn, sid: str | None):
    """The person a session cookie names, or None for an unknown or expired one."""
    if not sid or len(sid) > 100:
        return None
    return conn.execute("SELECT p.* FROM session s JOIN person p ON p.id = s.person_id "
                        "WHERE s.id_hash=? AND s.expires_at > datetime('now')", (_hash(sid),)).fetchone()


def end_session(conn, sid: str | None) -> None:
    if sid:
        conn.execute("DELETE FROM session WHERE id_hash=?", (_hash(sid),))
        conn.commit()


def end_sessions(conn, person_id: int, keep: str | None = None) -> None:
    """End every session of this person, except the one whose id is `keep` (the one in use)."""
    conn.execute("DELETE FROM session WHERE person_id=? AND id_hash IS NOT ?",
                 (person_id, _hash(keep) if keep else None))
    conn.commit()


def new_reset(conn, email: str) -> str | None:
    """A reset token for the account with this email, or None if there's none. Only its hash is stored."""
    row = conn.execute("SELECT id FROM person WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    if not row:
        return None
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO reset (token_hash, person_id, expires_at) VALUES (?, ?, datetime('now', ?))",
                 (_hash(token), row["id"], f"+{RESET_HOURS} hours"))
    conn.commit()
    return token


def reset_person(conn, token: str) -> int | None:
    """The person a reset token is for, if it's unused and less than an hour old."""
    if not token or len(token) > 100:
        return None
    row = conn.execute("SELECT person_id FROM reset WHERE token_hash=? AND used_at IS NULL "
                       "AND expires_at > datetime('now')", (_hash(token),)).fetchone()
    return row["person_id"] if row else None


def use_reset(conn, token: str, password: str) -> int:
    """Set a new password from a reset link. Ends every session the person had. Returns their id."""
    person = reset_person(conn, token)
    if person is None:
        raise Refused(RESET_GONE)
    password = _clean_password(password)
    conn.execute("UPDATE person SET password_hash=? WHERE id=?", (hash_password(password), person))
    conn.execute("UPDATE reset SET used_at=datetime('now') WHERE person_id=? AND used_at IS NULL", (person,))
    conn.commit()
    end_sessions(conn, person)
    return person


def key_for(conn, person_id: int | None) -> str | None:
    """The person's key, decrypted, for the client of a run of theirs; None if they have none."""
    if person_id is None:
        return None
    row = conn.execute("SELECT api_key FROM person WHERE id=?", (person_id,)).fetchone()
    if not row or not row["api_key"]:
        return None
    try:
        return decrypt(_secret(), row["api_key"])
    except (InvalidToken, RuntimeError):  # the secret changed: the key is unreadable, so it's gone
        return None


def forget_key(conn, person_id: int) -> None:
    conn.execute("UPDATE person SET api_key=NULL, key_tail=NULL WHERE id=?", (person_id,))
    conn.commit()


def has_key(person) -> bool:
    return bool(person and person["api_key"])


def client_key(conn, run) -> dict:
    """What desk.go passes make_client for a run: the editor's key for a run on their own key, else
    nothing (the site's key). A run on its own key whose key has gone gets the recorded responses
    only, so it spends nobody's money and fails at its first new call."""
    options = json.loads(run["options"] or "{}")
    if not options.get("own_key"):
        return {}
    key = key_for(conn, options.get("editor_id"))
    return {"api_key": key} if key else {"replay": True}


def spent_words(conn, run_id: int) -> str:
    """What a run on someone's own key has spent, in words: tokens, never money."""
    tokens, calls = conn.execute("SELECT COALESCE(SUM(input_tokens + output_tokens), 0), COUNT(*) FROM call "
                                 "WHERE run_id=? AND from_cache=0", (run_id,)).fetchone()
    if not calls:
        return "Nothing spent from your key."
    said = f"{calls:,} model call{'' if calls == 1 else 's'}"
    if tokens < 1000:
        return f"Spent under a thousand tokens of your key, in {said}."
    return f"Spent about {round(tokens / 1000):,} thousand tokens of your key, in {said}."


# Sign-ups, sign-ins and reset mails per address (and per email address): kept in memory, so a
# restart forgets them, which is fine for limits this coarse.
_signups: dict[str, deque] = defaultdict(deque)
_logins: dict[str, deque] = defaultdict(deque)
_resets: dict[str, deque] = defaultdict(deque)


def _allow(seen: dict[str, deque], keys: list[str], limit: int, now: float | None, count: bool = True) -> bool:
    """True, and counted against every key (unless `count` is False), if each key has been seen fewer
    than `limit` times in the last hour."""
    now = time.time() if now is None else now
    queues = [seen[digest(k)] for k in keys if k]
    for q in queues:
        while q and q[0] < now - 3600:
            q.popleft()
    if any(len(q) >= limit for q in queues):
        return False
    for q in queues if count else ():
        q.append(now)
    return True


def allow_signup(address: str, now: float | None = None, count: bool = True) -> bool:
    """True, and counted unless `count` is False, if this address has signed up fewer than SIGNUPS_PER_HOUR
    times in the last hour."""
    return _allow(_signups, [address or "-"], SIGNUPS_PER_HOUR, now, count)


def allow_login(address: str, email: str, now: float | None = None) -> bool:
    """True, and counted, if neither this address nor this email address has tried LOGINS_PER_HOUR times this hour."""
    return _allow(_logins, [f"ip:{address or '-'}", f"email:{(email or '').strip().lower()}"], LOGINS_PER_HOUR, now)


def allow_reset(address: str, email: str, now: float | None = None) -> bool:
    return _allow(_resets, [f"ip:{address or '-'}", f"email:{(email or '').strip().lower()}"], RESETS_PER_HOUR, now)
