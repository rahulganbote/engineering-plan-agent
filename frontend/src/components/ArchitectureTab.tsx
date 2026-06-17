import React from 'react';
import { AlertCircle, Layers, Activity } from 'lucide-react';
import { MermaidRenderer } from './MermaidRenderer';

interface Component {
  name: string;
  responsibility: string;
  technology: string;
  interfaces: string[];
}

interface NFRMapping {
  nfr: string;
  architecture_decision: string;
  citation: string;
}

interface ArchitectureOutput {
  pattern?: string;
  pattern_justification?: string;
  components?: Component[];
  data_flow?: string[];
  nfr_mappings?: NFRMapping[];
  deployment_model?: string;
  diagram_mermaid?: string | null;
  diagram_svg?: string | null;
}

interface ArchitectureTabProps {
  architectureData: unknown;
}

export const ArchitectureTab: React.FC<ArchitectureTabProps> = ({ architectureData }) => {
  let arch: ArchitectureOutput | null = null;
  if (architectureData) {
    if (typeof architectureData === 'string') {
      try {
        arch = JSON.parse(architectureData) as ArchitectureOutput;
      } catch {
        arch = null;
      }
    } else {
      arch = architectureData as ArchitectureOutput;
    }
  }

  if (!arch || (!arch.components && !arch.pattern)) {
    return (
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl text-center space-y-3">
        <AlertCircle className="mx-auto text-slate-500" size={32} />
        <h4 className="text-sm font-bold text-slate-300">Architecture Spec Unavailable</h4>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          The solution architecture structure could not be parsed. Below is the raw data:
        </p>
        <pre className="p-4 bg-slate-950 rounded text-left font-mono text-[10px] text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-60">
          {typeof architectureData === 'string' ? architectureData : JSON.stringify(architectureData, null, 2)}
        </pre>
      </div>
    );
  }

  // Gather unique citations for footnotes
  const citationsList = Array.from(
    new Set(
      (arch.nfr_mappings || [])
        .map((n) => n.citation)
        .filter((c): c is string => typeof c === 'string' && c.trim().length > 0)
    )
  );

  const getCitationIndex = (citation: string) => {
    return citationsList.indexOf(citation) + 1;
  };

  return (
    <div className="space-y-8 animate-fade-in text-slate-100">
      {/* Overview Block */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-950 border border-slate-850 p-6 rounded-xl shadow-inner">
        <div>
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Architectural Pattern</span>
          <span className="text-lg font-black text-indigo-400">{arch.pattern || '—'}</span>
        </div>
        <div>
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Deployment Target</span>
          <span className="text-lg font-black text-indigo-400">{arch.deployment_model || '—'}</span>
        </div>
        {arch.pattern_justification && (
          <div className="md:col-span-2 border-t border-slate-850 pt-4 mt-2">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Pattern Justification Rationale</span>
            <p className="text-xs text-slate-350 leading-relaxed">{arch.pattern_justification}</p>
          </div>
        )}
      </div>

      {/* Diagrams Renderer Canvas */}
      {(arch.diagram_svg || arch.diagram_mermaid) && (
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/60 pb-2">System Architecture Blueprint</h3>
          <MermaidRenderer diagramSvg={arch.diagram_svg} diagramMermaid={arch.diagram_mermaid} />

          {/* Mermaid source accordion intentionally hidden in Workspace per UX request.
              The source is still available via Sandbox > Architecture demo
              for design-mode / power-user inspection. */}
        </div>
      )}

      {/* Components List */}
      {arch.components && arch.components.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/60 pb-2">Component Specifications</h3>
          <div className="grid grid-cols-1 gap-4">
            {arch.components.map((comp, idx) => (
              <div key={idx} className="bg-slate-900 border border-slate-850 rounded-xl p-5 hover:border-slate-800 transition flex flex-col md:flex-row justify-between gap-4">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    <Layers size={14} className="text-indigo-400" />
                    <h4 className="text-sm font-bold text-slate-200">{comp.name}</h4>
                    <span className="text-[10px] bg-slate-950 text-indigo-400 border border-slate-850 px-2 py-0.5 rounded font-mono">
                      {comp.technology}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{comp.responsibility}</p>
                </div>
                {comp.interfaces && comp.interfaces.length > 0 && (
                  <div className="md:w-64 space-y-1.5 self-start">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block">Exposed Interfaces</span>
                    <div className="flex flex-wrap gap-1">
                      {comp.interfaces.map((intf, iIdx) => (
                        <span key={iIdx} className="bg-slate-950 text-slate-400 px-2 py-0.5 rounded text-[10px] border border-slate-900">
                          {intf}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Flow Pipeline */}
      {arch.data_flow && arch.data_flow.length > 0 && (
        <div className="space-y-4 border border-slate-850 rounded-xl p-5 bg-slate-900/40">
          <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-2">
            <Activity size={14} className="text-indigo-400" /> Core System Data Flow Steps
          </h4>
          <div className="flex flex-wrap items-center gap-2 pt-2">
            {arch.data_flow.map((flow, idx) => (
              <React.Fragment key={idx}>
                {idx > 0 && <span className="text-slate-600 font-bold text-xs">→</span>}
                <div className="flex items-center gap-1.5 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-200 shadow-sm">
                  <span className="h-2 w-2 rounded-full bg-indigo-500" />
                  <span>{flow}</span>
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* NFR Mappings Table */}
      {arch.nfr_mappings && arch.nfr_mappings.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/60 pb-2">🛡️ Non-Functional Requirements (NFR) Compliance</h3>
          <div className="overflow-x-auto rounded-xl border border-slate-850 bg-slate-900 shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-950 border-b border-slate-850 text-slate-400 font-semibold">
                  <th className="p-3 w-1/3">Non-Functional Requirement</th>
                  <th className="p-3">Architecture Compliance Design Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850 bg-slate-900/40">
                {arch.nfr_mappings.map((n, idx) => (
                  <tr key={idx} className="hover:bg-slate-850/20 text-slate-350">
                    <td className="p-3 font-semibold text-slate-200">{n.nfr}</td>
                    <td className="p-3 leading-relaxed">
                      {n.architecture_decision}
                      {n.citation && (
                        <a 
                          href={`#cite-${n.citation}`} 
                          className="text-[9px] text-indigo-400 hover:text-indigo-300 font-black align-super ml-0.5"
                          title={`Citation: ${n.citation}`}
                        >
                          [{getCitationIndex(n.citation)}]
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sources & Citations Glossar */}
      {citationsList.length > 0 && (
        <div className="border border-slate-850 rounded-xl p-5 bg-slate-950 shadow-inner">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-850 pb-2 mb-3">
            Sources & RAG Citations
          </h4>
          <ol className="list-decimal pl-5 space-y-2 text-xs text-slate-400">
            {citationsList.map((citation) => (
              <li key={citation} id={`cite-${citation}`} className="scroll-mt-24">
                <span className="font-mono text-slate-300 font-bold block">{citation}</span>
                <span className="text-[10px] text-slate-500 block mt-0.5">Retrieved from engineering knowledge store</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};
