/**
 * VoiceWidgetFAB - collapse-by-default wrapper for the ElevenLabs Conversational AI widget.
 *
 * Why this exists: the bare `<elevenlabs-convai>` widget renders an always-visible
 * pill button + "Powered by ElevenLabs" footer that competes with the workspace UI.
 * Recruiters/EMs viewing the demo shouldn't see the widget unless they intend to use it.
 *
 * Default state: small circular FAB (mic icon) at top-right of the viewport.
 * On click: mounts the widget inline; an × button collapses back to the FAB.
 *
 * Trade-off: the widget unmounts on collapse (simple, no zombie WebSocket). If a user
 * collapses mid-call, the call ends. Acceptable for the demo/HITL approval flow where
 * the typical session is single-shot.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Mic, X } from 'lucide-react';

interface VoiceWidgetFABProps {
  agentId: string;
  runId: string;
  voiceBrief: string;
  apiBaseUrl: string;
}

export const VoiceWidgetFAB: React.FC<VoiceWidgetFABProps> = ({
  agentId,
  runId,
  voiceBrief,
  apiBaseUrl,
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Click-outside to collapse - only while expanded
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div
      ref={containerRef}
      className="voice-widget-fab fixed top-3 right-44 z-50"
    >
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Start a voice call with the EM Copilot agent"
          title="Start a voice call"
          className="flex items-center justify-center w-11 h-11 rounded-full bg-gradient-to-br from-primary to-primary text-white shadow-lg hover:shadow-primary/40 hover:scale-105 transition-all duration-200 ring-2 ring-primary/30"
        >
          <Mic size={18} />
        </button>
      ) : (
        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close voice call widget"
            className="absolute -top-2 -right-2 z-10 w-6 h-6 rounded-full bg-secondary text-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center shadow-md ring-1 ring-ring"
          >
            <X size={12} />
          </button>
          <elevenlabs-convai
            agent-id={agentId}
            variant="compact"
            dynamic-variables={JSON.stringify({
              run_id: runId,
              api_base_url: apiBaseUrl,
              artifact_brief: voiceBrief,
              voice_brief: voiceBrief,
            })}
          />
        </div>
      )}
    </div>
  );
};
