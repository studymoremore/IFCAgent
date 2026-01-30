import os

class Config:
    # ================= 路径配置 (在此修改) =================
    # 假设你的外部数据集在项目上级目录或其他位置
    # 请确保该路径下包含 expert/, organization/, patent/ 三个文件夹
    RAW_DATA_ROOT = r"../knowledge_graph/kg_build/processed_downloaded_pages_json" 
    
    # 向量库存储路径 (生成的 .index 和 .pkl 文件存放处)
    VECTOR_DB_PATH = "data/vector_store"

    # ================= 模型配置 =================
    API_KEY = "sk-..."
    
    # Embedding 模型
    EMBEDDING_URL = "https://api.siliconflow.cn/v1/embeddings"
    EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B" # 保持和你之前一致
    EMBEDDING_DIMENSION = 4096

    # ================= 业务配置 =================
    # 实体类型对应文件夹名称
    ENTITY_TYPES = ["expert", "organization", "patent"]
    
    # 映射关系 (如果文件夹名和逻辑名不一致，可以在此映射，目前保持一致)
    ENTITY_MAP = {
        "expert": "expert",
        "organization": "organization",
        "patent": "patent"
    }

config = Config()

# 自动创建存储目录
if not os.path.exists(config.VECTOR_DB_PATH):
    os.makedirs(config.VECTOR_DB_PATH)