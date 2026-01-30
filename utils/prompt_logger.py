"""
LLM Prompt日志记录模块

用于记录每一次LLM调用时使用的完整prompt
"""

import os
import json
import json5
from datetime import datetime
from typing import List, Dict, Any, Optional


class PromptLogger:
    """Prompt日志记录器"""
    
    def __init__(self, log_dir: str = "logs/prompts"):
        """
        初始化日志记录器
        
        Args:
            log_dir: 日志文件存储目录
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.call_count = 0
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳字符串"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    def _get_log_filename(self, agent_type: str = "unknown") -> str:
        """
        获取日志文件名
        
        Args:
            agent_type: 智能体类型（如recommendation_manager, moderator等）
            
        Returns:
            日志文件路径
        """
        date_str = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.log_dir, f"{agent_type}_{date_str}.jsonl")
    
    def _format_messages(self, messages: List[Dict[str, Any]], system_message: Optional[str] = None) -> str:
        """
        格式化消息列表为可读的字符串
        
        Args:
            messages: 消息列表
            system_message: 系统消息（可选）
            
        Returns:
            格式化后的prompt字符串
        """
        parts = []
        
        # 如果有系统消息，先添加系统消息
        if system_message:
            parts.append(system_message)
        
        # 添加消息内容（只提取content字段）
        for msg in messages:
            content = msg.get('content', '')
            
            # 处理content可能是字符串或列表的情况
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                # 如果是列表，提取文本内容
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        parts.append(item.get('text', ''))
                    elif isinstance(item, dict):
                        parts.append(json.dumps(item, ensure_ascii=False))
                    else:
                        parts.append(str(item))
            else:
                parts.append(str(content))
        
        return "\n".join(parts)
    
    def log_llm_call(
        self,
        agent_type: str,
        agent_name: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        """
        记录LLM调用
        
        Args:
            agent_type: 智能体类型（如recommendation_manager, moderator, project_agent等）
            agent_name: 智能体名称（可选，如项目名称、专家名称等）
            messages: 消息列表
            system_message: 系统消息（可选）
            model: 使用的模型名称（可选）
            additional_info: 额外的信息（可选）
        """
        self.call_count += 1
        
        # 构建日志记录（只保存原始的 system_message 和 messages）
        log_entry = {
            "call_id": self.call_count,
            "timestamp": self._get_timestamp(),
            "agent_type": agent_type,
            "agent_name": agent_name,
            "model": model,
            "system_message": system_message,
            "messages": messages
        }
        
        # 写入JSONL文件
        log_file = self._get_log_filename(agent_type)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        # 同时打印到控制台（可选，用于调试）
        # print(f"\n[Prompt Logger] 记录LLM调用 #{self.call_count} - {agent_type}" + 
        #       (f" ({agent_name})" if agent_name else ""))
    
    def log_embedding_call(
        self,
        text: str,
        model: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        """
        记录Embedding API调用
        
        Args:
            text: 输入的文本
            model: 使用的模型名称（可选）
            additional_info: 额外的信息（可选）
        """
        self.call_count += 1
        
        # 构建日志记录
        log_entry = {
            "call_id": self.call_count,
            "timestamp": self._get_timestamp(),
            "call_type": "embedding",
            "model": model,
            "input_text": text,
            "text_length": len(text),
            "additional_info": additional_info or {}
        }
        
        # 写入JSONL文件
        log_file = self._get_log_filename("embedding")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        # 同时打印到控制台（可选，用于调试）
        print(f"\n[Prompt Logger] 记录Embedding调用 #{self.call_count}" + 
              (f" - {model}" if model else ""))


# 全局日志记录器实例
_global_logger: Optional[PromptLogger] = None


def get_logger() -> PromptLogger:
    """获取全局日志记录器实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = PromptLogger()
    return _global_logger


def set_logger(logger: PromptLogger):
    """设置全局日志记录器实例"""
    global _global_logger
    _global_logger = logger
