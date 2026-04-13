"""
健壮的向量化服务 - 多模型备选策略 + 重试机制 + 健康检查
彻底解决向量化失败问题
"""

import os
import logging
import asyncio
import time
import hashlib
import threading
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path
from io import BytesIO

if not os.environ.get('HF_ENDPOINT'):
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)


class EmbeddingBackend(Enum):
    LOCAL_HUGGINGFACE = "local_huggingface"
    ONLINE_HUGGINGFACE = "online_huggingface"
    OPENAI = "openai"
    TFIDF = "tfidf"
    NONE = "none"


@dataclass
class EmbeddingConfig:
    backend: EmbeddingBackend = EmbeddingBackend.NONE
    dimension: int = 384
    model_name: str = ""
    is_ready: bool = False
    error_message: str = ""
    load_time_ms: int = 0


@dataclass
class VectorizationResult:
    success: bool
    chunk_count: int = 0
    item_id: str = ""
    error: str = ""
    processing_time_ms: int = 0
    backend_used: EmbeddingBackend = EmbeddingBackend.NONE


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 30000
    exponential_base: float = 2.0


class RobustEmbeddingService:
    """
    健壮的嵌入服务 - 多模型备选策略
    
    优先级顺序:
    1. 本地 HuggingFace 模型（预下载）
    2. 在线 HuggingFace 模型（通过镜像）
    3. OpenAI Embeddings API（如果配置）
    4. TF-IDF 本地嵌入（最后备选）
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.config = EmbeddingConfig()
        self._embedding_model = None
        self._tfidf_vectorizer = None
        self._vocabulary: Dict[str, int] = {}
        self._idf_weights: Dict[str, float] = {}
        
        self._initialize_embedding()
    
    def _initialize_embedding(self):
        """按优先级尝试初始化嵌入模型"""
        start_time = time.time()
        
        backends_to_try = [
            (self._try_local_huggingface, EmbeddingBackend.LOCAL_HUGGINGFACE),
            (self._try_online_huggingface, EmbeddingBackend.ONLINE_HUGGINGFACE),
            (self._try_openai, EmbeddingBackend.OPENAI),
            (self._try_tfidf, EmbeddingBackend.TFIDF),
        ]
        
        for try_func, backend in backends_to_try:
            try:
                if try_func():
                    self.config.backend = backend
                    self.config.is_ready = True
                    self.config.load_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"[OK] 嵌入模型初始化成功: {backend.value}, 耗时 {self.config.load_time_ms}ms")
                    return
            except Exception as e:
                logger.warning(f"[WARN] {backend.value} 初始化失败: {e}")
                continue
        
        self.config.error_message = "所有嵌入后端初始化失败"
        logger.error(f"[ERR] {self.config.error_message}")
    
    def _try_local_huggingface(self) -> bool:
        """尝试加载本地预下载的模型"""
        local_model_path = os.path.join(MODEL_CACHE_DIR, 'all-MiniLM-L6-v2')
        
        if not os.path.exists(local_model_path):
            logger.info(f"[INFO] 本地模型不存在: {local_model_path}")
            return False
        
        logger.info(f"[INFO] 尝试加载本地模型: {local_model_path}")
        
        from langchain_community.embeddings import HuggingFaceEmbeddings
        self._embedding_model = HuggingFaceEmbeddings(
            model_name=local_model_path,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        test_embedding = self._embedding_model.embed_query("test")
        if len(test_embedding) != 384:
            raise ValueError(f"嵌入维度异常: {len(test_embedding)}")
        
        self.config.model_name = "all-MiniLM-L6-v2 (local)"
        self.config.dimension = 384
        return True
    
    def _try_online_huggingface(self) -> bool:
        """尝试从在线加载模型（通过镜像）"""
        logger.info(f"[INFO] 尝试在线加载模型, 镜像: {os.environ.get('HF_ENDPOINT', 'default')}")
        
        from langchain_community.embeddings import HuggingFaceEmbeddings
        self._embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu', 'cache_folder': MODEL_CACHE_DIR},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        test_embedding = self._embedding_model.embed_query("test")
        if len(test_embedding) != 384:
            raise ValueError(f"嵌入维度异常: {len(test_embedding)}")
        
        self.config.model_name = "all-MiniLM-L6-v2 (online)"
        self.config.dimension = 384
        return True
    
    def _try_openai(self) -> bool:
        """尝试使用 OpenAI Embeddings API"""
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.info("[INFO] 未配置 OPENAI_API_KEY")
            return False
        
        logger.info("[INFO] 尝试使用 OpenAI Embeddings")
        
        from langchain_openai import OpenAIEmbeddings
        self._embedding_model = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=api_key
        )
        
        test_embedding = self._embedding_model.embed_query("test")
        self.config.model_name = "text-embedding-3-small"
        self.config.dimension = len(test_embedding)
        return True
    
    def _try_tfidf(self) -> bool:
        """使用 TF-IDF 作为最后的备选方案"""
        logger.info("[INFO] 使用 TF-IDF 嵌入作为备选方案")
        
        self._init_tfidf_vocabulary()
        self._embedding_model = None
        self.config.model_name = "tfidf-fallback"
        self.config.dimension = 384
        return True
    
    def _init_tfidf_vocabulary(self):
        """初始化 TF-IDF 词汇表"""
        common_words = [
            "的", "是", "在", "了", "和", "与", "或", "有", "为", "以",
            "及", "其", "这", "那", "之", "上", "下", "中", "来", "去",
            "到", "从", "向", "把", "被", "让", "给", "对", "于", "而",
            "能", "会", "可", "要", "应", "将", "已", "也", "都", "就",
            "但", "如", "因", "所", "着", "过", "时", "年", "月", "日",
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "need",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "we", "us", "our", "you", "your", "he", "him", "his", "she",
            "and", "or", "but", "if", "then", "else", "when", "where",
            "what", "which", "who", "whom", "whose", "how", "why", "for",
        ]
        
        for idx, word in enumerate(common_words[:384]):
            self._vocabulary[word] = idx
            self._idf_weights[word] = 1.0
    
    def embed_text(self, text: str) -> Optional[List[float]]:
        """将文本转换为嵌入向量"""
        if not text or not text.strip():
            return None
        
        try:
            if self._embedding_model is not None:
                return self._embedding_model.embed_query(text)
            else:
                return self._embed_tfidf(text)
        except Exception as e:
            logger.error(f"[ERR] 嵌入生成失败: {e}")
            return self._embed_tfidf(text) if self.config.backend == EmbeddingBackend.TFIDF else None
    
    def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量生成嵌入向量"""
        if self._embedding_model is not None:
            try:
                return self._embedding_model.embed_documents(texts)
            except Exception as e:
                logger.error(f"[ERR] 批量嵌入失败: {e}")
                return [self.embed_text(t) for t in texts]
        else:
            return [self._embed_tfidf(t) for t in texts]
    
    def _embed_tfidf(self, text: str) -> List[float]:
        """TF-IDF 嵌入实现"""
        import numpy as np
        
        words = list(text.lower())
        word_freq: Dict[str, int] = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        embedding = np.zeros(384, dtype=np.float32)
        
        text_hash = hashlib.md5(text.encode()).hexdigest()
        np.random.seed(int(text_hash[:8], 16))
        
        for word, freq in word_freq.items():
            if word in self._vocabulary:
                idx = self._vocabulary[word]
                embedding[idx] = freq * self._idf_weights.get(word, 1.0)
            else:
                word_hash = hashlib.md5(word.encode()).hexdigest()
                pseudo_idx = int(word_hash[:3], 16) % 384
                embedding[pseudo_idx] += freq * 0.5
        
        noise = np.random.randn(384).astype(np.float32) * 0.01
        embedding += noise
        
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding.tolist()
    
    def is_ready(self) -> bool:
        return self.config.is_ready
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "backend": self.config.backend.value,
            "model_name": self.config.model_name,
            "dimension": self.config.dimension,
            "is_ready": self.config.is_ready,
            "error_message": self.config.error_message,
            "load_time_ms": self.config.load_time_ms
        }


