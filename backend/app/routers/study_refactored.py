"""
统一的学习逻辑模块
支持：普通学习、强化学习、复习 三种模式
核心逻辑：
1. 第1轮：学习全部单词
2. 第2轮及以后：只学习上一轮的错误单词
3. 如果某轮全部正确，完成学习
4. 如果中途退出，下次继续当前轮次
"""

from typing import List, Set, Tuple, Optional
from sqlalchemy.orm import Session


def get_study_words(
    all_word_ids: List[int],
    existing_records: list,
    study_type: str
) -> Tuple[List[int], int, bool]:
    """
    统一的学习逻辑函数
    
    Args:
        all_word_ids: 学习组的所有单词ID
        existing_records: 已有的学习记录
        study_type: 学习类型 ('new', 'enhance', 'review')
    
    Returns:
        study_word_ids: 本次需要学习的单词ID列表
        current_round: 当前轮次
        is_completed: 是否已完成学习
    """
    
    # 获取最大轮次
    max_round = 0
    if existing_records:
        max_round = max(r.round for r in existing_records)
    
    # 获取当前轮次的记录
    current_round_records = [r for r in existing_records if r.round == max_round]
    
    # 获取当前轮次错误的单词ID
    current_wrong_ids = set()
    for record in current_round_records:
        if not record.correct:
            current_wrong_ids.add(record.word_id)
    
    # 确定当前轮次应该学习的单词列表
    if max_round <= 1:
        # 第1轮：学习全部单词
        target_word_ids = all_word_ids
    else:
        # 第2轮及以后：只学习上一轮的错误单词
        prev_round = max_round - 1
        prev_round_records = [r for r in existing_records if r.round == prev_round]
        prev_wrong_ids = set()
        for record in prev_round_records:
            if not record.correct:
                prev_wrong_ids.add(record.word_id)
        target_word_ids = list(prev_wrong_ids) if prev_wrong_ids else []
    
    # 判断当前轮次是否已完成
    is_current_round_complete = (
        len(current_round_records) >= len(target_word_ids) and max_round > 0
    )
    
    # 决策逻辑
    if not is_current_round_complete and existing_records:
        # 当前轮次未完成，继续当前轮次
        studied_ids = set(r.word_id for r in current_round_records)
        remaining_ids = [wid for wid in target_word_ids if wid not in studied_ids]
        study_word_ids = remaining_ids if remaining_ids else target_word_ids
        current_round = max_round
        is_completed = False
        
    elif is_current_round_complete and current_wrong_ids:
        # 当前轮次已完成但有错误，进入下一轮
        study_word_ids = list(current_wrong_ids)
        current_round = max_round + 1
        is_completed = False
        
    elif is_current_round_complete and not current_wrong_ids:
        # 当前轮次已完成且全部正确，完成学习
        study_word_ids = []
        current_round = max_round
        is_completed = True
        
    else:
        # 新开始
        study_word_ids = all_word_ids
        current_round = 1
        is_completed = False
    
    return study_word_ids, current_round, is_completed


def calculate_study_result(existing_records: list, all_word_ids: List[int]) -> dict:
    """
    计算学习结果统计
    
    Returns:
        {
            'total_words': 总单词数,
            'studied_words': 已学习单词数,
            'correct_count': 正确数,
            'wrong_count': 错误数,
            'current_round': 当前轮次,
            'is_completed': 是否完成
        }
    """
    if not existing_records:
        return {
            'total_words': len(all_word_ids),
            'studied_words': 0,
            'correct_count': 0,
            'wrong_count': 0,
            'current_round': 0,
            'is_completed': False
        }
    
    max_round = max(r.round for r in existing_records)
    current_round_records = [r for r in existing_records if r.round == max_round]
    
    correct_count = sum(1 for r in current_round_records if r.correct)
    wrong_count = sum(1 for r in current_round_records if not r.correct)
    
    return {
        'total_words': len(all_word_ids),
        'studied_words': len(current_round_records),
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'current_round': max_round,
        'is_completed': False  # 需要结合 get_study_words 的结果判断
    }
