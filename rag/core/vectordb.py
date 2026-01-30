import os
import faiss
import pickle
import numpy as np
from config.config import RAG_CONFIG as config

class VectorDB:
    def __init__(self, db_name: str):
        self.db_name = db_name
        # 解析并规范化向量库存储路径：支持相对路径（相对于项目根目录）或绝对路径
        base_path = config.get('VECTOR_DB_PATH', 'data/vector_store')
        if not os.path.isabs(base_path):
            # 项目根目录：当前文件的上两级目录（rag/core -> rag -> project_root）
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            candidate = os.path.join(project_root, base_path)
            if os.path.exists(candidate):
                base_path = candidate
            else:
                # 如果 candidate 不存在，也尝试以当前工作目录解析（保持向后兼容）
                base_path = os.path.abspath(base_path)

        # 确保目录存在
        try:
            os.makedirs(base_path, exist_ok=True)
        except Exception:
            pass

        self.index_path = os.path.join(base_path, f"{db_name}.index")
        self.metadata_path = os.path.join(base_path, f"{db_name}_meta.pkl")
        self.dimension = config['EMBEDDING_DIMENSION']
        self.index = None
        self.metadata = []
        
        self._load_or_create()

    def _load_or_create(self):
        """加载已有索引或创建新索引"""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            print(f"[{self.db_name}] 加载已有索引...")
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, "rb") as f:
                self.metadata = pickle.load(f)
        else:
            print(f"[{self.db_name}] 创建新索引...")
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []

    def add_item(self, text: str, vector: list, original_data: dict = None):
        """添加单条数据"""
        if not vector:
            return False
            
        vector_np = np.array(vector, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(vector_np)
        
        self.index.add(vector_np)
        
        record = {
            "id": len(self.metadata),
            "text": text,
            "original_data": original_data or {}
        }
        self.metadata.append(record)
        return True

    def save(self):
        """持久化到磁盘"""
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, "wb") as f:
                pickle.dump(self.metadata, f)
            print(f"[{self.db_name}] 保存成功，当前数据量: {len(self.metadata)}")
        except Exception as e:
            print(f"[{self.db_name}] 保存失败: {e}")

    def get_vector_by_name(self, name: str):
        """
        根据专家姓名获取其 embedding 向量
        改进：严格匹配元数据中的 title 字段，避免被 text 中的公共专利内容误导
        """
        found_idx = -1
        found_text = ""
        
        for i, meta in enumerate(self.metadata):
            orig = meta.get("original_data", {})
            # 从 original_data 的不同可能层级获取 title
            actual_title = orig.get("title") or orig.get("data", {}).get("title")
            
            # 使用严格相等比对
            if actual_title and str(actual_title).strip() == name.strip():
                found_idx = i
                found_text = meta.get("text", "")
                break
        
        if found_idx == -1:
            print(f"未找到名为 '{name}' 的严格匹配记录。")
            return None, None

        try:
            vector = self.index.reconstruct(found_idx)
            return vector, found_text
        except Exception as e:
            print(f"无法重建向量: {e}")
            return None, None