import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

# choose parameters (example). Tune for your hardware!
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)

DSN = "dbname=yourdb user=youruser password=secret host=db-host sslmode=require"

def create_user(username: str, password: str):
    hashed = ph.hash(password)   # includes salt + params in encoded string
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
              "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
              (username, hashed)
            )

def verify_login(username: str, password: str) -> bool:
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if not row:
                return False   # user not found (don't reveal which)
            user_id, stored_hash = row
    try:
        ph.verify(stored_hash, password)   # raises VerifyMismatchError on bad password
    except (VerifyMismatchError, VerificationError):
        return False
    # password correct; check if we should rehash with new params
    if ph.check_needs_rehash(stored_hash):
        new_hash = ph.hash(password)
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
    return True

password = 'development'
import time
print('start hash')
start = time.time()
hashed_password = ph.hash(password)
print(time.time() - start)
print(hashed_password)

print('start verify')
start = time.time()
result = ph.verify(hashed_password, password)
print(time.time() - start)
print(result)