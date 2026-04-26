# utils/family_tree.py
import json
from typing import Dict, List, Optional, Any
from collections import defaultdict


class FamilyTreeGenerator:
    """Генератор структуры данных для семейного дерева"""

    def __init__(self, persons: Dict[str, Dict], family_name: str = ""):
        """
        Инициализация генератора

        Args:
            persons: Словарь с данными о родственниках
            family_name: Название семьи
        """
        self.persons = persons
        self.family_name = family_name
        self.tree_data = {
            "nodes": [],
            "links": [],
            "metadata": {
                "family_name": family_name,
                "total_persons": len(persons),
                "generated_at": None
            }
        }

    def generate_tree(self) -> Dict:
        """
        Генерация полной структуры для визуализации дерева

        Returns:
            Dict: Структура с узлами и связями для визуализации
        """
        from datetime import datetime

        nodes = []
        links = []
        processed_links = set()  # Для избежания дублирования связей

        # Создаём узлы для каждого человека
        for person_id, person in self.persons.items():
            node = self._create_node(person_id, person)
            nodes.append(node)

        # Создаём связи
        for person_id, person in self.persons.items():
            # Связи супругов
            for spouse_id in person.get("spouses", []):
                link_key = tuple(sorted([person_id, spouse_id]))
                if link_key not in processed_links:
                    links.append({
                        "source": person_id,
                        "target": spouse_id,
                        "type": "spouse",
                        "title": "Супруг(а)"
                    })
                    processed_links.add(link_key)

            # Связи детей (ребёнок -> родитель)
            for child_id in person.get("children", []):
                link_key = (child_id, person_id)
                if link_key not in processed_links:
                    links.append({
                        "source": child_id,
                        "target": person_id,
                        "type": "child",
                        "title": "Ребёнок"
                    })
                    processed_links.add(link_key)

        self.tree_data["nodes"] = nodes
        self.tree_data["links"] = links
        self.tree_data["metadata"]["generated_at"] = datetime.now().isoformat()

        return self.tree_data

    def _create_node(self, person_id: str, person: Dict) -> Dict:
        """Создание узла для одного человека"""
        # Определяем поколение (на основе родителей)
        generation = self._calculate_generation(person_id)

        # Форматируем даты для отображения
        birth_year = None
        death_year = None
        lifespan = ""

        if person.get("birth_date"):
            birth_year = person["birth_date"][:4]
            lifespan = birth_year
            if person.get("death_date"):
                death_year = person["death_date"][:4]
                lifespan += f" — {death_year}"
            else:
                lifespan += " — н.в."

        return {
            "id": person_id,
            "name": person.get("full_name", "Неизвестно"),
            "gender": person.get("gender", "male"),
            "status": person.get("status", "living"),
            "birth_date": person.get("birth_date"),
            "death_date": person.get("death_date"),
            "birth_year": birth_year,
            "death_year": death_year,
            "lifespan": lifespan,
            "age": person.get("age"),
            "birth_place": person.get("birth_place"),
            "death_place": person.get("death_place"),
            "biography": person.get("biography", ""),
            "generation": generation,
            "avatar": person.get("avatar"),
            "children_count": len(person.get("children", [])),
            "has_parents": len(person.get("parents", [])) > 0
        }

    def _calculate_generation(self, person_id: str, cache: Dict = None) -> int:
        """Расчёт поколения человека (рекурсивно через родителей)"""
        if cache is None:
            cache = {}

        if person_id in cache:
            return cache[person_id]

        person = self.persons.get(person_id, {})
        parents = person.get("parents", [])

        if not parents:
            generation = 0
        else:
            # Берём максимальное поколение среди родителей + 1
            parent_generations = []
            for parent_id in parents:
                if parent_id in self.persons:
                    parent_gen = self._calculate_generation(parent_id, cache)
                    parent_generations.append(parent_gen)

            if parent_generations:
                generation = max(parent_generations) + 1
            else:
                generation = 0

        cache[person_id] = generation
        return generation

    def get_roots(self) -> List[Dict]:
        """Получение корневых узлов (самых старших в роду)"""
        roots = []
        for person_id, person in self.persons.items():
            if not person.get("parents"):
                roots.append(self._create_node(person_id, person))
        return sorted(roots, key=lambda x: x.get("birth_year", "9999"))

    def get_tree_by_root(self, root_id: str) -> Dict:
        """Получение поддерева от указанного корня"""
        visited = set()

        def traverse(person_id):
            if person_id in visited:
                return None
            visited.add(person_id)

            person = self.persons.get(person_id, {})
            node = self._create_node(person_id, person)

            # Добавляем детей
            children = []
            for child_id in person.get("children", []):
                child_node = traverse(child_id)
                if child_node:
                    children.append(child_node)

            if children:
                node["children"] = children

            return node

        root_node = traverse(root_id)
        return root_node if root_node else {}

    def get_adjacency_list(self) -> Dict:
        """Получение списка смежности для графа"""
        adjacency = defaultdict(list)

        for person_id, person in self.persons.items():
            for spouse_id in person.get("spouses", []):
                if spouse_id not in adjacency[person_id]:
                    adjacency[person_id].append(spouse_id)

            for child_id in person.get("children", []):
                if child_id not in adjacency[person_id]:
                    adjacency[person_id].append(child_id)

            for parent_id in person.get("parents", []):
                if parent_id not in adjacency[person_id]:
                    adjacency[person_id].append(parent_id)

        return dict(adjacency)

    def export_to_json(self, filepath: str = None) -> str:
        """Экспорт дерева в JSON"""
        tree_data = self.generate_tree()
        json_str = json.dumps(tree_data, ensure_ascii=False, indent=2)

        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

    def export_for_visualization(self) -> Dict:
        """
        Экспорт данных для визуализации с использованием библиотек
        (например, для D3.js или ECharts)
        """
        tree = self.generate_tree()

        # Преобразуем в формат, удобный для визуализации
        return {
            "nodes": [
                {
                    "id": node["id"],
                    "name": node["name"],
                    "gender": node["gender"],
                    "lifespan": node["lifespan"],
                    "generation": node["generation"],
                    "symbolSize": 30 + (node["children_count"] * 2),
                    "category": 0 if node["gender"] == "male" else 1,
                    "itemStyle": {
                        "color": "#4eac60" if node["gender"] == "male" else "#f1c40f" if node[
                                                                                             "status"] == "living" else "#95a5a6"
                    }
                }
                for node in tree["nodes"]
            ],
            "links": tree["links"],
            "categories": [
                {"name": "Мужской", "itemStyle": {"color": "#4eac60"}},
                {"name": "Женский", "itemStyle": {"color": "#f1c40f"}}
            ]
        }


