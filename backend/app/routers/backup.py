from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, date
import json
from typing import Optional
from pydantic import BaseModel

from ..models import get_db, User, WordBank, Word, StudyGroup, StudyRecord, ReviewPlan
from ..auth import get_current_user

router = APIRouter(prefix="/api/backup", tags=["backup"])


class ImportData(BaseModel):
    username: Optional[str] = None
    exported_at: Optional[str] = None
    banks: list = []
    groups: list = []


@router.post("/export")
def export_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_id = current_user.id
    
    banks = db.query(WordBank).filter(WordBank.user_id == user_id).all()
    bank_data = []
    for bank in banks:
        words = db.query(Word).filter(Word.bank_id == bank.id).all()
        bank_data.append({
            "name": bank.name,
            "words": [
                {
                    "seq_num": w.seq_num,
                    "word": w.word,
                    "phonetic": w.phonetic,
                    "meaning": w.meaning
                }
                for w in words
            ]
        })
    
    groups = db.query(StudyGroup).filter(StudyGroup.user_id == user_id).all()
    group_data = []
    for group in groups:
        records = db.query(StudyRecord).filter(StudyRecord.group_id == group.id).all()
        plans = db.query(ReviewPlan).filter(ReviewPlan.group_id == group.id).all()
        group_data.append({
            "bank_id": group.bank_id,
            "name": group.name,
            "start_seq": group.start_seq,
            "end_seq": group.end_seq,
            "status": group.status,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "completed_at": group.completed_at.isoformat() if group.completed_at else None,
            "records": [
                {
                    "word_id": r.word_id,
                    "round": r.round,
                    "correct": r.correct,
                    "studied_at": r.studied_at.isoformat() if r.studied_at else None
                }
                for r in records
            ],
            "plans": [
                {
                    "review_date": p.review_date.isoformat() if p.review_date else None,
                    "original_date": p.original_date.isoformat() if p.original_date else None,
                    "review_round": p.review_round,
                    "status": p.status,
                    "postponed_days": p.postponed_days,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None
                }
                for p in plans
            ]
        })
    
    export_data = {
        "username": current_user.username,
        "exported_at": datetime.utcnow().isoformat(),
        "banks": bank_data,
        "groups": group_data
    }
    
    return export_data


@router.post("/import")
async def import_data(
    data: ImportData,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bank_id_map = {}
    for bank_info in data.banks:
        bank = WordBank(
            name=bank_info["name"],
            user_id=current_user.id,
            word_count=len(bank_info.get("words", []))
        )
        db.add(bank)
        db.commit()
        db.refresh(bank)
        
        word_id_map = {}
        for w in bank_info.get("words", []):
            word = Word(
                bank_id=bank.id,
                seq_num=w["seq_num"],
                word=w["word"],
                phonetic=w["phonetic"],
                meaning=w["meaning"]
            )
            db.add(word)
            db.commit()
            db.refresh(word)
            word_id_map[w.get("old_id", w["seq_num"])] = word.id
        
        bank_id_map[bank_info["name"]] = bank.id
    
    for group_info in data.groups:
        bank_name = group_info.get("bank_name", "")
        bank_id = bank_id_map.get(bank_name)
        if not bank_id:
            continue
        
        group = StudyGroup(
            user_id=current_user.id,
            bank_id=bank_id,
            name=group_info["name"],
            start_seq=group_info["start_seq"],
            end_seq=group_info["end_seq"],
            status=group_info.get("status", "new"),
            created_at=datetime.fromisoformat(group_info["created_at"]) if group_info.get("created_at") else datetime.utcnow(),
            completed_at=datetime.fromisoformat(group_info["completed_at"]) if group_info.get("completed_at") else None
        )
        db.add(group)
        db.commit()
        db.refresh(group)
        
        for r in group_info.get("records", []):
            record = StudyRecord(
                group_id=group.id,
                word_id=r["word_id"],
                round=r["round"],
                correct=r["correct"],
                studied_at=datetime.fromisoformat(r["studied_at"]) if r.get("studied_at") else datetime.utcnow()
            )
            db.add(record)
        
        for p in group_info.get("plans", []):
            # 兼容旧数据：如果没有original_date，使用review_date
            review_date = date.fromisoformat(p["review_date"]) if p.get("review_date") else date.today()
            original_date = date.fromisoformat(p["original_date"]) if p.get("original_date") else review_date
            
            plan = ReviewPlan(
                group_id=group.id,
                review_date=review_date,
                original_date=original_date,
                review_round=p["review_round"],
                status=p.get("status", "pending"),
                postponed_days=p.get("postponed_days", 0),
                completed_at=datetime.fromisoformat(p["completed_at"]) if p.get("completed_at") else None
            )
            db.add(plan)
        
        db.commit()
    
    return {"message": "Data imported successfully"}
