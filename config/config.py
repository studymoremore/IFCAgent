"""
项目配置文件
"""

# LLM 配置
# ==================== 配置选项 ====================
# 方式1：使用 Qwen 模型（DashScope）
LLM_CONFIG_QWEN = {
    'model': 'qwen-max-latest',
    'model_type': 'qwen_dashscope',
    'api_key': 'sk-...',
    # 如果这里没有设置 'api_key'，它将读取 `DASHSCOPE_API_KEY` 环境变量。
    'generate_cfg': {
        'top_p': 0.8
    }
}

# 方式2：使用 GPT-3.5-turbo（OpenAI 兼容 API）
LLM_CONFIG_GPT = {
    'model': 'gpt-3.5-turbo-0125',
    'model_server': 'https://api.getgoapi.com/v1',  # base_url，去掉 /chat/completions
    'api_key': 'sk-...',
    'generate_cfg': {
        'top_p': 0.8
    }
}

# ==================== 当前使用的配置 ====================
LLM_CONFIG = LLM_CONFIG_GPT  # 默认使用 Qwen 模型

# 项目配置
PROJECT_CONFIG = {
    'candidate_experts_per_project': 5,  # 每个项目加载的候选专家数量
    'parallel_projects': 10,  # 并行处理的项目数量
    'data_path': {
        'projects': './data/projects',
        'experts': './data/experts',
    }
}

# RAG 配置
RAG_CONFIG = {
 # ================= 路径配置 (在此修改) =================
    # 假设你的外部数据集在项目上级目录或其他位置
    # 请确保该路径下包含 expert/, organization/, patent/ 三个文件夹
    'RAW_DATA_ROOT': r"../knowledge_graph/kg_build/processed_downloaded_pages_json",

    # 向量库存储路径 (生成的 .index 和 .pkl 文件存放处)
    'VECTOR_DB_PATH': "rag/data/vector_store",

    # ================= 模型配置 =================
    'API_KEY': "sk-...",
    
    # Embedding 模型
    'EMBEDDING_URL': "https://api.siliconflow.cn/v1/embeddings",
    'EMBEDDING_MODEL': "Qwen/Qwen3-Embedding-8B", # 保持和你之前一致
    'EMBEDDING_DIMENSION': 4096,

    # ================= 业务配置 =================
    # 实体类型对应文件夹名称
    'ENTITY_TYPES': ["expert", "organization", "patent"],
    
    # 映射关系 (如果文件夹名和逻辑名不一致，可以在此映射，目前保持一致)
    'ENTITY_MAP': {
        "expert": "expert",
        "organization": "organization",
        "patent": "patent"
    }
}
from pathlib import Path
import os
# 知识图谱配置
# --- Neo4j 连接配置 ---
# 如果是本地安装的 Neo4j，默认地址通常也是 bolt://localhost:7687
# --- 路径配置 ---
# 使用相对路径，确保在任何人的电脑上都能运行
# 获取项目根目录（config目录的父目录）
_project_root = Path(__file__).parent.parent
_base_dir = _project_root / "knowledge_graph" / "kg_build" / "processed_downloaded_pages_json"

KG_CONFIG = {
    'NEO4J_URI': "bolt://localhost:7687",
    'NEO4J_USER': "neo4j",
    'NEO4J_PASSWORD': "your_password",  # 请替换为你的密码
    'BASE_DIR': str(_base_dir),
    'EXPERT_DIR': str(_base_dir / "expert"),
    'ORG_DIR': str(_base_dir / "organization"),
    'PATENT_DIR': str(_base_dir / "patent"),
}

