import sqlite3
from datetime import datetime

conn = sqlite3.connect('wordmaster.db')
cursor = conn.cursor()

# 查看用户表
cursor.execute('SELECT id, username, created_at FROM users')
users = cursor.fetchall()
print("用户表:")
for u in users:
    print(f"  ID:{u[0]}, 用户名:{u[1]}, 创建时间:{u[2]}")

conn.close()
