import os
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('all_proxy', None)
import sys
import json
import json5
from concurrent.futures import ThreadPoolExecutor, as_completed
# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录（当前文件的父目录）
project_root = os.path.dirname(current_dir)
# 将项目根目录添加到sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.config import LLM_CONFIG, PROJECT_CONFIG
llm = LLM_CONFIG
from agents.recommendation_manager import RecommendationManager

if __name__ == "__main__":
    # 从PROJECT_CONFIG加载项目数据
    projects_data = []
    projects_path = PROJECT_CONFIG['data_path']['projects']
    projects_abs_path = os.path.join(project_root, projects_path)
    if os.path.exists(projects_abs_path):
        for filename in os.listdir(projects_abs_path):
            if filename.endswith('.json'):
                file_path = os.path.join(projects_abs_path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                        projects_data.append(project_data)
                        print(f"已加载: {filename}")
                except Exception as e:
                    print(f"加载文件 {filename} 时出错: {e}")
    
    print(f"\n总共加载了 {len(projects_data)} 个项目文件")
    
    # 并行度配置
    parallel_degree = PROJECT_CONFIG.get('parallel_projects', 5)
    print(f"并行度设置为：{parallel_degree}")
    
    def process_project(index, project_data, total_projects):
        """处理单个项目的推荐任务"""
        try:
            project_title = project_data.get('标题', f'项目{index+1}')
            print(f"\n[{index+1}/{total_projects}] 开始处理项目：{project_title}")
            
            recommendation_manager = RecommendationManager(llm=llm)
            expert_candidates = recommendation_manager.retrieve_expert_candidates(project_data)
            agent_pairs = recommendation_manager.create_agent_pairs(expert_candidates, project_data)
            discussion_results = recommendation_manager.collect_discussion_results(agent_pairs)
            ranked_experts = recommendation_manager.evaluate_and_rerank(
                discussion_results, expert_candidates, project_data=project_data
            )
            
            print(f"[{index+1}/{total_projects}] 项目 {project_title} 处理完成")
            return index, project_title, ranked_experts, None
        except Exception as e:
            error_msg = f"项目 {project_data.get('标题', f'项目{index+1}')} 处理失败：{str(e)}"
            print(f"[{index+1}/{total_projects}] {error_msg}")
            return index, project_data.get('标题', f'项目{index+1}'), None, error_msg
    
    # 并行处理
    total_projects = len(projects_data)
    results = [None] * total_projects
    
    with ThreadPoolExecutor(max_workers=parallel_degree) as executor:
        future_to_index = {
            executor.submit(process_project, idx, project_data, total_projects): idx
            for idx, project_data in enumerate(projects_data)
        }
        
        completed_count = 0
        for future in as_completed(future_to_index):
            index, project_title, ranked_experts, error = future.result()
            results[index] = {
                'project_title': project_title,
                'ranked_experts': ranked_experts,
                'error': error
            }
            completed_count += 1
            print(f"\n总体进度：{completed_count}/{total_projects} 个项目已完成")
    
    # 输出结果
    print("\n" + "="*80)
    print("所有项目处理完成！")
    print("="*80)
    for result in results:
        if result['error']:
            print(f"\n项目 {result['project_title']}：失败 - {result['error']}")
        else:
            print(f"\n项目 {result['project_title']}：成功")
            print(f"推荐结果：{result['ranked_experts']}")