class TreeVisualizationHelper:
    """Класс для подготовки данных к различным визуализациям"""

    @staticmethod
    def format_for_chartjs(tree_data: Dict) -> Dict:
        """Форматирование для Chart.js"""
        nodes = tree_data.get("nodes", [])

        # Группировка по поколениям
        generations = {}
        for node in nodes:
            gen = node.get("generation", 0)
            if gen not in generations:
                generations[gen] = []
            generations[gen].append(node)

        return {
            "generations": generations,
            "total_count": len(nodes),
            "male_count": len([n for n in nodes if n.get("gender") == "male"]),
            "female_count": len([n for n in nodes if n.get("gender") == "female"]),
            "living_count": len([n for n in nodes if n.get("status") == "living"]),
            "deceased_count": len([n for n in nodes if n.get("status") == "deceased"])
        }

    @staticmethod
    def format_for_echarts(tree_data: Dict) -> Dict:
        """Форматирование для ECharts"""
        nodes = tree_data.get("nodes", [])
        links = tree_data.get("links", [])

        # Создаём карту для быстрого доступа
        node_map = {node["id"]: node for node in nodes}

        # Определяем уровни для иерархического расположения
        levels = {}
        for node in nodes:
            gen = node.get("generation", 0)
            if gen not in levels:
                levels[gen] = []
            levels[gen].append(node["id"])

        return {
            "nodes": nodes,
            "links": links,
            "levels": levels,
            "categories": [
                {"name": "Мужской", "itemStyle": {"color": "#4eac60"}},
                {"name": "Женский", "itemStyle": {"color": "#f1c40f"}}
            ]
        }

    @staticmethod
    def format_for_d3js(tree_data: Dict) -> Dict:
        """Форматирование для D3.js (иерархическая структура)"""
        # Находим корневые узлы
        roots = []
        node_map = {node["id"]: node for node in tree_data["nodes"]}

        # Находим всех, у кого нет родителей
        for node in tree_data["nodes"]:
            has_parent = False
            for link in tree_data["links"]:
                if link["target"] == node["id"] and link["type"] == "child":
                    has_parent = True
                    break
            if not has_parent:
                roots.append(node["id"])

        # Строим иерархию
        def build_hierarchy(node_id, visited=None):
            if visited is None:
                visited = set()
            if node_id in visited:
                return None
            visited.add(node_id)

            node = node_map.get(node_id, {})
            children = []

            # Находим всех детей
            for link in tree_data["links"]:
                if link["source"] == node_id and link["type"] == "child":
                    child = build_hierarchy(link["target"], visited)
                    if child:
                        children.append(child)

            return {
                "id": node_id,
                "name": node.get("name", ""),
                "gender": node.get("gender", ""),
                "lifespan": node.get("lifespan", ""),
                "generation": node.get("generation", 0),
                "children": children
            }

        hierarchy = []
        for root_id in roots:
            root_node = build_hierarchy(root_id)
            if root_node:
                hierarchy.append(root_node)

        return {"hierarchy": hierarchy, "roots_count": len(roots)}

    @staticmethod
    def generate_family_text(tree_generator: 'FamilyTreeGenerator') -> str:
        """Генерация текстового представления семейного дерева"""
        lines = []
        roots = tree_generator.get_roots()

        def print_tree(person_id: str, prefix: str = "", is_last: bool = True):
            person = tree_generator.persons.get(person_id, {})
            name = person.get("full_name", "Неизвестно")
            lifespan = ""
            if person.get("birth_date"):
                lifespan = f" ({person['birth_date'][:4]}"
                if person.get("death_date"):
                    lifespan += f"-{person['death_date'][:4]})"
                else:
                    lifespan += "-н.в.)"

            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}{lifespan}")

            # Рекурсивно выводим детей
            children = person.get("children", [])
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, child_id in enumerate(children):
                is_last_child = (i == len(children) - 1)
                print_tree(child_id, new_prefix, is_last_child)

        lines.append(f"🌳 Семейное дерево: {tree_generator.family_name}")
        lines.append("=" * 50)

        for i, root in enumerate(roots):
            is_last_root = (i == len(roots) - 1)
            root_prefix = "" if is_last_root else "│   "
            lines.append(f"📌 Родоначальник:")
            print_tree(root["id"], "", is_last_root)
            if not is_last_root:
                lines.append("│")

        return "\n".join(lines)