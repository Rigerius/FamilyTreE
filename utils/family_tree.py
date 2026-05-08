import json
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque


class FamilyTreeGenerator:

    def __init__(self, persons: Dict[str, Dict], family_name: str = ""):
        self.persons = persons
        self.family_name = family_name
        self._tree_data = None

    @property
    def tree_data(self):
        """Ленивая генерация и кэширование"""
        if self._tree_data is None:
            self._tree_data = self._build_tree()
        return self._tree_data

    def _build_tree(self) -> Dict:
        from datetime import datetime
        generations = self._calculate_generations()
        nodes = []
        for pid, p in self.persons.items():
            node = self._create_node(pid, p, generations.get(pid, 0))
            nodes.append(node)

        links = []
        processed = set()
        for pid, p in self.persons.items():
            for child_id in p.get("children", []):
                if child_id in self.persons:
                    link_key = (pid, child_id)
                    if link_key not in processed:
                        links.append({
                            "source": pid, "target": child_id,
                            "type": "child", "title": "Ребёнок"
                        })
                        processed.add(link_key)
            for spouse_id in p.get("spouses", []):
                if spouse_id in self.persons:
                    link_key = tuple(sorted([pid, spouse_id]))
                    if link_key not in processed:
                        links.append({
                            "source": pid, "target": spouse_id,
                            "type": "spouse", "title": "Супруг(а)"
                        })
                        processed.add(link_key)

        return {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "family_name": self.family_name,
                "total_persons": len(self.persons),
                "generated_at": datetime.now().isoformat()
            }
        }

    def _calculate_generations(self) -> Dict[str, int]:
        gens = {}
        roots = [pid for pid, p in self.persons.items()
                 if not p.get("parents") or all(par not in self.persons for par in p["parents"])]
        q = deque(roots)
        for r in roots:
            gens[r] = 0
        while q:
            cur = q.popleft()
            cur_gen = gens[cur]
            for child_id in self.persons[cur].get("children", []):
                if child_id in self.persons and child_id not in gens:
                    gens[child_id] = cur_gen + 1
                    q.append(child_id)
        for pid in self.persons:
            if pid not in gens:
                gens[pid] = 0

        changed = True
        while changed:
            changed = False
            for pid, p in self.persons.items():
                for sp_id in p.get("spouses", []):
                    if sp_id in self.persons:
                        max_gen = max(gens.get(pid, 0), gens.get(sp_id, 0))
                        if gens.get(pid) != max_gen or gens.get(sp_id) != max_gen:
                            gens[pid] = max_gen
                            gens[sp_id] = max_gen
                            changed = True
        for pid, p in self.persons.items():
            for child_id in p.get("children", []):
                if child_id in gens and gens[child_id] <= gens[pid]:
                    gens[child_id] = gens[pid] + 1
        return gens

    def _create_node(self, person_id: str, person: Dict, generation: int) -> Dict:
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
        else:
            lifespan = "дата неизв."
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
            "birth_place": person.get("birth_place"),
            "death_place": person.get("death_place"),
            "biography": person.get("biography", ""),
            "generation": generation,
            "avatar": person.get("avatar"),
            "children_count": len(person.get("children", [])),
            "has_parents": len(person.get("parents", [])) > 0,
            "parents": person.get("parents", []),
            "spouses": person.get("spouses", []),
            "children": person.get("children", []),
        }

    def to_visjs(self):
        """Возвращает данные в формате, готовом для vis‑network"""
        tree = self.tree_data
        return {
            "nodes": tree["nodes"],
            "edges": tree["links"],
        }

    def export_to_json(self, filepath=None):
        json_str = json.dumps(self.to_visjs(), ensure_ascii=False, indent=2)
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)
        return json_str

    def get_roots(self) -> List[Dict]:
        roots = []
        for pid, p in self.persons.items():
            if not p.get("parents") or all(parent not in self.persons for parent in p["parents"]):
                roots.append(self._create_node(pid, p, 0))
        return sorted(roots, key=lambda x: x.get("birth_year") or "9999")

    def get_adjacency_list(self) -> Dict:
        adj = defaultdict(list)
        for pid, p in self.persons.items():
            for s in p.get("spouses", []):
                if s in self.persons: adj[pid].append(s)
            for c in p.get("children", []):
                if c in self.persons: adj[pid].append(c)
            for parent in p.get("parents", []):
                if parent in self.persons: adj[pid].append(parent)
        return dict(adj)


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