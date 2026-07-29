from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, ALLOWED_EMAIL_DOMAIN
from app.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Créer un nouveau compte utilisateur.
    Le compte est créé avec is_active=False et doit être approuvé par un administrateur.
    """
    # Platform is provisioned exclusively for Vermeg staff — reject a
    # non-Vermeg email up front rather than creating an account that
    # would just sit in the pending-approval queue forever.
    if not user_data.email.lower().endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only @{ALLOWED_EMAIL_DOMAIN} email addresses are allowed"
        )

    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )

    # Create new user — inactive until admin approval
    hashed_password = get_password_hash(user_data.password)

    db_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=False,   # ← pending admin approval
        is_admin=False
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    logger.info(f"New user registered (pending approval): {db_user.username}")

    return db_user


@router.post("/login")
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Connexion utilisateur - retourne un JWT token.
    """
    # Find user
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Verify password
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Check if account is pending approval
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PENDING_APPROVAL"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username},
        expires_delta=access_token_expires
    )

    logger.info(f"User logged in: {user.username}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_admin": user.is_admin
        }
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les informations de l'utilisateur connecté.
    """
    return current_user


@router.post("/logout")
def logout():
    """
    Déconnexion utilisateur.
    Avec JWT, la déconnexion se fait côté client en supprimant le token.
    """
    return {"message": "Successfully logged out"}