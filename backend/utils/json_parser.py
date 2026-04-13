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
    
    text = text.strip()
    if not text:
        return None
        
    try:
        json_str = _extract_json_block(text)
        if not json_str:
            logger.error("文本中未找到合法的 JSON 结构标记")
            return None
        
        json_str = _deep_clean_json(json_str)
        
        result = _multi_strategy_parse(json_str)
        if result is not None:
            logger.info(f"[JSON解析] 多策略解析成功")
            return result
        
        result = _repair_and_parse(json_str)
        if result is not None:
            logger.info(f"[JSON解析] 修复解析成功")
            return result
        
        result = _parse_truncated_array(json_str)
        if result is not None:
            logger.info(f"[JSON解析] 截断数组解析成功")
            return result
            
        logger.error(f"JSON 解析全部策略失败 | 内容前 200 字: {json_str[:200]}")
        return None

    except Exception as e:
        logger.error(f"终极 JSON 清洗失败: {e}")
        return None


def _extract_json_block(text: str) -> Optional[str]:
    """提取JSON块，处理嵌套结构和截断情况"""
    start_idx = -1
    start_char = ''
    end_char = ''
    
    brace_pos = text.find('{')
    bracket_pos = text.find('[')
    
    if brace_pos != -1 and (bracket_pos == -1 or brace_pos < bracket_pos):
        start_idx = brace_pos
        start_char = '{'
        end_char = '}'
    elif bracket_pos != -1:
        start_idx = bracket_pos
        start_char = '['
        end_char = ']'
    else:
        return None
    
    brace_depth = 0
    bracket_depth = 0
    in_string = False
    escape_next = False
    found_complete = False
    end_idx = -1
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\' and in_string:
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
            elif char == '[':
                bracket_depth += 1
            elif char == ']':
                bracket_depth -= 1
            
            if start_char == '{' and brace_depth == 0 and bracket_depth == 0:
                end_idx = i
                found_complete = True
                break
            elif start_char == '[' and bracket_depth == 0 and brace_depth == 0:
                end_idx = i
                found_complete = True
                break
    
    if found_complete and end_idx >= start_idx:
        return text[start_idx:end_idx + 1]
    
    end_idx = text.rfind(end_char)
    if end_idx > start_idx:
        return text[start_idx:end_idx + 1]
    
    if start_idx != -1:
        truncated = text[start_idx:]
        logger.info(f"[JSON提取] 检测到截断JSON，返回从位置 {start_idx} 到末尾的内容，长度: {len(truncated)}")
        return truncated
    
    return None


def _parse_truncated_array(json_str: str) -> Optional[List]:
    """专门处理截断的JSON数组"""
    if not json_str.strip().startswith('['):
        return None
    
    try:
        json_str = json_str.strip()
        if not json_str.startswith('['):
            return None
        
        inner = json_str[1:].strip()
        if not inner:
            return []
        
        objects = []
        current_obj = ""
        brace_depth = 0
        in_string = False
        escape_next = False
        
        for char in inner:
            if escape_next:
                current_obj += char
                escape_next = False
                continue
            
            if char == '\\':
                current_obj += char
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                current_obj += char
                continue
            
            if not in_string:
                if char == '{':
                    if brace_depth == 0 and current_obj.strip():
                        current_obj = ""
                    brace_depth += 1
                    current_obj += char
                elif char == '}':
                    brace_depth -= 1
                    current_obj += char
                    if brace_depth == 0:
                        obj_str = current_obj.strip().rstrip(',')
                        if obj_str:
                            try:
                                obj = json.loads(obj_str)
                                objects.append(obj)
                            except:
                                try:
                                    repaired = _complete_truncated_json(obj_str)
                                    if repaired:
                                        obj = json.loads(repaired)
                                        objects.append(obj)
                                except:
                                    pass
                        current_obj = ""
                elif char == ',' and brace_depth == 0:
                    continue
                else:
                    current_obj += char
            else:
                current_obj += char
        
        if current_obj.strip() and brace_depth >= 0:
            obj_str = current_obj.strip().rstrip(',')
            if obj_str and obj_str.startswith('{'):
                try:
                    repaired = _complete_truncated_json(obj_str)
                    if repaired:
                        obj = json.loads(repaired)
                        objects.append(obj)
                except:
                    pass
        
        if objects:
            logger.info(f"[截断数组解析] 成功提取 {len(objects)} 个对象")
            return objects
        
        return None
        
    except Exception as e:
        logger.error(f"[截断数组解析] 失败: {e}")
        return None


