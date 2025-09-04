from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import (
    OAuth2PasswordBearer,
    SecurityScopes,
)
from jwt.exceptions import InvalidTokenError
from ldap3 import ALL, Connection, Server
from pydantic import BaseModel, ValidationError

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    scopes: list[str] = []


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/token",
    scopes={"targets:read": "Read targets.", "targets:write": "Write targets."},
)


def authenticate_user(username: str, password: str) -> User | bool:
    user_bind_dn = settings.LDAP_USER_BIND_DN.format(username=username)
    server = Server(settings.LDAP_SERVER_URI, get_info=ALL)
    conn = Connection(server, user=user_bind_dn, password=password)
    if not conn.bind():
        return False

    conn.search(
        search_base=settings.LDAP_USER_SEARCH_BASE,
        search_filter=settings.LDAP_USER_SEARCH_FILTER.format(username=username),
        attributes=[
            settings.LDAP_USERNAME_ATTR,
            settings.LDAP_EMAIL_ATTR,
            settings.LDAP_NAME_ATTR,
        ]
    )
    
    if conn.entries:
        entry = conn.entries[0]
        email = entry[settings.LDAP_EMAIL_ATTR].value if settings.LDAP_EMAIL_ATTR in entry else None
        full_name = entry[settings.LDAP_NAME_ATTR].value if settings.LDAP_NAME_ATTR in entry else entry[settings.LDAP_USERNAME_ATTR].value

        return User(username=username, email=email, full_name=full_name)
    return User(username=username)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=8)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


async def get_current_user(security_scopes: SecurityScopes, token: Annotated[str, Depends(oauth2_scheme)]):
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")
        full_name = payload.get("full_name")
        email = payload.get("email")
        if username is None:
            raise credentials_exception
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, username=username)
    except (InvalidTokenError, ValidationError) as e:
        raise credentials_exception
    user = User(username=username, full_name=full_name, email=email)
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user
