import React, { useState, useEffect } from 'react';
import { ReactFlow, Background, Controls, Edge, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network } from 'lucide-react';

const initialNodes: Node[] = [
  { id: 'Force', position: { x: 250, y: 50 }, data: { label: 'Force' }, style: { background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px' } },
  { id: 'Mass', position: { x: 50, y: 50 }, data: { label: 'Mass' }, style: { background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px' } },
  { id: 'Newton\'s 2nd Law', position: { x: 150, y: 150 }, data: { label: 'Newton\'s 2nd Law' }, style: { background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px' } },
  { id: 'Newton\'s 3rd Law', position: { x: 350, y: 150 }, data: { label: 'Newton\'s 3rd Law' }, style: { background: '#1f2937', color: '#fff', border: '1px solid #374151', borderRadius: '8px', padding: '10px' } },
];

const initialEdges: Edge[] = [
  { id: 'e-mass-n2', source: 'Mass', target: 'Newton\'s 2nd Law', animated: true },
  { id: 'e-force-n2', source: 'Force', target: 'Newton\'s 2nd Law', animated: true },
  { id: 'e-force-n3', source: 'Force', target: 'Newton\'s 3rd Law', animated: true },
];

export default function KnowledgeMap({ unlockedNode }: { unlockedNode?: string }) {
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);

  useEffect(() => {
    if (unlockedNode) {
      setNodes((nds) =>
        nds.map((n) => {
          if (unlockedNode.includes(n.id)) {
            return {
              ...n,
              style: { ...n.style, background: '#10b981', border: 'none' },
            };
          }
          return n;
        })
      );
    }
  }, [unlockedNode]);

  return (
    <div className="w-full h-[300px] bg-[#070714] rounded-xl border border-white/5 overflow-hidden relative">
      <div className="absolute top-3 left-4 z-10 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
          <Network className="w-4 h-4 text-emerald-400" />
        </div>
        <span className="text-gray-300 font-semibold text-sm">Knowledge Map</span>
      </div>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="#374151" gap={16} />
        <Controls className="bg-gray-900 border-white/10 fill-white" />
      </ReactFlow>
    </div>
  );
}
