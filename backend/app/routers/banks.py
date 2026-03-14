from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import csv
import io
from datetime import datetime

from ..models import get_db, User, WordBank, Word
from ..schemas import WordBankCreate, WordBankResponse, WordResponse
from ..auth import get_current_user

router = APIRouter(prefix="/api/banks", tags=["word_banks"])


@router.get("", response_model=list[WordBankResponse])
def get_banks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(WordBank).filter(WordBank.user_id == current_user.id).all()


@router.post("", response_model=WordBankResponse)
async def import_bank(
    file: UploadFile = File(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bank = WordBank(name=name, user_id=current_user.id, word_count=0)
    db.add(bank)
    db.commit()
    db.refresh(bank)

    content = await file.read()
    decoded = content.decode('utf-8-sig')
    reader = csv.reader(io.StringIO(decoded))
    next(reader, None)

    words_to_add = []
    for row in reader:
        if len(row) >= 4:
            word = Word(
                bank_id=bank.id,
                seq_num=int(row[0]),
                word=row[1],
                phonetic=row[2],
                meaning=row[3]
            )
            words_to_add.append(word)
    
    db.bulk_save_objects(words_to_add)
    bank.word_count = len(words_to_add)
    db.commit()
    db.refresh(bank)
    
    return bank


@router.delete("/{bank_id}")
def delete_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bank = db.query(WordBank).filter(
        WordBank.id == bank_id,
        WordBank.user_id == current_user.id
    ).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    db.query(Word).filter(Word.bank_id == bank_id).delete()
    db.delete(bank)
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
    bank = db.query(WordBank).filter(
        WordBank.id == bank_id,
        WordBank.user_id == current_user.id
    ).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    query = db.query(Word).filter(Word.bank_id == bank_id)
    if start is not None and end is not None:
        query = query.filter(Word.seq_num >= start, Word.seq_num <= end)
    return query.order_by(Word.seq_num).all()
