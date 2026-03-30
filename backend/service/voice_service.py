import os
import logging
import tempfile
import asyncio
import subprocess
from typing import Optional, Tuple
from pathlib import Path

# 仅保留核心依赖：whisper（移除 pydub/pyaudio）
import whisper

logger = logging.getLogger(__name__)

class VoiceService:
    """
    语音转文字服务：负责音频预处理与 Whisper 模型推理
    【无 pydub / pyaudio 依赖版】纯 ffmpeg 处理音频
    """
    _model = None  # 类变量，单例加载模型以节省内存

    @classmethod
    def load_model(cls, model_name: str = "base"):
        """
        加载 Whisper 模型
        推荐模型: base (150MB, 速度快), small (500MB, 准确率更高)
        """
        if cls._model is None:
            logger.info(f"正在加载 Whisper 模型: {model_name}...")
            cls._model = whisper.load_model(model_name)
            logger.info("Whisper 模型加载完成。")
        return cls._model

    @staticmethod
    async def transcribe(file_data: bytes, filename: str) -> Tuple[str, float]:
        """
        识别语音内容（纯ffmpeg处理音频，无pydub依赖）
        :param file_data: 音频文件二进制数据
        :param filename: 原始文件名（带后缀）
        :return: (识别出的文本, 音频总时长)
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / filename
            output_wav = temp_path / "processed.wav"

            # 1. 保存上传的文件
            with open(input_file, "wb") as f:
                f.write(file_data)

            try:
                # 2. 【核心优化】尝试执行ffmpeg转换
                logger.info(f"正在预备转换音频: {filename} -> wav")
                
                # ffmpeg命令：转16kHz单声道wav（Whisper标准格式）
                ffmpeg_cmd = [
                    "ffmpeg", "-i", str(input_file),
                    "-ar", "16000",        # 采样率16k
                    "-ac", "1",            # 单声道
                    "-c:a", "pcm_s16le",   # 音频编码
                    "-y", str(output_wav)  # 覆盖输出
                ]

                # 在Windows下，如果ffmpeg不在环境变量，subprocess.run会抛出WinError 2
                def run_cmd(cmd, name):
                    try:
                        return subprocess.run(
                            cmd, check=True, capture_output=True, 
                            text=True, shell=True # Windows下使用shell=True增加兼容性
                        )
                    except (FileNotFoundError, subprocess.CalledProcessError) as e:
                        # 检查是否是由于找不到命令引起的
                        is_missing = isinstance(e, FileNotFoundError) or "不是内部或外部命令" in str(getattr(e, 'stderr', ''))
                        if is_missing:
                            msg = f"检测到系统缺少 {name}。请访问 https://ffmpeg.org/download.html 下载并安装，或将 bin 目录添加到系统 PATH 环境变量。"
                            logger.error(f"环境错误: {msg}")
                            raise Exception(msg)
                        logger.error(f"{name} 执行失败: {getattr(e, 'stderr', str(e))}")
                        raise Exception(f"{name} 处理音频失败")

                # 尝试转换格式，如果失败则尝试直接转写（Whisper 对某些格式有内置支持）
                try:
                    # A. 转换格式
                    run_cmd(ffmpeg_cmd, "ffmpeg")
                    # B. 获取音频时长
                    duration_cmd = [
                        "ffprobe", "-i", str(input_file),
                        "-show_entries", "format=duration",
                        "-v", "quiet", "-of", "csv=p=0"
                    ]
                    duration_result = run_cmd(duration_cmd, "ffprobe")
                    duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else 0.0
                    transcribe_source = str(output_wav)
                except Exception as e:
                    if "下载并安装" in str(e):
                        logger.warning("FFmpeg 缺失，尝试绕过预处理直接投喂给 Whisper...")
                        transcribe_source = str(input_file)
                        duration = 0.0 # 无法获取时长
                    else:
                        raise e

                # 3. 执行语音识别（逻辑不变）
                logger.info(f"开始 Whisper 转写任务 (源: {transcribe_source})...")
                model = VoiceService.load_model("base")
                
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: model.transcribe(transcribe_source, language="zh", fp16=False)
                )

                text = result.get("text", "").strip()
                logger.info(f"转写成功，长度: {len(text)} 字")
                
                return text, duration

            except subprocess.CalledProcessError as e:
                logger.error(f"音频预处理失败(ffmpeg): {e.stderr}")
                raise Exception("音频格式处理失败，请检查文件格式")
            except Exception as e:
                logger.error(f"语音转写过程发生错误: {str(e)}")
                raise e

# 导出单例
voice_service = VoiceService()