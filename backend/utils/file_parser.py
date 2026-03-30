import io
import base64
import PyPDF2
from docx import Document

def parse_base64_file_to_text(base64_str: str, file_type: str) -> str:
    """
    将 Base64 编码的文件内容转换为纯文本 (.txt 效果)
    """
    try:
        # 解码 base64
        file_bytes = base64.b64decode(base64_str)
        file_io = io.BytesIO(file_bytes)
        text = ""

        if file_type.lower() == 'pdf':
            reader = PyPDF2.PdfReader(file_io)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        
        elif file_type.lower() in ['docx', 'doc']:
            doc = Document(file_io)
            text = "\n".join([para.text for para in doc.paragraphs])
        
        else:
            # 默认为文本格式
            try:
                text = file_bytes.decode('utf-8')
            except:
                text = file_bytes.decode('gbk', errors='ignore')

        return text.strip()
    except Exception as e:
        print(f"File parsing error: {e}")
        return f"解析失败: {str(e)}"
