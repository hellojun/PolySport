"""
文本处理服务
"""

from typing import List


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    将文本分割成小块

    Args:
        text: 原始文本
        chunk_size: 每块的字符数
        overlap: 重叠字符数

    Returns:
        文本块列表
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # 尝试在句子边界处分割
        if end < len(text):
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else len(text)

    return chunks


class TextProcessor:
    """文本处理器"""

    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        分割文本

        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小

        Returns:
            文本块列表
        """
        return split_text_into_chunks(text, chunk_size, overlap)

    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        预处理文本
        - 移除多余空白
        - 标准化换行
        """
        import re

        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    @staticmethod
    def get_text_stats(text: str) -> dict:
        """获取文本统计信息"""
        return {
            "total_chars": len(text),
            "total_lines": text.count('\n') + 1,
            "total_words": len(text.split()),
        }
