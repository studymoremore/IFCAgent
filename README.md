# IFCAgent
Interaction-Free Collaboration Agent

A scientific reciprocal recommendation system built on the Qwen-Agent framework.

## Overview

IFCAgent is an agent-based scientific reciprocal recommendation system that enables accurate matching between project needs and research experts through a multi-agent collaboration mechanism.

### Core Workflow

1. **Semantic Parsing & Profiling**: The Recommendation Manager Agent performs semantic parsing and profile extraction for the user’s project requirements.
2. **Candidate Retrieval**: A hybrid retrieval tool that integrates a knowledge graph and semantic vectors is used to preliminarily retrieve candidate resources from the database.
3. **Bidirectional Session Mechanism**: Bidirectional sessions are initiated. Both demand-side and supply-side agents load their corresponding profiles, and a Moderator Agent orchestrates multi-round, multi-dimensional matching discussions between the Project Agent (demand side) and the Expert Agent (supply side), dynamically mediating conflicts and converging the discussion.
4. **Recommendation Report Generation**: The Recommendation Manager Agent aggregates discussion outcomes from all sessions and generates a recommendation report that integrates attribute matching, capability evaluation, and path-based evidence, clearly presenting evidence chains such as shared patents.

## Project Structure

IFCAgent/
 ├── agents/                       # Agent modules
 │   ├── **init**.py
 │   ├── main.py                   # Entry of agent modules (actual runtime entry)
 │   ├── recommendation_manager.py # Recommendation Manager Agent
 │   │                              # - Semantic parsing & profiling
 │   │                              # - Create and manage multiple agent pairs
 │   │                              # - Collect discussion results
 │   │                              # - Match scoring, evaluation & reranking
 │   │                              # - Generate recommendation report
 │   ├── moderator.py              # Moderator Agent
 │   │                              # - Organize multi-round, multi-dimensional discussions
 │   │                              # - Dynamically mediate conflicts & converge logic
 │   │                              # - Control discussion strategy and dimensions
 │   │                              # - Call knowledge-graph tools for evidence
 │   ├── project_agent.py          # Project Agent (demand side)
 │   │                              # - Represent project needs
 │   │                              # - Participate in matching discussions
 │   └── expert_agent.py           # Expert Agent (supply side)
 │                                  # - Represent research experts
 │                                  # - Participate in matching discussions
 │
 ├── tools/                        # Tool modules
 │   ├── **init**.py
 │   ├── hybrid_retrieval.py       # Hybrid retrieval tool
 │   │                              # - Combine KG and semantic vector retrieval
 │   │                              # - Preliminary candidate retrieval
 │   ├── rag_tool.py               # RAG retrieval tool
 │   │                              # - Retrieve expert data (patents, organizations, etc.)
 │   │                              # - Vector-similarity-based retrieval
 │   └── kg_retrieval.py           # Knowledge graph retrieval tool
 │                                  # - Retrieve path relations between entities
 │                                  # - Support collaborator/colleague/similar-expert queries
 │                                  # - Convert paths into natural language
 │
 ├── knowledge_graph/              # Knowledge graph module
 │   ├── **init**.py
 │   └── kg_build/                 # KG construction module
 │       ├── build_graph.py        # Main script to build the knowledge graph
 │       ├── kg_tool.py            # KG tool class
 │       ├── kg_utils.py           # KG utility functions
 │       ├── config.py             # KG configuration
 │       ├── docker-compose.yml    # Neo4j Docker configuration
 │       ├── requirements.txt      # Dependencies for KG construction
 │       └── processed_downloaded_pages_json/  # Processed data directory
 │           ├── expert/           # Expert data
 │           ├── organization/     # Organization data
 │           └── patent/           # Patent data
 │
 ├── rag/                          # RAG module
 │   ├── **init**.py
 │   ├── config.py                 # RAG configuration
 │   ├── build_kb.py               # Script to build the vector knowledge base
 │   ├── core/                     # Core modules
 │   │   ├── **init**.py
 │   │   ├── llm_client.py         # LLM client (for embeddings)
 │   │   └── vectordb.py           # Vector DB wrapper (FAISS-based)
 │   ├── etl/                      # ETL modules
 │   │   ├── **init**.py
 │   │   └── loader.py             # Data loader
 │   └── data/                     # RAG data directory
 │       └── vector_store/         # Vector DB storage
 │           ├── *.index           # FAISS index files
 │           └── *_meta.pkl        # Metadata files
 │
 ├── config/                       # Configuration module
 │   ├── **init**.py
 │   └── config.py                 # Project configuration
 │                                  # - LLM config (Qwen/GPT)
 │                                  # - Project settings
 │                                  # - RAG settings
 │                                  # - KG settings (Neo4j)
 │
 ├── utils/                        # Utility modules
 │   ├── **init**.py
 │   ├── data_loader.py            # Data loading utilities
 │   │                              # - Load project requirements
 │   │                              # - Load candidate experts
 │   └── prompt_logger.py          # Prompt logging utility (optional)
 │
 ├── data/                         # Data directory
 │   ├── projects/                 # Project requirements (JSON files)
 │   ├── experts/                  # Expert data (JSON files)
 │   ├── organization/             # Organization data (JSON files)
 │   └── patent/                   # Patent data (JSON files)
 │
 ├── results/                      # Output directory
 │   └── [project_name]/           # Recommendation results per project
 │       ├── [expert_name].json    # Discussion result for a single expert
 │       └── ...                   # Other result files
 │
 ├── main.py                       # Main entry point
 ├── requirements.txt              # Dependencies
 └── README.md                     # Documentation

