from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.security import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_user,
)

router = APIRouter(tags=["token"])


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user: bool | User = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "scopes": [
                "deployers:read",
                "deployers:write",
                "deployments:read",
                "deployments:write",
                "dynamic_policies:read",
                "dynamic_policies:write",
                "networks:read",
                "networks:write",
                "policies:read",
                "policies:write",
                "revisions:read",
                "revisions:write",
                "services:read",
                "services:write",
                "targets:read",
                "targets:write",
                "tests:read",
                "tests:write",
            ],
        },
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=User)
async def read_me(
    current_user: Annotated[User, Security(get_current_user)],
):
    return current_user
