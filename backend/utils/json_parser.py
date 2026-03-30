import re
import json
import ast
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def clean_and_extract_json(text: str) -> Any:
    """
    终极 JSON 提取与清洗函数：
    1. 从杂乱文本中提取 {...} 或 [...]
    2. 移除所有 Markdown 干扰字符 (**, -, # 等)
    3. 规整引号与换行
    4. 宽容解析并提供默认回退
    """
    if not text or not isinstance(text, str):
        return None
        
    try:
        # --- 第一步：精准提取 JSON 片段 ---
        # 寻找第一个 { 或 [ 开始，最后一个 } 或 ] 结束
        start_idx = -1
        end_idx = -1
        
        # 寻找起始位置
        brace_pos = text.find('{')
        bracket_pos = text.find('[')
        
        if brace_pos != -1 and (bracket_pos == -1 or brace_pos < bracket_pos):
            start_idx = brace_pos
            # 寻找最后一个 }
            end_idx = text.rfind('}')
        elif bracket_pos != -1:
            start_idx = bracket_pos
            # 寻找最后一个 ]
            end_idx = text.rfind(']')
            
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            logger.error("文本中未找到合法的 JSON 结构标记")
            return None
            
        json_str = text[start_idx:end_idx + 1]
        
        # --- 第二步：深度清洗内容 ---
        # 1. 移除所有 Markdown 格式符号 (针对字符串内容)
        # 注意：这里我们主要移除引起歧义的加粗、斜体等，而不是结构化的 [] {}
        json_str = re.sub(r'\*\*', '', json_str) # 移除 **内容**
        json_str = re.sub(r'(?m)^[\s]*[-*+][\s]+', '', json_str) # 移除行首列表符 - * +
        json_str = re.sub(r'#+', '', json_str)   # 移除 # 标题符
        
        # 2. 移除所有字面换行符 (JSON 字符串内不能有硬换行)
        # 将字符串内的换行符替换为空格或 \n
        # 这是一个近似处理，但在教学辅助场景效果很好
        json_str = json_str.replace('\n', ' ').replace('\r', ' ')
        
        # 3. 修复 AI 常见的未转义引号（进阶版）
        # 我们的 Prompt 已经要求内容用单引号，边界用双引号
        # 这里补全：如果发现内容中还有双引号，尝试转义
        # 逻辑：非结构化位置的双引号进行转义 (这里的正则匹配比较保守)
        # 我们先处理所有的 \" 为 "
        json_str = json_str.replace('\\"', '"')
        # 然后把非结构化的 " 转义
        # 寻找被 " 包裹的字符串，并处理其中的 "
        # 这是一个极简的实现，针对用户提出的 "赋值为"张三"" 情况
        def quote_fixer(match):
            m = match.group(0)
            # 如果匹配到的内容内部还有双引号，转义它
            content = m[1:-1]
            fixed = content.replace('"', '\\"')
            return f'"{fixed}"'
            
        # 识别 JSON 字符串的正则
        json_str = re.sub(r'"(.*?)"', quote_fixer, json_str)

        # 4. 移除多余的尾随逗号
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # --- 第三步：多重解析回退 ---
        # 方案 A: 标准解析
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
            
        # 方案 B: AST 宽容解析 (处理单引号键名或 True/False)
        try:
            # 兼容标准 JSON 中的关键字
            safe_eval = json_str.replace('null', 'None').replace('true', 'True').replace('false', 'False')
            result = ast.literal_eval(safe_eval)
            if isinstance(result, (dict, list)):
                return result
        except:
            pass
            
        # 方案 C: 极其激进的单双引号互换尝试
        try:
            # 有时 AI 会输出 {'key': 'value'}，这在 JSON 中是不合法的
            alt_json = json_str.replace("'", '"')
            return json.loads(alt_json)
        except:
            pass
            
        return None

    except Exception as e:
        logger.error(f"终极 JSON 清洗失败: {e}")
        return None
