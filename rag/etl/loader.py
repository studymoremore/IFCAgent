<<<<<<< Updated upstream
import os
import json
import glob
from config import config

def load_json_files(entity_type: str):
    """
    生成器：遍历指定实体类型的文件夹，yield处理后的文本和原始数据
    """
    # 拼接外部数据路径: processed_downloaded_pages_json/expert
    folder_path = os.path.join(config.RAW_DATA_ROOT, entity_type)
    
    if not os.path.exists(folder_path):
        print(f"Error: 文件夹不存在 - {folder_path}")
        return

    file_pattern = os.path.join(folder_path, "*.json") # 假设是json后缀，如果是txt但内容是json也行
    files = glob.glob(file_pattern)
    
    print(f"Found {len(files)} files in {folder_path}")

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    continue
                
                # 尝试解析JSON
                try:
                    data = json.loads(content)
                    
                    # === 核心逻辑：如何将JSON转为Embedding文本 ===
                    # 方案：将JSON转回字符串，确保包含所有字段
                    # 你也可以在这里做定制，比如只提取 "name" 和 "skills" 组合成字符串
                    text_to_embed = json.dumps(data, ensure_ascii=False, indent=0)
                    
                    yield file_path, text_to_embed, data
                    
                except json.JSONDecodeError:
                    # 如果不是标准JSON，视作纯文本处理
                    yield file_path, content, {"raw_content": content}
                    
        except Exception as e:
=======
import os
import json
import glob
from config import config

def load_json_files(entity_type: str):
    """
    生成器：遍历指定实体类型的文件夹，yield处理后的文本和原始数据
    """
    # 拼接外部数据路径: processed_downloaded_pages_json/expert
    folder_path = os.path.join(config.RAW_DATA_ROOT, entity_type)
    
    if not os.path.exists(folder_path):
        print(f"Error: 文件夹不存在 - {folder_path}")
        return

    file_pattern = os.path.join(folder_path, "*.json") # 假设是json后缀，如果是txt但内容是json也行
    files = glob.glob(file_pattern)
    
    print(f"Found {len(files)} files in {folder_path}")

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    continue
                
                # 尝试解析JSON
                try:
                    data = json.loads(content)
                    
                    # === 核心逻辑：如何将JSON转为Embedding文本 ===
                    # 方案：将JSON转回字符串，确保包含所有字段
                    # 你也可以在这里做定制，比如只提取 "name" 和 "skills" 组合成字符串
                    text_to_embed = json.dumps(data, ensure_ascii=False, indent=0)
                    
                    yield file_path, text_to_embed, data
                    
                except json.JSONDecodeError:
                    # 如果不是标准JSON，视作纯文本处理
                    yield file_path, content, {"raw_content": content}
                    
        except Exception as e:
>>>>>>> Stashed changes
            print(f"Skipping file {file_path}: {e}")