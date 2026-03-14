"""
修复复习计划数据脚本
清理错误的复习计划数据，重新创建正确的艾宾浩斯复习计划
"""

import sys
sys.path.append('.')

from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import ReviewPlan, StudyGroup

# 艾宾浩斯遗忘曲线间隔（天）
EBINGHAUS_INTERVALS = [1, 3, 7, 15, 30]

def fix_review_plans():
    # 创建数据库连接
    engine = create_engine("sqlite:///./wordmaster.db")
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 获取所有已完成的学习组
        groups = db.query(StudyGroup).filter(StudyGroup.status == "completed").all()
        
        print(f"找到 {len(groups)} 个已完成的学习组")
        
        for group in groups:
            # 删除该学习组的所有现有复习计划
            existing_plans = db.query(ReviewPlan).filter(
                ReviewPlan.group_id == group.id
            ).all()
            
            if existing_plans:
                print(f"\n学习组 '{group.name}' (ID: {group.id}):")
                print(f"  删除 {len(existing_plans)} 个旧复习计划")
                for plan in existing_plans:
                    db.delete(plan)
            
            # 创建新的正确复习计划
            # 使用学习组的完成日期作为基准
            base_date = group.completed_at.date() if group.completed_at else date.today()
            
            print(f"  创建新的复习计划 (基准日期: {base_date}):")
            for round_num, interval in enumerate(EBINGHAUS_INTERVALS, 1):
                review_date = base_date + timedelta(days=interval)
                plan = ReviewPlan(
                    group_id=group.id,
                    review_date=review_date,
                    review_round=round_num,
                    status="pending"
                )
                db.add(plan)
                print(f"    第{round_num}轮: {review_date}")
        
        db.commit()
        print("\n修复完成！")
        
        # 验证修复结果
        print("\n验证结果:")
        plans = db.query(ReviewPlan).all()
        print(f"总复习计划数: {len(plans)}")
        
        for group in groups[:3]:  # 只显示前3个组
            plans = db.query(ReviewPlan).filter(
                ReviewPlan.group_id == group.id
            ).order_by(ReviewPlan.review_round).all()
            if plans:
                print(f"\n  {group.name}:")
                for p in plans:
                    print(f"    第{p.review_round}轮: {p.review_date}")
        
    except Exception as e:
        db.rollback()
        print(f"修复失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    fix_review_plans()
