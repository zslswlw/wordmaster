import sqlite3

conn = sqlite3.connect('wordmaster.db')
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("所有表:")
for t in tables:
    print(f"  {t[0]}")

# 查看用户表结构
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print("\nusers 表结构:")
for c in columns:
    print(f"  {c[1]} ({c[2]})")

conn.close()
