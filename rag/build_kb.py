import argparse
import os
import json
import numpy as np
import copy
from config import config
from core.llm_client import get_embedding
from core.vectordb import VectorDB

def build_database():
    print("=== 正在启动 RAG 数据库物理隔离式构建 ===")
    
    for entity_type in config.ENTITY_TYPES:
        db_key = config.ENTITY_MAP.get(entity_type, entity_type)
        print(f"\n检查实体类型: {entity_type} ...")
        db = VectorDB(db_name=db_key)
        
        # 1. 物理回滚保护：如果数据量异常，回滚到 6702 条安全点
        if entity_type == "expert" and len(db.metadata) > 6702:
            print(f"  [Safety] 正在物理回滚至 6702 条安全点...")
            import faiss
            safe_vectors = [db.index.reconstruct(i) for i in range(6702)]
            new_index = faiss.IndexFlatIP(config.EMBEDDING_DIMENSION)
            new_index.add(np.array(safe_vectors).astype('float32'))
            db.index = new_index
            db.metadata = db.metadata[:6702]
            db.save()

        # 2. 构建查重集合
        existing_titles = set()
        for meta in db.metadata:
            orig = meta.get("original_data", {})
            t = orig.get("title") or orig.get("data", {}).get("title")
            if t: existing_titles.add(str(t).strip())

        # 3. 物理扫描文件夹进行补录
        folder_path = os.path.join(config.RAW_DATA_ROOT, entity_type)
        if not os.path.exists(folder_path): continue
        
        files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        success_count = 0

        for file_name in files:
            file_path = os.path.join(folder_path, file_name)
            expert_name = file_name.replace(".json", "").strip()

            if expert_name in existing_titles:
                continue

            try:
                # 4. 强制物理重读：确保读取的内容与文件名完全匹配
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    # 重新转换为字符串用于 Embedding
                    text_for_embedding = json.dumps(raw_data, ensure_ascii=False)

                # 5. 长度截断
                if len(text_for_embedding) > 30000:
                    text_for_embedding = text_for_embedding[:30000]

                print(f"  [新入库] {expert_name}...")
                vector = get_embedding(text_for_embedding)
                
                if vector:
                    # 强行校准内部标题
                    if "data" in raw_data: raw_data["data"]["title"] = expert_name
                    raw_data["title"] = expert_name
                    
                    db.add_item(
                        text=text_for_embedding,
                        vector=vector,
                        original_data=copy.deepcopy(raw_data)
                    )
                    success_count += 1
            except Exception as e:
                print(f"  ❌ 处理 {file_name} 失败: {e}")

        if success_count > 0:
            db.save()
            print(f"  ✅ {entity_type} 处理完成，新增 {success_count} 条。")

def inspect_expert(name):
    """
    增强版调试函数：展示向量特征并精简文本输出
    """
    from core.vectordb import VectorDB
    import re
    
    db = VectorDB(db_name="expert")
    vector, full_text = db.get_vector_by_name(name)
    
    if vector is not None:
        print(f"\n" + "★" * 60)
        print(f"【 检索键 】: {name}")
        print("-" * 60)
        
        # 1. 向量前 20 位预览 (格式化为小数点后 4 位)
        v_preview = [f"{x:.8f}" for x in vector[:20]]
        print(f"【 向量预览 (前20位) 】:\n{v_preview}")
        print("-" * 60)
        
        # 2. 尝试提取元数据标题
        title_match = re.search(r'"title":\s*"([^"]+)"', str(full_text))
        real_title = title_match.group(1) if title_match else "Unknown"
        print(f"【 实际标题 】: {real_title}")
        
        # 3. 精简文本预览 (仅展示前 150 个字符，更易读)
        clean_text = str(full_text)[:150].replace('\n', ' ').strip()
        print(f"【 内容预览 】: {clean_text}...")
        
        # 4. 最终状态判定
        if real_title.strip() == name.strip():
            print("\n✨ 状态检查：[ 正常 ] - 索引与物理内容严格一致")
        else:
            print("\n🚨 状态检查：[ 异常 ] - 发现身份错位！")
            
        print("★" * 60 + "\n")
    else:
        print(f"\n❌ 检索失败：库中未找到专家 【{name}】\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--inspect', type=str)
    args = parser.parse_args()

    if args.inspect:
        inspect_expert(args.inspect)
    else:
        build_database()
