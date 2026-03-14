import sqlite3

conn = sqlite3.connect('wordmaster.db')
cursor = conn.cursor()

# 查看学习记录
cursor.execute('SELECT COUNT(*) FROM study_records')
count = cursor.fetchone()[0]
print(f"学习记录总数: {count}")

cursor.execute('SELECT * FROM study_records LIMIT 5')
records = cursor.fetchall()
print("\n学习记录示例:")
for r in records:
    print(f"  {r}")

conn.close()