## Core Components

### 1. Recommendation Manager Agent (RecommendationManager)

**Responsibilities**:
- Perform semantic parsing and profile extraction for project requirements
- Create and manage multiple agent pairs (for each project, create 20 sets of Moderator/Project/Expert agents)
- Collect discussion results from each session
- Evaluate match quality and rerank retrieved entities
- Organize interpretability/explanation information for the current recommendation
- Recommend the best candidates to the user
- Generate a recommendation report integrating attribute matching, capability assessment, and path-based evidence

**Key Methods**:
- `parse_project_requirement()`: Semantic parsing & profiling
- `create_agents()`: Create agent pairs
- `collect_discussion_results()`: Collect discussion results
- `evaluate_and_rerank()`: Evaluate & rerank retrieved entities
- `generate_recommendation_explanations()`: Generate recommendation explanations
- `select_top_recommendations()`: Select top recommendations
- `generate_recommendation_report()`: Generate the recommendation report

### 2. Moderator Agent (Moderator)

**Responsibilities**:
- Organize multi-round, multi-dimensional matching discussions between Project (demand side) and Expert (supply side) agents
- Dynamically mediate conflicts and converge the discussion
- Control discussion strategy and discussion dimensions

**Key Methods**:
- `organize_discussion()`: Start and coordinate discussions between both parties

- `control_discussion_dimensions()`: Control discussion dimensions
  - **Technical Capability Match**: Whether the project’s technical needs/challenges match the expert’s technical expertise
  - **Experience Match**: Whether the project’s goals/expected outputs align with the expert’s prior experience and past outcomes
  - **Resource Match**: Whether the project’s required resources/environment/location align with the expert’s organization qualifications/resources/work location
  - **Willingness Match**: Whether the funding/cooperation mode offered by the project matches the expert’s expectations

- `control_discussion_strategy()`: Control discussion strategy
  - Issue discussion dimensions; each dimension corresponds to one round. Randomly decide which side asks first, and enforce a “one question–one answer” rhythm.
  - In each round, both sides may ask at most 10 questions (to avoid excessive divergence). Either side may end the round early. When ending, both sides should record any questions they remain interested in but have not discussed (or not fully discussed), if any. The moderator records the raw dialogue.
  - After finishing the four dimensions, collect whether either side still has unresolved topics they want to explore. If so, organize a final round without a fixed dimension. The side with more questions asks first; again enforce the “one question–one answer” rhythm and cap questions at 10 per side.
  - At the end of all discussions, the moderator generates a recommendation report containing: (i) consensus points (clearly matched attributes) and (ii) divergence points (mismatches or risks), and sends it to the Recommendation Manager Agent.

- `moderate_conflicts()`: Mediate conflicts
  - The moderator monitors the dialogue trajectory. After each dimension, if it determines that the Project Agent and Expert Agent have deviated or become stuck, it may require both sides to restart that round, summarizing issues from the previous attempt and correcting the direction. Restarts are limited to at most 3 times.
  - When restarting, if needed, the moderator can call `KGRetrieval` to fetch evidence related to the discussion focus and include it as supplementary information in the opening statement of the new round.

### 3. Project Agent (ProjectAgent)

**Responsibilities**:
- Represent project requirements
- Participate in matching discussions with the Expert Agent

**Key Method**:
- `participate_in_discussion()`: Participate in discussion and express project needs

### 4. Expert Agent (ExpertAgent)

**Responsibilities**:
- Represent research experts
- Participate in matching discussions with the Project Agent

**Key Method**:
- `participate_in_discussion()`: Participate in discussion and present expertise and resources

### 5. Hybrid Retrieval Tool (HybridRetrieval)

**Responsibilities**:
- Hybrid retrieval that combines knowledge-graph retrieval and semantic vector retrieval
- Perform preliminary candidate retrieval from the database

**Note**: The knowledge-graph retrieval part is currently left blank.

### 6. RAG Retrieval Tool (RAGTool)

**Responsibilities**:
- Retrieve expert data, including patent information and affiliated enterprise/organization information

### 7. Knowledge Graph Retrieval Tool (KGRetrieval)

**Responsibilities**:
- Retrieve path relations between entities in the knowledge graph
- Support Expert–Patent–Expert (co-author/collaborator) relationship retrieval
- Support Expert–Organization–Expert (colleague) relationship retrieval
- Convert retrieved paths into natural language descriptions

**Key Features**:
- Support specifying source and target entities to search paths
- Support filtering by relation types (e.g., `coauthor`, `colleague`)
- Automatically convert paths into natural language, e.g., “Expert A and Expert B jointly own patent P”

## Data Flow

```
Project requirements (loaded locally)
 ↓
 Recommendation Manager Agent: semantic parsing & profiling
 ↓
 Hybrid retrieval tool: preliminarily retrieve 20 candidate experts
 ↓
 Create 20 agent groups (Moderator + Project + Expert)
 ↓
 Moderator Agent: organize multi-round, multi-dimensional discussions
 ↓
 Collect discussion results
 ↓
 Recommendation Manager Agent: match evaluation & reranking
 ↓
 Recommendation Manager Agent: organize recommendation explanations
 ↓
 Recommendation Manager Agent: select top-k recommendations
 ↓
 Generate recommendation report (attribute matching + capability evaluation + path evidence + explanations)
```



## Installation & Usage

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Set the DashScope API Key (if using the DashScope service):

export DASHSCOPE_API_KEY=your_api_key_here

### 3. Prepare Data

Place project requirement data in `data/projects/` and expert data in `data/experts/`.

### 4. Run

```
python main.py
```

