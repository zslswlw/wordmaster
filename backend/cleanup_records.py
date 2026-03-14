import sqlite3

conn = sqlite3.connect('wordmaster.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM study_records')
conn.commit()
print('已删除所有学习记录')
conn.close()
