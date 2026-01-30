"""
推荐管理智能体

负责：
1. 调用检索工具，召回候选专家
2. 创建多个主持人、项目、专家智能体对，并行进行多轮对话
3. 收集各个会话的结果
4. 对召回的专家的匹配度评估重排
5. 整理本次推荐的解释信息
6. 将最优的专家向用户推荐
7. 生成集成属性匹配、能力评估的推荐报告
"""

from qwen_agent.agents import Assistant
import os
import sys
import json
import json5
import time
import numpy as np
import faiss
# 添加项目根目录到Python路径，确保可以正确导入模块
# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录（当前文件的父目录）
project_root = os.path.dirname(current_dir)
# 将项目根目录添加到sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from config.config import PROJECT_CONFIG
from tools.rag_tool import RAGTool
from agents.project_agent import ProjectAgent
from agents.expert_agent import ExpertAgent
from agents.moderator import Moderator
from config.config import LLM_CONFIG
# from utils.prompt_logger import get_logger  # [PROMPT_LOGGER] 取消注释以启用prompt记录

llm = LLM_CONFIG

import dashscope

from rag.core.vectordb import VectorDB

class RecommendationManager(Assistant):
    """推荐管理智能体"""
    
    def __init__(self, llm=None, **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.config = PROJECT_CONFIG
        self.top_k = PROJECT_CONFIG['candidate_experts_per_project']
        self.results = []
        self.rag_tool = RAGTool()
        self.expert_db = VectorDB(db_name="expert")
        # 保存system_message用于日志记录（如果有的话）
        if 'system_message' in kwargs:
            self.system_message = kwargs['system_message']
        else:
            self.system_message = getattr(self, 'system_message', None)
        # # 初始化 DashScope API Key
        # if dashscope:
        #     from config.config import LLM_CONFIG
        #     api_key = LLM_CONFIG.get('api_key') or os.getenv('DASHSCOPE_API_KEY')
        #     if api_key:
        #         dashscope.api_key = api_key
        
    def retrieve_expert_candidates(self, project_data):
        """
        利用项目向量在专家数据库中召回候选专家
        """
        # 1. 将项目数据转换为字符串用于 Embedding
        if not isinstance(project_data, str):
            project_text = json5.dumps(project_data, ensure_ascii=False)
        else:
            project_text = project_data
        
        # 2. 获取项目向量
        project_vector = None
        try:
            # response = Embedding.call(
            #     model='text-embedding-v2',
            #     input=project_text
            # )
            # if response.status_code == 200:
            #     project_vector = response.output['embeddings'][0]['embedding']
            from rag.core.llm_client import get_embedding
            project_vector = get_embedding(project_text)
            #print(project_vector)
        except Exception as e:
            print(f"项目向量化失败: {e}")
            return []

        if project_vector is None:
            return []

        # 3. 准备检索参数
        top_k = self.top_k
        query_np = np.array(project_vector, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(query_np)
        
        # 4. 执行向量检索
        scores, indices = self.expert_db.index.search(query_np, top_k)
        
        # 5. 反向查找专家姓名和 ID
        expert_candidates = []
        for idx in indices[0]:
            if idx == -1: continue # 未匹配到结果
            
            # 从 metadata 中提取昨晚存入的原始信息
            meta = self.expert_db.metadata[idx]
            orig_data = meta.get("original_data", {})
            
            # 根据数据结构尝试获取姓名
            expert_name = orig_data.get("title") or orig_data.get("data", {}).get("title") or "未知专家"
            
            expert_candidates.append({
                'id': str(idx), 
                'name': expert_name
            })
        print(f"召回候选专家: {[exp['name'] for exp in expert_candidates]}")
        timestamp = time.time()
        local_time = time.localtime(timestamp)
        formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        self.start_time = timestamp

        print(f"开始讨论时间：{formatted_time}")
        return expert_candidates
    
    def create_agent_pairs(self, expert_candidates, project_data):
        """
        创建多个智能体对（主持人、项目、专家）
        
        Args:
            expert_candidates: 候选专家列表，每个元素包含 'id' 和 'name' 字段
            
        Returns:
            智能体对列表
        """
        expert_profiles = []
        experts_dir = self.config['data_path']['experts']
        
        # 确保路径是绝对路径
        if not os.path.isabs(experts_dir):
            experts_dir = os.path.join(project_root, experts_dir)
        
        for expert in expert_candidates:
            expert_name = expert.get('name', '')
            expert_id = expert.get('id', '')
            
            if not expert_name:
                print(f"警告：专家 {expert_id} 没有名字，跳过")
                continue
            
            # 构建JSON文件路径
            expert_file_path = os.path.join(experts_dir, f"{expert_name}.json")
            
            # 检查文件是否存在
            if not os.path.exists(expert_file_path):
                print(f"警告：专家文件不存在：{expert_file_path}")
                continue
            
            # 加载JSON文件
            try:
                with open(expert_file_path, 'r', encoding='utf-8') as f:
                    expert_data = json5.load(f)
                    expert_profiles.append(expert_data)
            except Exception as e:
                print(f"错误：加载专家文件失败 {expert_file_path}：{str(e)}")
                continue
        
        agent_pairs = []
        for expert in expert_profiles:
            expert_agent = ExpertAgent(expert, llm=llm, name=expert['data']['title'])
            project_agent = ProjectAgent(project_data, llm=llm, name=project_data['标题'])
            moderator = Moderator(llm=llm)
            agent_pairs.append((moderator, project_agent, expert_agent))
        return agent_pairs
    
    def collect_discussion_results(self, agent_pairs):
        """
        收集各个会话的讨论结果
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def run_discussion(index, moderator, project_agent, expert_agent):
            """执行单个讨论任务"""
            print(f"开始讨论第{index+1}个任务，项目：{project_agent.name}，专家：{expert_agent.name}")
            return index, moderator.organize_discussion(project_agent, expert_agent)['report']
        
        discussion_results = [None] * len(agent_pairs)
        print(f"开始并行讨论，共有{len(agent_pairs)}个讨论任务")
        with ThreadPoolExecutor(max_workers=len(agent_pairs)) as executor:
            future_to_index = {
                executor.submit(run_discussion, idx, moderator, project_agent, expert_agent): idx
                for idx, (moderator, project_agent, expert_agent) in enumerate(agent_pairs)
            }
            for future in as_completed(future_to_index):
                index, report = future.result()
                discussion_results[index] = report
                
        return discussion_results
    
    def evaluate_and_rerank(self, discussion_results, expert_candidates=None, project_data=None):
        """
        对召回的实体的匹配度评估重排       
        根据讨论结果，评估每个专家与项目的匹配度，并进行重排序
        """
        
        # 构建评估提示词
        prompt_parts = []
        prompt_parts.append("你是一个推荐评估专家，需要根据项目与专家的讨论结果，对专家进行匹配度评估和重排序。")
        prompt_parts.append("")
        prompt_parts.append("## 讨论结果")
        prompt_parts.append("")
        prompt_parts.append(f"以下是 {len(discussion_results)} 个专家与项目的讨论结果，每个讨论结果包含了匹配度分析、共识点和分歧点。")
        prompt_parts.append("")
        
        # 为每个讨论结果编号并展示
        for idx, report in enumerate(discussion_results, 1):
            prompt_parts.append(f"### 专家 {idx} 的讨论结果")
            prompt_parts.append(str(report))
            prompt_parts.append("")
        
        prompt_parts.append("## 评估任务")
        prompt_parts.append("")
        prompt_parts.append("请根据以上讨论结果，完成以下任务：")
        prompt_parts.append("1. **评估匹配度**：为每个专家评估与项目的匹配度得分（0-100分）")
        prompt_parts.append("2. **分析匹配情况**：分析每个专家的匹配优势和不匹配的地方")
        prompt_parts.append("3. **重排序**：根据匹配度对所有专家进行重排序（从高到低）")
        prompt_parts.append("4. **给出理由**：为每个专家给出详细的重排理由，说明为什么排在这个位置")
        prompt_parts.append("")
        prompt_parts.append("## 评估维度")
        prompt_parts.append("请综合考虑以下维度进行评分：")
        prompt_parts.append("- **技术能力匹配**（权重30%）：专家的技术专长、研究领域是否与项目需求匹配")
        prompt_parts.append("- **经验匹配**（权重25%）：专家的过往经验、历史成果是否与项目目标相似")
        prompt_parts.append("- **资源匹配**（权重20%）：专家所在组织的资源、资质是否满足项目要求")
        prompt_parts.append("- **意愿匹配**（权重15%）：专家对项目的合作意愿和条件是否匹配")
        prompt_parts.append("- **讨论质量**（权重10%）：讨论中展现的匹配证据、共识程度和讨论深度")
        prompt_parts.append("")
        prompt_parts.append("## 输出格式")
        prompt_parts.append("请严格按照以下JSON格式输出结果：")
        prompt_parts.append("""{
  "ranked_experts": [
    {
      "expert_index": 1,
      "score": 85,
      "reason": "该专家在技术能力匹配方面表现突出，其专业领域与项目需求高度吻合。讨论中展现了充分的技术实力和合作意愿，在多个维度上都有良好的匹配表现。"
    },
    {
      "expert_index": 2,
      "score": 72,
      "reason": "该专家在经验匹配方面有一定优势，但在资源匹配方面存在不足。讨论中展现了一定的合作意愿，但技术能力与项目需求的匹配度中等。"
    }
  ]
}""")
        prompt_parts.append("")
        prompt_parts.append("**重要说明**：")
        prompt_parts.append("- `expert_index` 是讨论结果的序号（从1开始，对应上面的'专家 1'、'专家 2'等）")
        prompt_parts.append("- `score` 是综合匹配度得分（0-100的整数）")
        prompt_parts.append("- `reason` 是详细的重排理由，需要说明该专家为什么排在这个位置，包括匹配优势和不匹配的地方")
        prompt_parts.append("- 请确保所有专家都被包含在 `ranked_experts` 列表中，且按得分从高到低排序")
        
        # 调用 LLM 进行评估
        messages = [{'role': 'user', 'content': '\n'.join(prompt_parts)}]
        
        # [PROMPT_LOGGER] 记录prompt - 取消注释以启用
        # logger = get_logger()
        # system_message = getattr(self, 'system_message', None)
        # project_name = project_data.get('标题', '未知项目') if isinstance(project_data, dict) else '未知项目'
        # logger.log_llm_call(
        #     agent_type="recommendation_manager",
        #     agent_name=f"{project_name}_evaluate_and_rerank",
        #     messages=messages,
        #     system_message=system_message,
        #     model=llm.get('model') if isinstance(llm, dict) else None,
        #     additional_info={
        #         "method": "evaluate_and_rerank",
        #         "discussion_results_count": len(discussion_results)
        #     }
        # )
        
        response_messages = []
        for response in self.run(messages=messages):
            response_messages = response
        
        # 解析响应
        agent_response_text = ""
        for msg in reversed(response_messages):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if isinstance(content, str):
                    agent_response_text = content
                    break
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')
                            if text:
                                agent_response_text = text
                                break
                    if agent_response_text:
                        break
        
        # 如果没有提取到文本，尝试从最后一个消息获取
        if not agent_response_text and response_messages:
            last_msg = response_messages[-1]
            content = last_msg.get('content', '')
            if isinstance(content, str):
                agent_response_text = content
        
        # 解析JSON响应
        ranked_experts = []
        try:
            json_start = agent_response_text.find('{')
            json_end = agent_response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = agent_response_text[json_start:json_end]
                result_data = json5.loads(json_str)
                ranked_indices = result_data.get('ranked_experts', [])
                
                # 将索引转换为专家信息
                for ranked_item in ranked_indices:
                    expert_index = ranked_item.get('expert_index', 0)
                    score = ranked_item.get('score', 0)
                    reason = ranked_item.get('reason', '')
                    
                    # 如果提供了 expert_candidates，使用其信息
                    if expert_candidates and 1 <= expert_index <= len(expert_candidates):
                        expert = expert_candidates[expert_index - 1]
                        ranked_experts.append({
                            'id': expert.get('id', ''),
                            'name': expert.get('name', f'专家{expert_index}'),
                            'score': score,
                            'reason': reason
                        })
                    else:
                        # 如果没有提供 expert_candidates，只返回索引和得分
                        ranked_experts.append({
                            'id': f'expert_{expert_index}',
                            'name': f'专家{expert_index}',
                            'score': score,
                            'reason': reason
                        })
        except Exception as e:
            print(f"解析评估结果失败：{str(e)}")
            print(f"原始响应：{agent_response_text[:500]}")
            if expert_candidates:
                ranked_experts = [
                    {
                        'id': exp.get('id', ''),
                        'name': exp.get('name', ''),
                        'score': 50,
                        'reason': '评估解析失败，保持原始顺序'
                    }
                    for exp in expert_candidates
                ]
        project_name = project_data.get('标题', '未知项目') if isinstance(project_data, dict) else '未知项目'
        # 清理项目名称，移除不适合文件系统的字符
        safe_project_name = project_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        output_path = os.path.join(project_root, "results", safe_project_name)
        os.makedirs(output_path, exist_ok=True)

                # 记录结束讨论时间
        end_time = time.time()
        time_diff = end_time - self.start_time
        
        # 将时间差（秒数）转换为小时:分钟:秒格式
        hours = int(time_diff // 3600)
        minutes = int((time_diff % 3600) // 60)
        seconds = int(time_diff % 60)
        formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # 格式化时间戳为可读格式
        start_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))
        end_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))
        
        print(f"结束讨论时间：{end_time_str}")
        print(f"讨论时间：{formatted_time}")    
        ranked_experts.append({'开始讨论时间': start_time_str})
        ranked_experts.append({'结束讨论时间': end_time_str})
        ranked_experts.append({'讨论时间': formatted_time})


        result_file = os.path.join(output_path, f"{safe_project_name}.json")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(ranked_experts, f, ensure_ascii=False, indent=4)
        return ranked_experts