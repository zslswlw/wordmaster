from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
import csv
import io

from .. import models
from ..models import get_db, User, WordBank, Word
from ..schemas import WordBankCreate, WordBankResponse, WordResponse
from ..auth import get_current_user, get_admin_user
from ..services.learning_content import seed_bank_evolution
from ..admin_consistency import RevisionConflict, audit_admin_action, utc_iso

router = APIRouter(prefix="/api/banks", tags=["word_banks"])


@router.get("", response_model=list[WordBankResponse])
def get_banks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """所有认证用户可查看共享词库"""
    return db.query(WordBank).all()


@router.post("", response_model=WordBankResponse)
async def import_bank(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    try:
        content = await file.read()
        decoded = content.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(decoded))
        
        # 尝试读取表头
        try:
            next(reader, None)
        except StopIteration:
            raise HTTPException(status_code=400, detail="CSV文件为空或格式错误")

        words_to_add = []
        for row in reader:
            if len(row) >= 4:
                try:
                    word = Word(
                        bank_id=0,  # 临时值，后面会更新
                        seq_num=int(row[0]),
                        word=row[1],
                        phonetic=row[2],
                        meaning=row[3]
                    )
                    words_to_add.append(word)
                except (ValueError, IndexError) as e:
                    # 跳过格式错误的行
                    continue
        
        if not words_to_add:
            raise HTTPException(status_code=400, detail="CSV文件中没有有效的单词数据")
        
        # 创建词库
        bank = WordBank(name=name, word_count=len(words_to_add), user_id=admin.id)
        db.add(bank)
        db.flush()
        
        # 更新单词的词库ID
        for word in words_to_add:
            word.bank_id = bank.id
        
        db.bulk_save_objects(words_to_add)
        db.flush()

        seed_bank_evolution(db, bank.id, priority=100, commit=False)
        audit_admin_action(
            db,
            request,
            admin,
            action="word_bank.import",
            target_type="word_bank",
            target_id=bank.id,
            after={
                "id": bank.id,
                "name": bank.name,
                "word_count": bank.word_count,
                "revision": bank.revision,
            },
        )
        db.commit()
        db.refresh(bank)

        return bank
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.delete("/{bank_id}")
def delete_bank(
    bank_id: int,
    expected_revision: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    bank = db.query(WordBank).filter(WordBank.id == bank_id).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    current = {
        "id": bank.id,
        "name": bank.name,
        "word_count": bank.word_count,
        "revision": bank.revision,
        "created_at": utc_iso(bank.created_at),
    }
    if bank.revision != expected_revision:
        raise RevisionConflict(current)

    in_use = db.query(models.StudyGroup.id).filter(
        models.StudyGroup.bank_id == bank_id,
    ).first()
    if in_use:
        raise HTTPException(status_code=409, detail="词库仍被学习组使用，请先删除相关学习组")

    word_ids = [row[0] for row in db.query(Word.id).filter(Word.bank_id == bank_id).all()]
    if word_ids:
        db.query(models.MemoryExposure).filter(
            models.MemoryExposure.word_id.in_(word_ids),
        ).delete(synchronize_session=False)
        db.query(models.MemoryFeedback).filter(
            models.MemoryFeedback.word_id.in_(word_ids),
        ).delete(synchronize_session=False)
        db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.word_id.in_(word_ids),
        ).delete(synchronize_session=False)
    job_ids = db.query(models.AiJob.id).filter(models.AiJob.bank_id == bank_id)
    db.query(models.AiJobAttempt).filter(
        models.AiJobAttempt.job_id.in_(job_ids),
    ).delete(synchronize_session=False)
    db.query(models.AiJob).filter(models.AiJob.bank_id == bank_id).delete(
        synchronize_session=False,
    )
    db.query(models.AiLaneState).filter(
        models.AiLaneState.cursor_bank_id == bank_id,
    ).update({"cursor_bank_id": None}, synchronize_session=False)
    flags = db.query(models.FeatureFlags).filter(
        models.FeatureFlags.priority_bank_id == bank_id,
    ).first()
    if flags:
        flags.priority_bank_id = None
        flags.revision = (flags.revision or 1) + 1
    db.query(Word).filter(Word.bank_id == bank_id).delete(synchronize_session=False)
    deleted = db.query(WordBank).filter(
        WordBank.id == bank_id,
        WordBank.revision == expected_revision,
    ).delete(synchronize_session=False)
    if deleted != 1:
        db.rollback()
        latest = db.query(WordBank).filter(WordBank.id == bank_id).first()
        raise RevisionConflict(
            {
                "id": latest.id,
                "name": latest.name,
                "word_count": latest.word_count,
                "revision": latest.revision,
                "created_at": utc_iso(latest.created_at),
            } if latest else {"deleted": True}
        )
    audit_admin_action(
        db,
        request,
        admin,
        action="word_bank.delete",
        target_type="word_bank",
        target_id=bank_id,
        before=current,
    )
    db.commit()
    return {"message": "Bank deleted successfully"}


@router.get("/{bank_id}/words", response_model=list[WordResponse])
def get_words(
    bank_id: int,
    start: int = None,
    end: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bank = db.query(WordBank).filter(WordBank.id == bank_id).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    query = db.query(Word).filter(Word.bank_id == bank_id)
    if start is not None and end is not None:
        query = query.filter(Word.seq_num >= start, Word.seq_num <= end)
    return query.order_by(Word.seq_num).all()