def _deep_clean_json(json_str: str) -> str:
    """深度清洗JSON字符串"""
    json_str = re.sub(r'\*\*', '', json_str)
    json_str = re.sub(r'(?m)^[\s]*[-*+][\s]+', '', json_str)
    json_str = re.sub(r'#+', '', json_str)
    
    json_str = re.sub(r'["""]', '"', json_str)
    json_str = re.sub(r"[''']", "'", json_str)
    
    json_str = _normalize_whitespace(json_str)
    
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    return json_str


def _normalize_whitespace(json_str: str) -> str:
    """规范化空白字符，保持字符串内容完整"""
    result = []
    in_string = False
    escape_next = False
    
    for char in json_str:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        
        if char == '\\':
            result.append(char)
            escape_next = True
            continue
        
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        
        if in_string:
            if char in '\n\r\t':
                result.append(' ')
            else:
                result.append(char)
        else:
            result.append(char)
    
    return ''.join(result)


def _multi_strategy_parse(json_str: str) -> Any:
    """多策略解析JSON"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    try:
        safe_eval = json_str.replace('null', 'None').replace('true', 'True').replace('false', 'False')
        result = ast.literal_eval(safe_eval)
        if isinstance(result, (dict, list)):
            return result
    except:
        pass
    
    try:
        alt_json = json_str.replace("'", '"')
        return json.loads(alt_json)
    except:
        pass
    
    return None


def _repair_and_parse(json_str: str) -> Any:
    """尝试修复并解析损坏的JSON"""
    try:
        repaired = _fix_quotes(json_str)
        result = json.loads(repaired)
        return result
    except:
        pass
    
    try:
        repaired = _escape_inner_quotes(json_str)
        result = json.loads(repaired)
        return result
    except:
        pass
    
    try:
        repaired = _complete_truncated_json(json_str)
        if repaired:
            result = json.loads(repaired)
            return result
    except:
        pass
    
    return None


def _fix_quotes(json_str: str) -> str:
    """修复JSON中的引号问题 - 增强版"""
    result = []
    in_string = False
    escape_next = False
    
    for i, char in enumerate(json_str):
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        
        if char == '\\':
            result.append(char)
            escape_next = True
            continue
        
        if char == '"':
            if not in_string:
                in_string = True
                result.append(char)
            else:
                next_non_space = _get_next_non_space(json_str, i + 1)
                if next_non_space in ':,}]':
                    in_string = False
                    result.append(char)
                else:
                    result.append('\\"')
            continue
        
        if in_string and char == "'":
            result.append("\\'")
            continue
        
        result.append(char)
    
    return ''.join(result)


def _get_next_non_space(s: str, start: int) -> str:
    """获取下一个非空白字符"""
    for i in range(start, len(s)):
        if not s[i].isspace():
            return s[i]
    return ''

def _escape_inner_quotes(json_str: str) -> str:
    """转义JSON字符串内部的双引号"""
    result = []
    in_string = False
    escape_next = False
    i = 0
    
    while i < len(json_str):
        char = json_str[i]
        
        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue
        
        if char == '\\':
            result.append(char)
            escape_next = True
            i += 1
            continue
        
        if char == '"':
            if not in_string:
                in_string = True
                result.append(char)
            else:
                next_chars = json_str[i+1:i+10].strip()
                is_end = False
                for c in next_chars:
                    if c in ':,}]':
                        is_end = True
                        break
                    elif c == '"':
                        break
                
                if is_end:
                    in_string = False
                    result.append(char)
                else:
                    result.append('\\"')
            i += 1
            continue
        
        result.append(char)
        i += 1
    
    return ''.join(result)


def _complete_truncated_json(json_str: str) -> Optional[str]:
    """尝试补全被截断的JSON"""
    open_braces = json_str.count('{') - json_str.count('}')
    open_brackets = json_str.count('[') - json_str.count(']')
    
    if open_braces < 0 or open_brackets < 0:
        return None
    
    if open_braces == 0 and open_brackets == 0:
        return None
    
    last_content_pos = -1
    for i in range(len(json_str) - 1, -1, -1):
        if json_str[i] not in ' \t\n\r,:' and not json_str[i].isspace():
            last_content_pos = i
            break
    
    if last_content_pos == -1:
        return None
    
    repaired = json_str[:last_content_pos + 1]
    
    in_string = False
    escape_next = False
    for char in json_str[:last_content_pos + 1]:
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
    
    if in_string:
        repaired += '"'
    
    repaired += ']' * open_brackets + '}' * open_braces
    
    logger.info(f"[JSON修复] 尝试补全截断JSON: 补充 {open_brackets} 个 ], {open_braces} 个 }}")
    
    return repaired
