from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import networkx as nx

from .pydantic_schema import DocumentGraph, Entity, Relationship

logger = logging.getLogger(__name__)


@dataclass
class MergedEntity:
    """
    全局图谱中的实体聚合表示。

    - 以 entity_id 为主键进行去重；
    - content 采取“语义合并”策略：
      - 若新内容与旧内容不同，保留较长版本，短版本可追加到 long_content_notes 中；
    - sources 用来记录该实体在不同文档中的 source_metadata，便于跨文档溯源。
    """

    entity_id: str
    entity_type: str
    name: str
    content: str
    sources: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_entity(cls, entity: Entity, source_metadata: Dict[str, Any]) -> "MergedEntity":
        return cls(
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            name=entity.name,
            content=entity.content,
            sources=[source_metadata] if source_metadata else [],
        )

    def merge_from(self, entity: Entity, source_metadata: Dict[str, Any]) -> None:
        """
        与新抽取的同 ID 实体进行合并。

        - 若 content 长度不同，保留较长的那一个；
        - sources 中追加新的 source_metadata（避免完全重复）。
        """
        # 内容合并：保留信息量更大的版本
        new_content = entity.content or ""
        if len(new_content) > len(self.content):
            self.content = new_content

        # 源信息合并：简单去重（基于 dict 比较）
        if source_metadata and source_metadata not in self.sources:
            self.sources.append(source_metadata)


