"""
模型预下载脚本 - 提前下载嵌入模型，避免运行时下载失败
支持多种下载方式
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = Path(__file__).parent.parent / "models"
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

HF_MIRROR = "https://hf-mirror.com"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
LOCAL_MODEL_NAME = "all-MiniLM-L6-v2"


def set_hf_mirror():
    """设置 HuggingFace 镜像"""
    os.environ['HF_ENDPOINT'] = HF_MIRROR
    logger.info(f"[INFO] 设置镜像: {HF_MIRROR}")


def download_with_huggingface_hub():
    """使用 huggingface_hub 下载"""
    try:
        from huggingface_hub import snapshot_download
        
        logger.info("[INFO] 使用 huggingface_hub 下载...")
        set_hf_mirror()
        
        local_path = MODEL_CACHE_DIR / LOCAL_MODEL_NAME
        
        snapshot_download(
            repo_id=MODEL_NAME,
            local_dir=str(local_path),
            local_dir_use_symlinks=False,
            resume_download=True
        )
        
        logger.info(f"[OK] 模型下载完成: {local_path}")
        return True
        
    except Exception as e:
        logger.error(f"[ERR] huggingface_hub 下载失败: {e}")
        return False


def download_with_sentence_transformers():
    """使用 sentence-transformers 下载"""
    try:
        from sentence_transformers import SentenceTransformer
        
        logger.info("[INFO] 使用 sentence-transformers 下载...")
        set_hf_mirror()
        
        model = SentenceTransformer(
            MODEL_NAME,
            cache_folder=str(MODEL_CACHE_DIR)
        )
        
        local_path = MODEL_CACHE_DIR / LOCAL_MODEL_NAME
        model.save(str(local_path))
        
        logger.info(f"[OK] 模型下载并保存完成: {local_path}")
        return True
        
    except Exception as e:
        logger.error(f"[ERR] sentence-transformers 下载失败: {e}")
        return False


def download_with_transformers():
    """使用 transformers 下载"""
    try:
        from transformers import AutoModel, AutoTokenizer
        
        logger.info("[INFO] 使用 transformers 下载...")
        set_hf_mirror()
        
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModel.from_pretrained(MODEL_NAME)
        
        local_path = MODEL_CACHE_DIR / LOCAL_MODEL_NAME
        local_path.mkdir(parents=True, exist_ok=True)
        
        tokenizer.save_pretrained(str(local_path))
        model.save_pretrained(str(local_path))
        
        logger.info(f"[OK] 模型下载并保存完成: {local_path}")
        return True
        
    except Exception as e:
        logger.error(f"[ERR] transformers 下载失败: {e}")
        return False


def verify_model():
    """验证模型是否可用"""
    try:
        local_path = MODEL_CACHE_DIR / LOCAL_MODEL_NAME
        
        if not local_path.exists():
            logger.warning(f"[WARN] 模型目录不存在: {local_path}")
            return False
        
        required_files = ["config.json", "pytorch_model.bin"]
        missing_files = []
        
        for f in required_files:
            if not (local_path / f).exists() and not (local_path / "model.safetensors").exists():
                missing_files.append(f)
        
        if missing_files:
            logger.warning(f"[WARN] 缺少文件: {missing_files}")
            return False
        
        logger.info("[INFO] 尝试加载模型验证...")
        
        from langchain_community.embeddings import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(
            model_name=str(local_path),
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        test_embedding = embeddings.embed_query("测试文本")
        
        if len(test_embedding) == 384:
            logger.info(f"[OK] 模型验证成功! 嵌入维度: {len(test_embedding)}")
            return True
        else:
            logger.warning(f"[WARN] 嵌入维度异常: {len(test_embedding)}")
            return False
            
    except Exception as e:
        logger.error(f"[ERR] 模型验证失败: {e}")
        return False


def download_model(method: str = "auto"):
    """
    下载模型
    
    Args:
        method: 下载方法 (auto/hub/st/transformers)
    """
    logger.info("=" * 60)
    logger.info("开始下载嵌入模型")
    logger.info(f"模型: {MODEL_NAME}")
    logger.info(f"目标目录: {MODEL_CACHE_DIR / LOCAL_MODEL_NAME}")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    if method == "auto":
        methods = [
            ("huggingface_hub", download_with_huggingface_hub),
            ("sentence_transformers", download_with_sentence_transformers),
            ("transformers", download_with_transformers),
        ]
        
        for name, func in methods:
            logger.info(f"\n[INFO] 尝试使用 {name}...")
            if func():
                break
        else:
            logger.error("[ERR] 所有下载方式都失败了")
            return False
            
    elif method == "hub":
        if not download_with_huggingface_hub():
            return False
            
    elif method == "st":
        if not download_with_sentence_transformers():
            return False
            
    elif method == "transformers":
        if not download_with_transformers():
            return False
    
    elapsed = time.time() - start_time
    
    logger.info("\n" + "=" * 60)
    logger.info("验证模型...")
    
    if verify_model():
        logger.info("=" * 60)
        logger.info(f"[SUCCESS] 模型下载完成! 耗时: {elapsed:.1f}秒")
        logger.info("=" * 60)
        return True
    else:
        logger.error("[ERR] 模型验证失败，请检查下载是否完整")
        return False


def check_status():
    """检查模型状态"""
    logger.info("=" * 60)
    logger.info("检查模型状态")
    logger.info("=" * 60)
    
    local_path = MODEL_CACHE_DIR / LOCAL_MODEL_NAME
    
    if not local_path.exists():
        logger.warning(f"[WARN] 模型未下载: {local_path}")
        logger.info("\n请运行以下命令下载模型:")
        logger.info("  python scripts/download_model.py --download")
        return
    
    logger.info(f"[OK] 模型目录存在: {local_path}")
    
    files = list(local_path.glob("*"))
    logger.info(f"\n模型文件 ({len(files)} 个):")
    for f in files:
        size_mb = f.stat().st_size / (1024 * 1024) if f.is_file() else 0
        logger.info(f"  - {f.name} ({size_mb:.2f} MB)")
    
    logger.info("\n验证模型...")
    if verify_model():
        logger.info("\n[OK] 模型状态: 正常可用")
    else:
        logger.warning("\n[WARN] 模型状态: 可能有问题")


def main():
    parser = argparse.ArgumentParser(description="嵌入模型预下载工具")
    parser.add_argument("--download", action="store_true", help="下载模型")
    parser.add_argument("--verify", action="store_true", help="验证模型")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--method", type=str, default="auto", 
                       choices=["auto", "hub", "st", "transformers"],
                       help="下载方法: auto(自动), hub(huggingface_hub), st(sentence-transformers), transformers")
    
    args = parser.parse_args()
    
    if args.download:
        success = download_model(args.method)
        sys.exit(0 if success else 1)
    elif args.verify:
        success = verify_model()
        sys.exit(0 if success else 1)
    elif args.status:
        check_status()
    else:
        check_status()
        logger.info("\n使用 --download 下载模型")
        logger.info("使用 --verify 验证模型")
        logger.info("使用 --status 查看状态")


if __name__ == "__main__":
    main()