class RobustVectorizationService:
    """
    健壮的向量化服务 - 包含重试机制和健康检查
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        
        self.embedding_service = RobustEmbeddingService()
        self._text_splitter = None
        self._retry_config = RetryConfig()
        
        self._pending_queue: List[Dict[str, Any]] = []
        self._processing = False
        self._stats = {
            "total_processed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_retries": 0
        }
    
    def _get_text_splitter(self):
        if self._text_splitter is None:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            self._text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=512,
                chunk_overlap=100,
                length_function=len,
                separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
            )
        return self._text_splitter
    
    def chunk_text(self, text: str) -> List[str]:
        """文本分块"""
        if not text or len(text.strip()) == 0:
            return []
        
        splitter = self._get_text_splitter()
        chunks = splitter.split_text(text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]
    
    async def vectorize_with_retry(
        self,
        item_id: str,
        content: str,
        source_resource: str = "unknown",
        page_number: int = 0,
        retry_config: Optional[RetryConfig] = None
    ) -> VectorizationResult:
        """
        带重试机制的向量化
        """
        config = retry_config or self._retry_config
        start_time = time.time()
        last_error = None
        
        for attempt in range(config.max_retries):
            try:
                result = await self._vectorize_single(
                    item_id, content, source_resource, page_number
                )
                
                if result.success:
                    return result
                
                last_error = result.error
                
                if attempt < config.max_retries - 1:
                    delay_ms = min(
                        int(config.base_delay_ms * (config.exponential_base ** attempt)),
                        config.max_delay_ms
                    )
                    logger.warning(
                        f"[RETRY] 向量化失败，{delay_ms}ms 后重试 "
                        f"(尝试 {attempt + 1}/{config.max_retries}): {item_id}"
                    )
                    self._stats["total_retries"] += 1
                    await asyncio.sleep(delay_ms / 1000)
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"[ERR] 向量化异常: {e}")
                
                if attempt < config.max_retries - 1:
                    delay_ms = min(
                        int(config.base_delay_ms * (config.exponential_base ** attempt)),
                        config.max_delay_ms
                    )
                    await asyncio.sleep(delay_ms / 1000)
        
        return VectorizationResult(
            success=False,
            item_id=item_id,
            error=f"重试 {config.max_retries} 次后仍失败: {last_error}",
            processing_time_ms=int((time.time() - start_time) * 1000),
            backend_used=self.embedding_service.config.backend
        )
    
    async def _vectorize_single(
        self,
        item_id: str,
        content: str,
        source_resource: str,
        page_number: int
    ) -> VectorizationResult:
        """单次向量化尝试"""
        start_time = time.time()
        
        try:
            from repository.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            supabase.table("knowledge_items").update({
                "vector_status": "processing"
            }).eq("id", item_id).execute()
            
            chunks = self.chunk_text(content)
            if not chunks:
                raise ValueError("文本分块失败或内容为空")
            
            embeddings = self.embedding_service.embed_texts(chunks)
            
            vectors_to_insert = []
            for chunk_index, (chunk_text_content, embedding) in enumerate(zip(chunks, embeddings)):
                if embedding is None:
                    logger.warning(f"[WARN] 第{chunk_index}块向量化失败，跳过")
                    continue
                
                vectors_to_insert.append({
                    "knowledge_item_id": item_id,
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text_content,
                    "vector_embedding": embedding,
                    "source_resource": source_resource,
                    "page_number": page_number
                })
            
            if not vectors_to_insert:
                raise ValueError("所有文本块向量化失败")
            
            if vectors_to_insert:
                supabase.table("knowledge_vectors").insert(vectors_to_insert).execute()
            
            processing_time = int((time.time() - start_time) * 1000)
            
            supabase.table("knowledge_items").update({
                "vector_status": "completed",
                "chunk_count": len(vectors_to_insert)
            }).eq("id", item_id).execute()
            
            self._log_vectorization(supabase, item_id, "success", len(vectors_to_insert), processing_time)
            
            self._stats["total_processed"] += 1
            self._stats["total_success"] += 1
            
            return VectorizationResult(
                success=True,
                chunk_count=len(vectors_to_insert),
                item_id=item_id,
                processing_time_ms=processing_time,
                backend_used=self.embedding_service.config.backend
            )
            
        except Exception as e:
            logger.error(f"[ERR] 向量化失败: {e}")
            
            try:
                from repository.supabase_client import get_supabase_client
                supabase = get_supabase_client()
                supabase.table("knowledge_items").update({
                    "vector_status": "failed"
                }).eq("id", item_id).execute()
                
                self._log_vectorization(supabase, item_id, "failed", 0, 0, str(e))
            except Exception as log_err:
                logger.warning(f"[WARN] 更新状态失败: {log_err}")
            
            self._stats["total_processed"] += 1
            self._stats["total_failed"] += 1
            
            return VectorizationResult(
                success=False,
                item_id=item_id,
                error=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
                backend_used=self.embedding_service.config.backend
            )
    
    def _log_vectorization(
        self,
        supabase,
        item_id: str,
        status: str,
        chunk_count: int,
        processing_time_ms: int,
        error_message: str = None
    ):
        """记录向量化日志"""
        try:
            log_data = {
                "knowledge_item_id": item_id,
                "status": status,
                "chunk_count": chunk_count,
                "processing_time_ms": processing_time_ms
            }
            if error_message:
                log_data["error_message"] = error_message[:500]
            
            supabase.table("vectorization_logs").insert(log_data).execute()
        except Exception as e:
            logger.warning(f"[WARN] 日志记录失败: {e}")
    
    async def batch_vectorize(
        self,
        item_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        include_failed: bool = True
    ) -> Dict[str, Any]:
        """
        批量向量化处理
        
        Args:
            item_ids: 指定条目ID列表
            user_id: 用户ID
            include_failed: 是否包含失败的条目
        """
        from repository.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        if item_ids:
            items_to_process = item_ids
        else:
            query = supabase.table("knowledge_items").select("id").eq("vector_status", "pending")
            if user_id:
                query = query.eq("user_id", user_id)
            result = query.execute()
            items_to_process = [item["id"] for item in result.data]
            
            if include_failed:
                query_failed = supabase.table("knowledge_items").select("id").eq("vector_status", "failed")
                if user_id:
                    query_failed = query_failed.eq("user_id", user_id)
                failed_result = query_failed.execute()
                items_to_process.extend([item["id"] for item in failed_result.data])
        
        if not items_to_process:
            logger.info("[INFO] 没有待向量化的条目")
            return {"total": 0, "success": 0, "failed": 0, "items": []}
        
        logger.info(f"[INFO] 开始批量向量化 {len(items_to_process)} 个条目")
        
        results = {
            "total": len(items_to_process),
            "success": 0,
            "failed": 0,
            "items": []
        }
        
        for idx, item_id in enumerate(items_to_process, 1):
            try:
                item = supabase.table("knowledge_items").select(
                    "id, name, content"
                ).eq("id", item_id).single().execute()
                
                if not item.data:
                    continue
                
                logger.info(f"[{idx}/{len(items_to_process)}] 向量化: {item.data['name']}")
                
                result = await self.vectorize_with_retry(
                    item_id=item.data["id"],
                    content=item.data.get("content", ""),
                    source_resource=item.data.get("name", "unknown")
                )
                
                if result.success:
                    results["success"] += 1
                    logger.info(f"[OK] 完成: {item.data['name']} ({result.chunk_count} 块)")
                else:
                    results["failed"] += 1
                    logger.error(f"[ERR] 失败: {item.data['name']} - {result.error}")
                
                results["items"].append({
                    "id": item_id,
                    "name": item.data.get("name"),
                    "success": result.success,
                    "chunk_count": result.chunk_count if result.success else 0,
                    "error": result.error if not result.success else None
                })
                
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"[ERR] 处理条目异常: {item_id} - {e}")
                results["failed"] += 1
                results["items"].append({
                    "id": item_id,
                    "success": False,
                    "error": str(e)
                })
        
        logger.info(
            f"[DONE] 批量向量化完成: "
            f"成功 {results['success']}, 失败 {results['failed']}"
        )
        
        return results
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            "embedding": self.embedding_service.get_status(),
            "stats": self._stats.copy(),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()


def get_robust_embedding_service() -> RobustEmbeddingService:
    """获取嵌入服务单例"""
    return RobustEmbeddingService()


def get_robust_vectorization_service() -> RobustVectorizationService:
    """获取向量化服务单例"""
    return RobustVectorizationService()


async def vectorize_knowledge_item_robust(
    item_id: str,
    content: str,
    source_resource: str = "unknown",
    page_number: int = 0
) -> Dict[str, Any]:
    """
    健壮的向量化接口 - 兼容原有接口
    """
    service = get_robust_vectorization_service()
    result = await service.vectorize_with_retry(
        item_id=item_id,
        content=content,
        source_resource=source_resource,
        page_number=page_number
    )
    
    return {
        "success": result.success,
        "chunk_count": result.chunk_count,
        "item_id": result.item_id,
        "error": result.error,
        "processing_time_ms": result.processing_time_ms,
        "backend_used": result.backend_used.value
    }
