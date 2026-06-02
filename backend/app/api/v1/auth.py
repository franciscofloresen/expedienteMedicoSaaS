"""API v1 — Auth endpoints (placeholder for Cognito integration)."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    """Cognito authentication — handled client-side with Amplify/SDK."""
    return {"detail": "Use Cognito Hosted UI or Amplify SDK for authentication"}


@router.post("/register")
async def register():
    """Doctor registration — creates Cognito user + tenant."""
    return {"detail": "Registration endpoint — TODO"}
