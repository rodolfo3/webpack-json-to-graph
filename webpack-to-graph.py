from graphviz import Digraph
import collections
import json


MIN_SIZE_TO_INCLUDE = 1024 * 400  # 400kb


def sizeof_fmt(num):
    for unit in ['','K','M','G']:
        if abs(num) < 1024.0:
            return "%3.1f%s" % (num, unit)
        num /= 1024.0
    return "%.1f%s" % (num, 'T')


class WebpackJson:
    def __init__(self, webpack_json):
        self._data = webpack_json

        self._cache_list_all_dependencies = {}
        self._requirements_tree = self._build_requirements_tree()

    def _get_module_by_id(self, module_id):
        module_id = unicode(module_id)
        modules = self._data["modules"]
        [module] = [m for m in modules if unicode(m["id"]) == module_id]
        return module

    def _build_requirements_tree(self):
        modules = self._data["modules"]
        req = collections.defaultdict(list)
        for module in modules:
            for reason in module.get("reasons", []):
                 k = unicode(reason["moduleId"])
                 v = unicode(module["id"])
                 if k!=v:
                    req[k].append(v)
        return dict(req)

    def _list_all_dependencies(self, module_id, p=None):
        module_id = unicode(module_id)
        if module_id in self._cache_list_all_dependencies:
            return self._cache_list_all_dependencies[module_id]

        p = p or []  # handle circular dependencies
        if module_id in p:
            return []

        deps = self._requirements_tree.get(module_id, [])
        deps_dep = []

        for dep in deps:
            deps_dep += self._list_all_dependencies(dep, p + [module_id])

        self._cache_list_all_dependencies[module_id] = list(set(deps + deps_dep))
        return self._cache_list_all_dependencies[module_id]

    def _get_total_size(self, module_id):
        module_id = unicode(module_id)
        module = self._get_module_by_id(module_id)
        return module["size"] + sum(
            self._get_module_by_id(d)["size"]
            for d in self._list_all_dependencies(module_id)
        )

    def _should_output(self, module_id):
        return self._get_total_size(module_id) > MIN_SIZE_TO_INCLUDE

    def _build_module_name(self, module):
        return "{} ({}/{})".format(
            module["name"],
            sizeof_fmt(module["size"]),
            sizeof_fmt(self._get_total_size(module["id"]))
        )

    def _build_edges(self):
        edges = []
        modules = (
            module
            for module in self._data["modules"]
            if module.get("reasons") and self._should_output(module["id"])
        )

        for module in modules:
            for reason in module["reasons"]:
                edge = (
                    unicode(reason["moduleId"]),
                    unicode(module["id"])
                )
                edges.append(edge)

        return list(set(edges))

    def _build_nodes(self):
        modules = self._data["modules"]
        return [
            (unicode(module["id"]), self._build_module_name(module))
            for module in modules
            if self._should_output(module["id"])
        ]

    def build_dot(self):
        dot = Digraph()
        [dot.node(*n) for n in self._build_nodes()]
        [dot.edge(*e) for e in self._build_edges()]
        return dot


if __name__ == "__main__":
    import sys
    filename = sys.argv[1]

    wp = WebpackJson(json.load(open(filename)))
    dot = wp.build_dot()
    dot.render(filename.replace(".json", "") + ".gv")
