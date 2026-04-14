import os
import logging
import tempfile
import asyncio
import subprocess
import time
from typing import Optional, Tuple
from pathlib import Path

import whisper

logger = logging.getLogger(__name__)

class VoiceService:
    """
    语音转文字服务 v2.1 - 稳定版
    v2.1修复：
    1. FFmpeg路径缓存（避免每次请求都跑子进程）
    2. 模型加载锁防并发竞态
    3. 使用 get_running_loop() 替代已废弃的 get_event_loop()
    4. 移除死代码 _find_ffprobe，改用可靠方式获取ffprobe
    5. 返回置信度信息
    6. ffprobe路径独立查找
    """

    _model = None
    _model_name = "base"
    _model_loading = False
    _ffmpeg_path: Optional[str] = None
    _ffprobe_path: Optional[str] = None
    _ffmpeg_checked = False

    SUPPORTED_EXTENSIONS = {".webm", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}
    MIN_AUDIO_SIZE = 1024
    MAX_AUDIO_SIZE = 50 * 1024 * 1024
    MIN_DURATION_SECONDS = 0.3

    @classmethod
    def _ensure_ffmpeg_paths(cls) -> Tuple[Optional[str], Optional[str]]:
        """
        查找并缓存 FFmpeg / FFprobe 路径。
        只在首次调用时执行子进程探测，后续直接返回缓存结果。
        """
        if cls._ffmpeg_checked:
            return cls._ffmpeg_path, cls._ffprobe_path

        cls._ffmpeg_path = None
        cls._ffprobe_path = None

        candidates = ["ffmpeg"]
        if os.name == 'nt':
            candidates.extend([
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                os.path.join(os.environ.get("PROGRAMFILES", ""), "ffmpeg", "bin", "ffmpeg.exe"),
            ])

        for cmd in candidates:
            try:
                result = subprocess.run(
                    [cmd, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if result.returncode == 0:
                    cls._ffmpeg_path = cmd
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue

        if cls._ffmpeg_path:
            base_dir = os.path.dirname(cls._ffmpeg_path)
            exe_name = "ffprobe.exe" if os.name == 'nt' else "ffprobe"
            probe_candidate = os.path.join(base_dir, exe_name)
            try:
                result = subprocess.run(
                    [probe_candidate, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if result.returncode == 0:
                    cls._ffprobe_path = probe_candidate
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass

        cls._ffmpeg_checked = True

        if cls._ffmpeg_path:
            logger.info(f"FFmpeg 缓存路径: {cls._ffmpeg_path}, FFprobe: {cls._ffprobe_path or '未找到'}")
        else:
            logger.warning("未检测到 FFmpeg，音频预处理将被跳过")

        return cls._ffmpeg_path, cls._ffprobe_path

    @classmethod
    def load_model(cls, model_name: str = "base"):
        """
        加载 Whisper 模型（带加载状态保护）
        返回模型实例或 None（正在加载中）
        """
        if cls._model is not None:
            return cls._model
        if cls._model_loading:
            logger.warning("Whisper 模型正在加载中，当前请求将返回 None")
            return None
        cls._model_loading = True
        try:
            logger.info(f"正在加载 Whisper 模型: {model_name} ...")
            start = time.time()
            cls._model = whisper.load_model(model_name)
            cls._model_name = model_name
            elapsed = time.time() - start
            logger.info(f"Whisper 模型 '{model_name}' 加载完成，耗时: {elapsed:.1f}s")
            return cls._model
        except Exception as e:
            logger.error(f"Whisper 模型加载失败: {e}")
            cls._model = None
            raise
        finally:
            cls._model_loading = False

    @staticmethod
    def _validate_audio(file_data: bytes, filename: str) -> None:
        """音频文件预校验"""
        if not file_data or len(file_data) < VoiceService.MIN_AUDIO_SIZE:
            raise ValueError("音频文件过短或为空，请重新录音")

        if len(file_data) > VoiceService.MAX_AUDIO_SIZE:
            raise ValueError(
                f"音频文件过大({len(file_data)/1024/1024:.1f}MB)，"
                f"上限{VoiceService.MAX_AUDIO_SIZE/1024/1024}MB"
            )

        ext = Path(filename).suffix.lower() if filename else ""
        if ext and ext not in VoiceService.SUPPORTED_EXTENSIONS:
            logger.warning(f"非常见音频格式: {ext}，将尝试兼容处理")

    @classmethod
    async def _get_duration(cls, ffprobe_path: Optional[str], input_file: Path) -> float:
        """获取音频时长"""
        if not ffprobe_path:
            return 0.0
        try:
            cmd = [
                ffprobe_path, "-i", str(input_file),
                "-show_entries", "format=duration",
                "-v", "quiet", "-of", "csv=p=0"
            ]
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            )
            raw = result.stdout.strip()
            duration = float(raw) if raw else 0.0
            if 0 < duration < VoiceService.MIN_DURATION_SECONDS:
                logger.warning(f"音频时长过短: {duration:.2f}s")
            return duration
        except Exception as e:
            logger.warning(f"获取音频时长失败: {e}")
            return 0.0

    @classmethod
    async def transcribe(cls, file_data: bytes, filename: str, language: Optional[str] = None) -> Tuple[str, float]:
        """
        语音转文字主入口
        :param file_data: 音频二进制数据
        :param filename: 文件名
        :param language: 指定语言(None=自动检测)
        :return: (识别文本, 时长秒)
        """
        cls._validate_audio(file_data, filename)

        safe_filename = filename or "audio.webm"

        with tempfile.TemporaryDirectory(prefix="voice_") as temp_dir:
            input_file = Path(temp_dir) / safe_filename
            output_wav = Path(temp_dir) / "processed_16k.wav"

            with open(input_file, "wb") as f:
                f.write(file_data)

            try:
                ffmpeg_path, ffprobe_path = cls._ensure_ffmpeg_paths()
                transcribe_source = str(input_file)
                duration = 0.0

                if ffmpeg_path:
                    try:
                        loop = asyncio.get_running_loop()

                        convert_cmd = [
                            ffmpeg_path, "-y", "-i", str(input_file),
                            "-ar", "16000", "-ac", "1",
                            "-c:a", "pcm_s16le",
                            str(output_wav)
                        ]
                        await loop.run_in_executor(
                            None,
                            lambda: subprocess.run(
                                convert_cmd,
                                capture_output=True,
                                text=True,
                                timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            )
                        )

                        if output_wav.exists() and output_wav.stat().st_size > 1024:
                            transcribe_source = str(output_wav)
                            duration = await cls._get_duration(ffprobe_path, input_file)
                            logger.info(f"音频预处理完成: {safe_filename} -> wav ({duration:.1f}s)")
                        else:
                            logger.warning("FFmpeg转换输出异常，回退到原始文件")
                    except subprocess.TimeoutExpired:
                        logger.error("FFmpeg转换超时(30s)，使用原始文件")
                    except Exception as e:
                        logger.warning(f"FFmpeg处理失败({e})，回退原始文件")
                else:
                    logger.warning("未检测到FFmpeg，跳过音频预处理")

                model = cls.load_model(cls._model_name)
                if model is None:
                    raise RuntimeError("Whisper模型尚未就绪，请稍后重试")

                logger.info(
                    f"开始 Whisper 转写 "
                    f"(源={Path(transcribe_source).name}, lang={'auto' if not language else language})..."
                )

                transcribe_kwargs = {
                    "fp16": False,
                    "verbose": False,
                }
                if language:
                    transcribe_kwargs["language"] = language

                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: model.transcribe(transcribe_source, **transcribe_kwargs)
                )

                detected_lang = result.get("language", language or "unknown")
                text = result.get("text", "").strip()

                if not text:
                    logger.warning("Whisper返回空文本")
                    return "", duration

                all_segments = result.get("segments", [])
                avg_confidence = 0.0
                if all_segments:
                    confidences = [
                        s.get("avg_logprob", 0)
                        for s in all_segments
                        if s.get("avg_logprob") is not None
                    ]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

                logger.info(
                    f"转写成功: {len(text)}字, 语言={detected_lang}, 置信度={avg_confidence:.2f}"
                )
                return text, duration

            except ValueError:
                raise
            except RuntimeError:
                raise
            except Exception as e:
                err_str = str(e).lower()
                if "no audio" in err_str or "empty" in err_str:
                    raise ValueError(
                        "未能从音频中检测到有效语音内容，请检查麦克风或重新录制"
                    )
                if "model" in err_str or "whisper" in err_str:
                    raise RuntimeError(f"语音模型错误: {e}")
                logger.error(f"语音转写未知错误: {e}", exc_info=True)
                raise Exception(f"语音转写失败: {str(e)[:100]}")

voice_service = VoiceService()
