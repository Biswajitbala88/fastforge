from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(password, hashed_password)


def check_password_rehash(hashed_password: str) -> bool:
    return password_hash.current_hasher.check_needs_rehash(hashed_password)


def verify_and_update_password(
    password: str,
    hashed_password: str,
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(password, hashed_password)