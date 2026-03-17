from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from ..models import get_db, User
from ..schemas import UserCreate, UserResponse, Token
from ..auth import verify_password, get_password_hash, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"注册请求: username={user.username}")
    try:
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            logger.warning(f"用户名已存在: {user.username}")
            raise HTTPException(status_code=400, detail="用户名已被注册")
        hashed_password = get_password_hash(user.password)
        new_user = User(username=user.username, password_hash=hashed_password)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"注册成功: {user.username}")
        return new_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")

@router.post("/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"登录请求: username={user.username}")
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user:
        logger.warning(f"用户不存在: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not verify_password(user.password, db_user.password_hash):
        logger.warning(f"密码验证失败: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )
    logger.info(f"登录成功: {user.username}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
