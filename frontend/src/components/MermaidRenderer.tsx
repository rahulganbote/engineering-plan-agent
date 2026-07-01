import React, { useEffect, useState, useRef } from 'react';
import mermaid from 'mermaid';
import { AlertCircle } from 'lucide-react';

interface MermaidRendererProps {
  diagramSvg?: string | null;
  diagramMermaid?: string | null;
}

export const MermaidRenderer: React.FC<MermaidRendererProps> = ({ diagramSvg, diagramMermaid }) => {
  const [renderedSvg, setRenderedSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (diagramSvg) {
      Promise.resolve().then(() => {
        setRenderedSvg(diagramSvg);
        setError(null);
      });
      return;
    }

    if (!diagramMermaid) {
      Promise.resolve().then(() => {
        setRenderedSvg(null);
        setError(null);
      });
      return;
    }

    const renderChart = async () => {
      try {
        // Initialize mermaid with appropriate theme and variables matching dark slate dashboard
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          securityLevel: 'loose',
          themeVariables: {
            background: '#090d16',
            primaryColor: '#6366f1',
            lineColor: '#334155',
          }
        });

        const id = `mermaid-svg-${Math.floor(Math.random() * 100000)}`;
        const { svg } = await mermaid.render(id, diagramMermaid);
        setRenderedSvg(svg);
        setError(null);
      } catch (e: unknown) {
        console.error("Mermaid client-side render error:", e);
        const errMsg = e instanceof Error ? e.message : String(e);
        setError(errMsg);
      }
    };

    renderChart();
  }, [diagramSvg, diagramMermaid]);

  if (error) {
    return (
      <div className="p-4 bg-danger/20 border border-danger/30 text-danger rounded-lg text-xs space-y-2">
        <div className="flex items-center gap-2 font-bold text-danger">
          <AlertCircle size={16} />
          <span>Mermaid client-side render failed</span>
        </div>
        <p className="text-[11px] text-danger font-mono">
          {error}
        </p>
        <p className="text-[10px] text-muted-foreground italic">
          You can still copy and run the source code below in any Mermaid-aware editor.
        </p>
      </div>
    );
  }

  if (!renderedSvg) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-xs">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mb-3" />
        <span>Generating diagram...</span>
      </div>
    );
  }

  return (
    <div className="w-full">
      <style>{`
        .mermaid-container svg {
          max-width: 100% !important;
          height: auto !important;
        }
        /* Override Kroki/Mermaid dark/light connector lines for dark mode compatibility */
        .mermaid-container svg path.path,
        .mermaid-container svg .edgePath .path,
        .mermaid-container svg .edgePaths path,
        .mermaid-container svg .transition path,
        .mermaid-container svg g.edgePaths path,
        .mermaid-container svg g.edgePaths .path {
          stroke: #94a3b8 !important; /* Tailwind slate-400 */
          stroke-width: 1.5px !important;
        }
        .mermaid-container svg marker path,
        .mermaid-container svg .marker path,
        .mermaid-container svg path.arrowheadPath,
        .mermaid-container svg marker .arrowheadPath,
        .mermaid-container svg .arrowheadPath {
          fill: #94a3b8 !important;
          stroke: #94a3b8 !important;
        }
        /* Override labels on connector lines if any */
        .mermaid-container svg .edgeLabel rect {
          fill: #090d16 !important; /* Matches background */
        }
        .mermaid-container svg .edgeLabel span {
          color: #cbd5e1 !important; /* Tailwind slate-300 */
        }
      `}</style>
      <div 
        ref={containerRef}
        className="mermaid-container w-full overflow-x-auto p-4 bg-background rounded-lg border border-border flex justify-center [&>svg]:max-w-full [&>svg]:h-auto text-foreground"
        dangerouslySetInnerHTML={{ __html: renderedSvg }}
      />
    </div>
  );
};
