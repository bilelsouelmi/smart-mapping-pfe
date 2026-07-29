from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

# Checked explicitly in auth.py's register() (not as a Pydantic
# field_validator) so a rejection comes back as the same clean
# {"detail": "..."} string shape as every other auth error (e.g. "Email
# or username already registered") — a Pydantic validator error is a 422
# with `detail` as a LIST of error objects, which the frontend's
# `toast.error(result.error)` can't render sensibly.
ALLOWED_EMAIL_DOMAIN = "vermeg.com"


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_compliance_officer: Optional[bool] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    is_compliance_officer: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True