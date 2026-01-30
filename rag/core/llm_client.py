import requests
import time
from config.config import RAG_CONFIG as config
import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# from utils.prompt_logger import get_logger  # [PROMPT_LOGGER] 取消注释以启用prompt记录

def get_embedding(text: str, retry_count=3) -> list:
    """
    获取文本的向量表示，带有简单的重试机制
    """
    MAX_CHAR_LENGTH = 12000
    if len(text) > MAX_CHAR_LENGTH:
        print(f"  [Warning] 文本过长 ({len(text)} 字)，已截断。")
        text = text[:MAX_CHAR_LENGTH]
    headers = {
        "Authorization": f"Bearer {config['API_KEY']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config['EMBEDDING_MODEL'],
        "input": text
    }

    # [PROMPT_LOGGER] 记录embedding调用 - 取消注释以启用
    # logger = get_logger()
    # logger.log_embedding_call(
    #     text=text,
    #     model=config['EMBEDDING_MODEL'],
    #     additional_info={
    #         "url": config['EMBEDDING_URL'],
    #         "text_length": len(text)
    #     }
    # )
    
    for i in range(retry_count):
        try:
            response = requests.post(config['EMBEDDING_URL'], json=payload, headers=headers, timeout=60)
            if response.status_code == 200: 
                return response.json()['data'][0]['embedding']
            else:
                error_detail = response.text
                
                print(f"Warning: API returned {response.status_code}, Detail: {error_detail}")
                time.sleep(1)
        except Exception as e:
            print(f"Error requesting embedding: {e}")
            time.sleep(1)
            
    # 如果重试多次失败，返回None或抛出异常，这里返回空列表由上层处理
    return []