class GraphBuilder:
    """
    负责将多个 DocumentGraph 合并为一个全局统一的知识网络。

    - 内部维护一个 networkx.MultiDiGraph 作为图论引擎；
    - 支持增量合并、去重与持久化；
    - 为“社会搜索”准备统计与导出能力。
    """

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        # 映射：entity_id -> MergedEntity
        self._entities: Dict[str, MergedEntity] = {}
        # 映射：(source_id, target_id, relation_type) -> 聚合 evidence 列表
        self._relationship_evidence: Dict[Tuple[str, str, str], List[str]] = {}

    # ---------------------------------------------------------------------
    # 增量合并逻辑
    # ---------------------------------------------------------------------

    def merge_document_graph(self, doc: DocumentGraph) -> None:
        """
        将单个 DocumentGraph 增量合并到全局图谱中。

        具备防御性：
        - 若 doc 为空或无实体/关系，安全返回；
        - 对实体与关系均做去重与内容合并。
        """
        if not doc or (not doc.entities and not doc.relationships):
            logger.info("merge_document_graph: received empty DocumentGraph; skip.")
            return

        source_meta = doc.source_metadata or {}

        # 1) 合并实体
        for entity in doc.entities:
            merged = self._entities.get(entity.entity_id)
            if merged is None:
                merged = MergedEntity.from_entity(entity, source_meta)
                self._entities[entity.entity_id] = merged

                # 在图中添加节点
                self.graph.add_node(
                    entity.entity_id,
                    entity_type=entity.entity_type,
                    name=entity.name,
                    content=entity.content,
                    sources=[source_meta] if source_meta else [],
                )
            else:
                # 已存在节点，执行内容与溯源合并
                merged.merge_from(entity, source_meta)
                # 同步更新图中的节点属性
                data = self.graph.nodes[entity.entity_id]
                data["content"] = merged.content
                data.setdefault("sources", [])
                if source_meta and source_meta not in data["sources"]:
                    data["sources"].append(source_meta)

        # 2) 合并关系
        for rel in doc.relationships:
            key = (rel.source_id, rel.target_id, rel.relation_type)

            # 聚合 evidence
            evidences = self._relationship_evidence.setdefault(key, [])
            if rel.evidence and rel.evidence not in evidences:
                evidences.append(rel.evidence)

            # 在图中添加/更新边（MultiDiGraph 允许多条边，但我们在属性层做去重）
            self.graph.add_edge(
                rel.source_id,
                rel.target_id,
                relation_type=rel.relation_type,
                evidences=list(evidences),
            )

    def merge_many(self, docs: Iterable[DocumentGraph]) -> None:
        """
        批量合并多个 DocumentGraph。
        """
        for doc in docs:
            self.merge_document_graph(doc)

    # ---------------------------------------------------------------------
    # 导出 / 持久化
    # ---------------------------------------------------------------------

    def to_json_dict(self) -> Dict[str, Any]:
        """
        将当前全局图谱导出为标准 JSON 友好的 dict 结构，便于持久化或下游消费。

        结构大致为：
        {
          "entities": [...],
          "relationships": [...]
        }
        """
        entities_payload: List[Dict[str, Any]] = []
        for entity_id, merged in self._entities.items():
            node_data = self.graph.nodes.get(entity_id, {})
            entities_payload.append(
                {
                    "entity_id": merged.entity_id,
                    "entity_type": merged.entity_type,
                    "name": merged.name,
                    "content": merged.content,
                    "sources": list(node_data.get("sources", merged.sources)),
                }
            )

        relationships_payload: List[Dict[str, Any]] = []
        for (src, tgt, rel_type), evidences in self._relationship_evidence.items():
            relationships_payload.append(
                {
                    "source_id": src,
                    "target_id": tgt,
                    "relation_type": rel_type,
                    "evidences": list(evidences),
                }
            )

        return {
            "entities": entities_payload,
            "relationships": relationships_payload,
        }

    def save_json(self, path: str | Path) -> None:
        """
        将当前全局图谱保存为 JSON 文件（UTF-8，ensure_ascii=False，避免中文乱码）。
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        data = self.to_json_dict()
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("GraphBuilder state saved to JSON: %s", p)

    def save_graphml(self, path: str | Path) -> None:
        """
        将当前 MultiDiGraph 导出为 GraphML，用于 Gephi 等工具可视化。
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # networkx 的 write_graphml 默认就是 UTF-8 编码
        nx.write_graphml(self.graph, p)
        logger.info("GraphBuilder graph saved to GraphML: %s", p)

    @classmethod
    def load_json(cls, path: str | Path) -> "GraphBuilder":
        """
        从 JSON 文件中恢复 GraphBuilder 状态，用于断点续传。

        若文件不存在或数据格式异常，则返回一个空的 GraphBuilder。
        """
        p = Path(path)
        builder = cls()

        if not p.exists():
            logger.warning("load_json: file not found, return empty GraphBuilder: %s", p)
            return builder

        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:  # noqa: BLE001
            logger.warning("load_json: failed to read JSON, return empty builder: %s", exc, exc_info=True)
            return builder

        entities = data.get("entities") or []
        relationships = data.get("relationships") or []

        # 恢复实体
        for item in entities:
            try:
                entity_id = item["entity_id"]
                merged = MergedEntity(
                    entity_id=entity_id,
                    entity_type=item.get("entity_type", ""),
                    name=item.get("name", ""),
                    content=item.get("content", ""),
                    sources=item.get("sources", []) or [],
                )
                builder._entities[entity_id] = merged

                builder.graph.add_node(
                    entity_id,
                    entity_type=merged.entity_type,
                    name=merged.name,
                    content=merged.content,
                    sources=list(merged.sources),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("load_json: skip invalid entity entry: %s", exc, exc_info=True)

        # 恢复关系
        for item in relationships:
            try:
                src = item["source_id"]
                tgt = item["target_id"]
                rel_type = item["relation_type"]
                evidences = item.get("evidences", []) or []

                key = (src, tgt, rel_type)
                builder._relationship_evidence[key] = list(evidences)

                builder.graph.add_edge(
                    src,
                    tgt,
                    relation_type=rel_type,
                    evidences=list(evidences),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("load_json: skip invalid relationship entry: %s", exc, exc_info=True)

        logger.info(
            "GraphBuilder state loaded from %s: %d entities, %d relationships",
            p,
            len(builder._entities),
            len(builder._relationship_evidence),
        )
        return builder

    # ---------------------------------------------------------------------
    # 社会搜索准备：统计与剪枝辅助
    # ---------------------------------------------------------------------

    def stats_report(self) -> Dict[str, Any]:
        """
        生成当前图谱的“密度”报告。

        返回结构示例：
        {
          "num_entities": 123,
          "num_relationships": 456,
          "num_weakly_connected_components": 7,
          "top_hub_entities": [
            {
              "entity_id": "UI_Component:Button",
              "degree": 42
            },
            ...
          ]
        }
        """
        num_entities = self.graph.number_of_nodes()
        num_relationships = self.graph.number_of_edges()

        if num_entities == 0:
            return {
                "num_entities": 0,
                "num_relationships": 0,
                "num_weakly_connected_components": 0,
                "top_hub_entities": [],
            }

        # 使用弱连通分量统计“孤立社区”数量
        undirected_view = self.graph.to_undirected(as_view=True)
        num_components = nx.number_connected_components(undirected_view)

        # 连接度最高的 Top 10 实体（基于总度数：入度+出度）
        degree_view = self.graph.degree()
        top_hubs = sorted(degree_view, key=lambda x: x[1], reverse=True)[:10]
        top_hub_entities = [
            {
                "entity_id": node_id,
                "degree": int(deg),
                "entity_type": self.graph.nodes[node_id].get("entity_type", ""),
                "name": self.graph.nodes[node_id].get("name", ""),
            }
            for node_id, deg in top_hubs
        ]

        return {
            "num_entities": int(num_entities),
            "num_relationships": int(num_relationships),
            "num_weakly_connected_components": int(num_components),
            "top_hub_entities": top_hub_entities,
        }


__all__ = ["MergedEntity", "GraphBuilder"]

