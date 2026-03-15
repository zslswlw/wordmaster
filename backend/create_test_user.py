#!/usr/bin/env python3
"""
创建测试用户脚本
用法: python create_test_user.py
"""

from app.models import get_db, User
from app.auth import get_password_hash

def create_test_user():
    db = next(get_db())
    
    # 检查是否已存在测试用户
    existing_user = db.query(User).filter(User.username == "admin").first()
    if existing_user:
        print("测试用户 'admin' 已存在")
        return
    
    # 创建测试用户
    hashed_password = get_password_hash("123456")
    new_user = User(username="admin", password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print(f"测试用户创建成功!")
    print(f"用户名: admin")
    print(f"密码: 123456")
    print(f"用户ID: {new_user.id}")

if __name__ == "__main__":
    create_test_user()
