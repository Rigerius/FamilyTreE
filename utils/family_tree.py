# utils/family_tree.py
import json
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
from datetime import datetime


class FamilyTreeGenerator:
    """Генератор структуры данных для семейного дерева (исправленная версия)"""

    def __init__(self, persons: Dict[str, Dict], family_name: str = ""):
        self.persons = persons
        self.family_name = family_name
        self._tree_data = None

    @property
    def tree_data(self):
        if self._tree_data is None:
            self._tree_data = self._build_tree()
        return self._tree_data

    def _build_tree(self) -> Dict:
        generations = self._calculate_generations()
        nodes = []
        for pid, p in self.persons.items():
            node = self._create_node(pid, p, generations.get(pid, 0))
            nodes.append(node)

        links = []
        processed = set()
        # parent → child
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
            # spouse
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
        # корни: нет родителей или все родители вне данных
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

        # выравниваем супругов
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
        # дети строго ниже родителей
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
        node = {
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
        # Добавляем координаты, если есть
        pos = person.get("position")
        if pos and "x" in pos and "y" in pos:
            node["x"] = pos["x"]
            node["y"] = pos["y"]
        return node

    def to_visjs(self):
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

    # Старые методы оставлены для совместимости
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
