import networkx as nx

class KnowledgeGraphManager:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        # Adding some core STEM concepts with prerequisite edges
        concepts = [
            "Force", "Mass", "Acceleration", "Velocity", "Newton's 1st Law",
            "Newton's 2nd Law", "Newton's 3rd Law", "Gravity", "Kinematics",
            "Energy", "Kinetic Energy", "Potential Energy", "Work"
        ]
        self.graph.add_nodes_from(concepts)
        
        edges = [
            ("Velocity", "Acceleration"),
            ("Mass", "Newton's 2nd Law"),
            ("Acceleration", "Newton's 2nd Law"),
            ("Force", "Newton's 2nd Law"),
            ("Force", "Newton's 3rd Law"),
            ("Mass", "Gravity"),
            ("Force", "Work"),
            ("Velocity", "Kinetic Energy"),
            ("Mass", "Kinetic Energy")
        ]
        self.graph.add_edges_from(edges)

    def get_prerequisites(self, concept):
        if concept in self.graph:
            return list(self.graph.predecessors(concept))
        return []

    def get_concept_map(self):
        """Returns the graph in a format suitable for React Flow"""
        nodes = [{"id": n, "data": {"label": n}, "position": {"x": 0, "y": 0}} for n in self.graph.nodes()]
        edges = [{"id": f"{u}-{v}", "source": u, "target": v} for u, v in self.graph.edges()]
        
        # Simple auto-layout mock
        x, y = 100, 100
        for node in nodes:
            node["position"] = {"x": x, "y": y}
            x += 200
            if x > 800:
                x = 100
                y += 100
                
        return {"nodes": nodes, "edges": edges}

kg_manager = KnowledgeGraphManager()
