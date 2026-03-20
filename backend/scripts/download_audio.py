#!/usr/bin/env python3
"""
音频下载脚本
用于批量下载单词音频文件

使用方法:
    python scripts/download_audio.py              # 下载所有缺失的音频
    python scripts/download_audio.py --word apple # 下载指定单词
    python scripts/download_audio.py --sync       # 同步模式（检查并下载所有）
"""

import os
import sys
import requests
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import SessionLocal, Word

# 音频源（按优先级排序）
AUDIO_SOURCES = [
    "https://ssl.gstatic.com/dictionary/static/sounds/oxford/{word}--_us_1.mp3",
    "https://dict.youdao.com/dictvoice?type=2&audio={word}",
]

# 音频存储路径
BASE_DIR = Path(__file__).parent.parent.parent
AUDIO_DIR = BASE_DIR / "frontend" / "public" / "audio"


def get_audio_path(word: str) -> Path:
    """获取单词音频文件的存储路径"""
    word = word.lower().strip()
    if not word:
        return None
    first_letter = word[0]
    target_dir = AUDIO_DIR / first_letter
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{word}.mp3"


def audio_exists(word: str) -> bool:
    """检查单词音频是否存在"""
    path = get_audio_path(word)
    return path.exists() if path else False


def download_audio(word: str, verbose: bool = False) -> bool:
    """
    下载单个单词的音频
    
    Args:
        word: 单词
        verbose: 是否打印详细信息
    
    Returns:
        是否成功
    """
    word = word.lower().strip()
    if not word:
        return False
    
    target_file = get_audio_path(word)
    
    # 已存在则跳过
    if target_file.exists():
        if verbose:
            print(f"  [SKIP] {word} (已存在)")
        return True
    
    # 尝试多个源下载
    for source in AUDIO_SOURCES:
        try:
            url = source.format(word=word)
            response = requests.get(url, timeout=10)
            # 检查响应是否有效（文件大小大于1KB）
            if response.status_code == 200 and len(response.content) > 1000:
                with open(target_file, 'wb') as f:
                    f.write(response.content)
                if verbose:
                    print(f"  [OK] {word}")
                return True
        except Exception as e:
            continue
    
    if verbose:
        print(f"  [FAIL] {word}")
    return False


def get_all_words() -> list:
    """从数据库获取所有唯一单词"""
    db = SessionLocal()
    try:
        words = db.query(Word.word).distinct().all()
        return [w[0] for w in words if w[0]]
    finally:
        db.close()


def download_all(max_workers: int = 5, verbose: bool = True):
    """
    下载所有缺失的音频
    
    Args:
        max_workers: 并发下载数
        verbose: 是否打印进度
    """
    words = get_all_words()
    total = len(words)
    
    if verbose:
        print(f"总共 {total} 个单词")
        print(f"开始下载（并发数: {max_workers}）...")
    
    success = 0
    failed = 0
    skipped = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_word = {
            executor.submit(download_audio, word, False): word 
            for word in words
        }
        
        for i, future in enumerate(as_completed(future_to_word)):
            word = future_to_word[future]
            try:
                result = future.result()
                if result:
                    if audio_exists(word):
                        skipped += 1
                    else:
                        success += 1
                        if verbose:
                            print(f"  [OK] {word}")
                else:
                    failed += 1
                    if verbose:
                        print(f"  [FAIL] {word}")
            except Exception as e:
                failed += 1
                if verbose:
                    print(f"  [ERROR] {word}: {e}")
            
            if verbose and (i + 1) % 10 == 0:
                print(f"进度: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%)")
    
    if verbose:
        print(f"\n完成!")
        print(f"  成功: {success}")
        print(f"  跳过（已存在）: {skipped}")
        print(f"  失败: {failed}")
    
    return success, skipped, failed


def main():
    parser = argparse.ArgumentParser(description='下载单词音频')
    parser.add_argument('--word', help='下载指定单词')
    parser.add_argument('--sync', action='store_true', help='同步模式（下载所有缺失的）')
    parser.add_argument('--workers', type=int, default=5, help='并发下载数（默认5）')
    parser.add_argument('--quiet', action='store_true', help='安静模式')
    
    args = parser.parse_args()
    
    # 确保音频目录存在
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.word:
        # 下载单个单词
        print(f"下载单词: {args.word}")
        success = download_audio(args.word, verbose=True)
        sys.exit(0 if success else 1)
    
    elif args.sync:
        # 同步模式
        download_all(max_workers=args.workers, verbose=not args.quiet)
    
    else:
        # 默认显示帮助
        parser.print_help()
        print("\n示例:")
        print("  python scripts/download_audio.py --word apple")
        print("  python scripts/download_audio.py --sync")
        print("  python scripts/download_audio.py --sync --workers 10")


if __name__ == "__main__":
    main()
