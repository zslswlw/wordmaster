import sqlite3

conn = sqlite3.connect('wordmaster.db')
cursor = conn.cursor()

# 清空学习记录
cursor.execute('DELETE FROM study_records')
conn.commit()
print(f'已删除 {cursor.rowcount} 条学习记录')

conn.close()
