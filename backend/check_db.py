import sqlite3

conn = sqlite3.connect('wordmaster.db')
cursor = conn.cursor()

# 查看学习组
cursor.execute('SELECT id, name, bank_id, start_seq, end_seq FROM study_groups')
groups = cursor.fetchall()
print("学习组:")
for g in groups:
    print(f"  ID:{g[0]}, 名称:{g[1]}, 词库ID:{g[2]}, 范围:{g[3]}-{g[4]}")

# 查看词库单词数量
if groups:
    group = groups[0]
    cursor.execute('SELECT COUNT(*) FROM words WHERE bank_id = ? AND seq_num >= ? AND seq_num <= ?', 
                   (group[2], group[3], group[4]))
    word_count = cursor.fetchone()[0]
    print(f"\n该组应有单词数: {word_count}")

# 查看单词
cursor.execute('SELECT id, seq_num, word FROM words WHERE bank_id = (SELECT bank_id FROM study_groups LIMIT 1) AND seq_num >= (SELECT start_seq FROM study_groups LIMIT 1) AND seq_num <= (SELECT end_seq FROM study_groups LIMIT 1)')
words = cursor.fetchall()
print(f"\n单词列表:")
for w in words:
    print(f"  ID:{w[0]}, 序号:{w[1]}, 单词:{w[2]}")

# 查看学习记录
cursor.execute('SELECT * FROM study_records')
records = cursor.fetchall()
print(f"\n学习记录数: {len(records)}")

conn.close()
