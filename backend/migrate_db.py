"""
数据库迁移脚本：为 ReviewPlan 表添加新字段
"""
import sqlite3
from datetime import date

def migrate_database():
    db_path = "./wordmaster.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查 review_plans 表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='review_plans'")
    if not cursor.fetchone():
        print("review_plans 表不存在，无需迁移")
        conn.close()
        return
    
    # 获取现有列
    cursor.execute("PRAGMA table_info(review_plans)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"现有列: {columns}")
    
    # 添加 original_date 列（如果不存在）
    if "original_date" not in columns:
        print("添加 original_date 列...")
        cursor.execute("ALTER TABLE review_plans ADD COLUMN original_date DATE")
        # 将现有数据的 original_date 设置为 review_date
        cursor.execute("UPDATE review_plans SET original_date = review_date WHERE original_date IS NULL")
        print("original_date 列添加完成")
    
    # 添加 postponed_days 列（如果不存在）
    if "postponed_days" not in columns:
        print("添加 postponed_days 列...")
        cursor.execute("ALTER TABLE review_plans ADD COLUMN postponed_days INTEGER DEFAULT 0")
        cursor.execute("UPDATE review_plans SET postponed_days = 0 WHERE postponed_days IS NULL")
        print("postponed_days 列添加完成")
    
    conn.commit()
    conn.close()
    print("数据库迁移完成！")

if __name__ == "__main__":
    migrate_database()
