from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List
import random
import json

from ..models import get_db, User, WordBank, Word, StudyGroup, StudyRecord, ReviewPlan
from ..schemas import StudyCheckRequest, StudyCheckResponse, ReviewPlanResponse
from ..auth import get_current_user

router = APIRouter(prefix="/api/study", tags=["study"])

EBINGHAUS_INTERVALS = [1, 3, 7, 15, 30]


@router.post("/start/{group_id}")
def start_study(
    group_id: int,
    is_review: bool = False,
    is_enhance: bool = False,
    plan_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if not is_review and not is_enhance:
        if group.status == "completed":
            raise HTTPException(status_code=400, detail="Group already completed")
        group.status = "learning"
        db.commit()
    
    words = db.query(Word).filter(
        Word.bank_id == group.bank_id,
        Word.seq_num >= group.start_seq,
        Word.seq_num <= group.end_seq
    ).all()
    
    word_ids = [w.id for w in words]
    
    # 根据模式选择查询的学习类型
    query_study_type = "review" if is_review else ("enhance" if is_enhance else "new")
    
    # 构建查询 - 复习模式时如果提供了plan_id，则只查询该计划的记录
    records_query = db.query(StudyRecord).filter(
        StudyRecord.group_id == group_id,
        StudyRecord.study_type == query_study_type
    )
    
    # 如果提供了plan_id，只查询该复习计划的记录
    if plan_id:
        records_query = records_query.filter(StudyRecord.plan_id == plan_id)
    
    existing_records = records_query.all()
    
    max_round = 0
    if existing_records:
        max_round = max(r.round for r in existing_records)
    
    # 获取当前轮次的记录
    current_round_records = [r for r in existing_records if r.round == max_round]
    
    # 获取当前轮次错误的单词ID
    wrong_word_ids = set()
    for record in current_round_records:
        if not record.correct:
            wrong_word_ids.add(record.word_id)
    
    if is_review:
        # 复习模式：复习整个学习组的所有单词
        # 复习的进度基于当前plan_id的记录（如果有）
        # 注意：如果没有plan_id，说明是新的开始，复习所有单词
        
        # 判断当前轮次是否已完成（所有单词都有记录）
        is_current_round_complete = len(current_round_records) >= len(word_ids) and max_round > 0
        
        # 如果当前轮次未完成（有单词还没听写），继续当前轮次
        if not is_current_round_complete and existing_records:
            # 获取本轮已听写的单词ID
            studied_word_ids = set(r.word_id for r in current_round_records)
            # 返回剩余未听写的单词
            remaining_word_ids = [wid for wid in word_ids if wid not in studied_word_ids]
            current_round = max_round
            study_word_ids = remaining_word_ids if remaining_word_ids else word_ids
        elif wrong_word_ids and is_current_round_complete:
            # 当前轮次已完成且有错误，进入下一轮只听写错误的
            current_round = max_round + 1
            study_word_ids = list(wrong_word_ids)
        elif existing_records and max_round > 0 and is_current_round_complete:
            # 有记录且上轮全部正确，检查是否已完成所有单词的复习
            # 获取已正确复习的单词ID（任意轮次正确即可）
            correct_word_ids = set()
            for record in existing_records:
                if record.correct:
                    correct_word_ids.add(record.word_id)
            
            # 如果所有单词都已正确复习，完成复习
            if len(correct_word_ids) >= len(word_ids):
                current_round = max_round
                study_word_ids = []
            else:
                # 还有单词未正确复习，继续复习所有单词
                current_round = max_round + 1
                study_word_ids = word_ids
        else:
            # 第一轮复习，听写所有单词（整个学习组的单词）
            current_round = 1
            study_word_ids = word_ids
    elif is_enhance:
        # 强化学习模式：听写所有单词（跟新学一样的逻辑，有错误继续下一轮）
        # 查询强化听写模式的记录
        enhance_records = db.query(StudyRecord).filter(
            StudyRecord.group_id == group_id,
            StudyRecord.study_type == "enhance"
        ).all()
        
        enhance_max_round = 0
        if enhance_records:
            enhance_max_round = max(r.round for r in enhance_records)
        
        # 获取当前强化轮次的记录
        current_enhance_records = [r for r in enhance_records if r.round == enhance_max_round]
        
        # 获取当前强化轮次错误的单词ID
        enhance_wrong_word_ids = set()
        for record in current_enhance_records:
            if not record.correct:
                enhance_wrong_word_ids.add(record.word_id)
        
        if enhance_max_round <= 1:
            # 第1轮强化：学习所有单词
            is_enhance_round_complete = len(current_enhance_records) >= len(word_ids) and enhance_max_round > 0
            
            if not is_enhance_round_complete and enhance_records:
                # 当前强化轮次未完成，继续当前轮次
                enhance_studied_ids = set(r.word_id for r in current_enhance_records)
                enhance_remaining = [wid for wid in word_ids if wid not in enhance_studied_ids]
                current_round = enhance_max_round
                study_word_ids = enhance_remaining if enhance_remaining else word_ids
            elif enhance_wrong_word_ids and is_enhance_round_complete:
                # 强化听写有错误，继续下一轮只听写错误的
                current_round = enhance_max_round + 1
                study_word_ids = list(enhance_wrong_word_ids)
            elif is_enhance_round_complete:
                # 强化听写全部正确，完成
                current_round = enhance_max_round
                study_word_ids = []
            else:
                # 第一轮强化听写，听写所有单词
                current_round = 1
                study_word_ids = word_ids
        else:
            # 第2轮及以后：只学习上一轮的错误单词
            enhance_prev_round = enhance_max_round - 1
            enhance_prev_records = [r for r in enhance_records if r.round == enhance_prev_round]
            enhance_prev_wrong_ids = set()
            for record in enhance_prev_records:
                if not record.correct:
                    enhance_prev_wrong_ids.add(record.word_id)
            
            # 当前轮次应该学习的单词 = 上一轮的错误单词
            enhance_target_ids = list(enhance_prev_wrong_ids) if enhance_prev_wrong_ids else []
            
            # 判断当前轮次是否完成（基于应该学习的单词数）
            is_enhance_round_complete = len(current_enhance_records) >= len(enhance_target_ids) and enhance_max_round > 0
            
            if not is_enhance_round_complete and enhance_records:
                # 当前强化轮次未完成，继续当前轮次
                enhance_studied_ids = set(r.word_id for r in current_enhance_records)
                enhance_remaining = [wid for wid in enhance_target_ids if wid not in enhance_studied_ids]
                current_round = enhance_max_round
                study_word_ids = enhance_remaining if enhance_remaining else enhance_target_ids
            elif enhance_wrong_word_ids and is_enhance_round_complete:
                # 强化听写有错误，继续下一轮只听写错误的
                current_round = enhance_max_round + 1
                study_word_ids = list(enhance_wrong_word_ids)
            elif is_enhance_round_complete:
                # 强化听写全部正确，完成
                current_round = enhance_max_round
                study_word_ids = []
            else:
                # 保险起见
                current_round = enhance_max_round
                study_word_ids = enhance_target_ids
    else:
        # 普通学习模式：有错误只学习错误的，没错误学习全部
        # 关键：需要确定当前轮次"应该"学习哪些单词
        
        if max_round <= 1:
            # 第1轮或新开始：学习所有单词
            is_current_round_complete = len(current_round_records) >= len(word_ids) and max_round > 0
            
            # 调试日志
            import logging
            logging.info(f"[DEBUG-R1] max_round={max_round}, word_ids count={len(word_ids)}")
            logging.info(f"[DEBUG-R1] current_round_records count={len(current_round_records)}")
            logging.info(f"[DEBUG-R1] wrong_word_ids count={len(wrong_word_ids)}")
            logging.info(f"[DEBUG-R1] is_current_round_complete={is_current_round_complete}")
            
            if not is_current_round_complete and existing_records:
                # 第1轮未完成，继续
                studied_word_ids = set(r.word_id for r in current_round_records)
                remaining_word_ids = [wid for wid in word_ids if wid not in studied_word_ids]
                current_round = max_round
                study_word_ids = remaining_word_ids if remaining_word_ids else word_ids
                logging.info(f"[DEBUG-R1] Branch: not complete, study_word_ids count={len(study_word_ids)}")
            elif wrong_word_ids and is_current_round_complete:
                # 第1轮完成且有错误，进入第2轮只听写错误的
                current_round = max_round + 1
                study_word_ids = list(wrong_word_ids)
                logging.info(f"[DEBUG-R1] Branch: complete with errors, study_word_ids count={len(study_word_ids)}")
            elif is_current_round_complete:
                # 第1轮完成且全部正确，完成学习
                current_round = max_round
                study_word_ids = []
                logging.info(f"[DEBUG-R1] Branch: complete all correct")
            else:
                # 新开始
                current_round = 1
                study_word_ids = word_ids
                logging.info(f"[DEBUG-R1] Branch: new start, study_word_ids count={len(study_word_ids)}")
        else:
            # 第2轮及以后：只学习上一轮的错误单词
            # 获取上一轮（max_round - 1）的错误单词作为当前轮次的目标
            prev_round = max_round - 1
            prev_round_records = [r for r in existing_records if r.round == prev_round]
            prev_wrong_word_ids = set()
            for record in prev_round_records:
                if not record.correct:
                    prev_wrong_word_ids.add(record.word_id)
            
            # 当前轮次应该学习的单词 = 上一轮的错误单词
            target_word_ids = list(prev_wrong_word_ids) if prev_wrong_word_ids else []
            
            # 判断当前轮次是否完成（基于应该学习的单词数）
            is_current_round_complete = len(current_round_records) >= len(target_word_ids) and max_round > 0
            
            # 调试日志
            import logging
            logging.info(f"[DEBUG] max_round={max_round}, prev_round={prev_round}")
            logging.info(f"[DEBUG] prev_round_records count={len(prev_round_records)}")
            logging.info(f"[DEBUG] prev_wrong_word_ids count={len(prev_wrong_word_ids)}")
            logging.info(f"[DEBUG] current_round_records count={len(current_round_records)}")
            logging.info(f"[DEBUG] wrong_word_ids count={len(wrong_word_ids)}")
            logging.info(f"[DEBUG] target_word_ids count={len(target_word_ids)}")
            logging.info(f"[DEBUG] is_current_round_complete={is_current_round_complete}")
            
            if not is_current_round_complete and existing_records:
                # 当前轮次未完成，继续学习剩余单词
                studied_word_ids = set(r.word_id for r in current_round_records)
                remaining_word_ids = [wid for wid in target_word_ids if wid not in studied_word_ids]
                current_round = max_round
                study_word_ids = remaining_word_ids if remaining_word_ids else target_word_ids
                logging.info(f"[DEBUG] Branch: not complete, study_word_ids count={len(study_word_ids)}")
            elif wrong_word_ids and is_current_round_complete:
                # 当前轮次已完成但还有错误，进入下一轮只听写这些错误
                current_round = max_round + 1
                study_word_ids = list(wrong_word_ids)
                logging.info(f"[DEBUG] Branch: complete with errors, study_word_ids count={len(study_word_ids)}")
            elif is_current_round_complete:
                # 当前轮次已完成且全部正确，完成学习
                current_round = max_round
                study_word_ids = []
                logging.info(f"[DEBUG] Branch: complete all correct")
            else:
                # 不应该到达这里，但保险起见
                current_round = max_round
                study_word_ids = target_word_ids
                logging.info(f"[DEBUG] Branch: else fallback, study_word_ids count={len(study_word_ids)}")
    
    random.shuffle(study_word_ids)
    
    return {
        "group_id": group_id,
        "group_name": group.name,
        "total_words": len(study_word_ids),
        "current_round": current_round,
        "word_ids": study_word_ids
    }


@router.get("/word/{word_id}", response_model=dict)
def get_word(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return {
        "id": word.id,
        "word": word.word,
        "phonetic": word.phonetic,
        "meaning": word.meaning
    }


@router.post("/check", response_model=StudyCheckResponse)
def check_answer(
    request: StudyCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 验证学习组是否存在且属于当前用户
    group = db.query(StudyGroup).filter(
        StudyGroup.id == request.group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    word = db.query(Word).filter(Word.id == request.word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    
    correct = request.user_input.strip().lower() == word.word.strip().lower()
    
    try:
        record = StudyRecord(
            group_id=request.group_id,
            word_id=request.word_id,
            round=request.round,
            correct=correct,
            study_type=request.study_type,
            plan_id=request.plan_id
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save record: {str(e)}")
    
    return StudyCheckResponse(
        correct=correct,
        correct_answer=word.word,
        word=word.word
    )


@router.post("/complete/{group_id}")
def complete_round(
    group_id: int,
    is_enhance: bool = False,
    is_review: bool = False,
    study_type: str = None,
    plan_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 复习模式：像新学一样多轮进行，直到所有单词正确
    if is_review or study_type == "review":
        # 根据参数构建查询
        query = db.query(StudyRecord).filter(StudyRecord.group_id == group_id)
        if study_type:
            query = query.filter(StudyRecord.study_type == study_type)
        if plan_id:
            query = query.filter(StudyRecord.plan_id == plan_id)
        
        records = query.all()
        
        if not records:
            return {"message": "No records", "next_step": "continue"}
        
        current_round = max(r.round for r in records)
        wrong_count = sum(1 for r in records if not r.correct and r.round == current_round)
        
        if wrong_count == 0:
            # 当前轮次全部正确，复习完成
            # 更新复习计划状态为已完成
            if plan_id:
                review_plan = db.query(ReviewPlan).filter(
                    ReviewPlan.id == plan_id,
                    ReviewPlan.group_id == group_id
                ).first()
                if review_plan:
                    review_plan.status = "completed"
                    review_plan.completed_at = datetime.utcnow()
                    db.commit()
            return {"message": "Review completed successfully", "status": "completed", "next_step": "completed"}
        else:
            # 复习还有错误，继续下一轮复习（像新学一样）
            return {"message": f"{wrong_count} words wrong", "next_step": "continue"}
    
    # 强化听写模式
    if is_enhance:
        # 查询强化听写模式的记录
        enhance_records = db.query(StudyRecord).filter(
            StudyRecord.group_id == group_id,
            StudyRecord.study_type == "enhance"
        ).all()
        
        if not enhance_records:
            return {"message": "No records", "next_step": "continue"}
        
        current_round = max(r.round for r in enhance_records)
        wrong_count = sum(1 for r in enhance_records if not r.correct and r.round == current_round)
        
        if wrong_count == 0:
            # 强化学习完成，标记为完成状态
            group.status = "completed"
            group.completed_at = datetime.utcnow()
            
            today = date.today()
            for round_num, interval in enumerate(EBINGHAUS_INTERVALS, 1):
                review_date = today + timedelta(days=interval)
                plan = ReviewPlan(
                    group_id=group_id,
                    review_date=review_date,
                    original_date=review_date,
                    review_round=round_num,
                    postponed_days=0
                )
                db.add(plan)
            
            db.commit()
            return {"message": "Group completed successfully", "status": "completed", "next_step": "completed"}
        else:
            # 强化学习还有错误，需要继续强化
            return {"message": f"{wrong_count} words wrong in enhance round", "next_step": "continue"}
    
    # 新学模式
    # 根据参数构建查询，默认只统计新学模式
    query = db.query(StudyRecord).filter(StudyRecord.group_id == group_id)
    if study_type:
        query = query.filter(StudyRecord.study_type == study_type)
    else:
        query = query.filter(StudyRecord.study_type == "new")
    if plan_id:
        query = query.filter(StudyRecord.plan_id == plan_id)
    
    records = query.all()
    
    if not records:
        return {"message": "No records", "next_step": "continue"}
    
    current_round = max(r.round for r in records)
    wrong_count = sum(1 for r in records if not r.correct and r.round == current_round)
    
    if wrong_count == 0:
        return {"message": "All words correct", "next_step": "enhance"}
    else:
        return {"message": f"{wrong_count} words wrong", "next_step": "continue"}


@router.get("/round/{group_id}")
def get_round_stats(
    group_id: int,
    study_type: str = None,
    plan_id: int = None,
    current_round: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 获取学习组信息
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 获取学习组总单词数
    total_words = db.query(Word).filter(
        Word.bank_id == group.bank_id,
        Word.seq_num >= group.start_seq,
        Word.seq_num <= group.end_seq
    ).count()
    
    query = db.query(StudyRecord).filter(
        StudyRecord.group_id == group_id
    )
    
    # 如果指定了学习类型，进行过滤；否则默认只统计新学模式
    if study_type:
        query = query.filter(StudyRecord.study_type == study_type)
    else:
        query = query.filter(StudyRecord.study_type == "new")
    
    # 如果指定了复习计划ID，进行过滤
    if plan_id:
        query = query.filter(StudyRecord.plan_id == plan_id)
    
    records = query.all()
    
    if not records:
        return {
            "current_round": current_round or 1,
            "total_rounds": 0,
            "total_words": total_words,
            "rounds": {}
        }
    
    # 使用字典去重，每个单词每轮只统计一次（取最新记录）
    round_words = {}  # {round: {word_id: (correct, record_id)}}
    for r in records:
        if r.round not in round_words:
            round_words[r.round] = {}
        # 如果同一个单词有多个记录，保留最新的（ID最大的）
        if r.word_id not in round_words[r.round] or r.id > round_words[r.round][r.word_id][1]:
            round_words[r.round][r.word_id] = (r.correct, r.id)
    
    # 统计每轮数据
    rounds = {}
    for round_num, words_data in round_words.items():
        rounds[round_num] = {"correct": 0, "wrong": 0, "total": len(words_data)}
        for correct, _ in words_data.values():
            if correct:
                rounds[round_num]["correct"] += 1
            else:
                rounds[round_num]["wrong"] += 1
    
    # 确定当前轮次
    actual_current_round = current_round or max(rounds.keys())
    current_round_data = rounds.get(actual_current_round, {"correct": 0, "wrong": 0, "total": 0})
    
    # 计算本轮单词数：使用实际统计的单词数（正确+错误）
    current_round_total = current_round_data.get("correct", 0) + current_round_data.get("wrong", 0)
    
    return {
        "current_round": actual_current_round,
        "total_words": total_words,
        "rounds": rounds,
        "current_round_stats": {
            "correct": current_round_data["correct"],
            "wrong": current_round_data["wrong"],
            "total": current_round_total
        }
    }
