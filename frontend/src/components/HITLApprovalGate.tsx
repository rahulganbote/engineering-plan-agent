import React, { useState } from 'react';
import { Check, X, ThumbsUp, AlertCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useWorkspace } from '../context/WorkspaceContext';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../lib/apiClient';
import { IntegrationNotConfigured } from './IntegrationNotConfigured';

export interface ApprovalResponse {
  run_id: string;
  decision: 'approved' | 'rejected';
  message: string;
  sheet_url?: string;
  export_status?: string;
  export_mode?: string;
  export_detail?: string;
  jira_url?: string;
  jira_status?: string;
  jira_detail?: string;
  jira_issue_key?: string;
  pipeline_status: string;
  rejection_count: number;
}

interface HITLApprovalGateProps {
  runId: string;
  onDecisionSubmitted?: (data: ApprovalResponse) => void;
}

export const HITLApprovalGate: React.FC<HITLApprovalGateProps> = ({ runId, onDecisionSubmitted }) => {
  const { apiBaseUrl, elevenlabsAgentId } = useWorkspace();
  const { user } = useAuth();
  const [reviewer, setReviewer] = useState('Engineering Manager');
  const [rating, setRating] = useState(4);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [submittingDecision, setSubmittingDecision] = useState<'approved' | 'rejected' | null>(null);

  const handleSubmit = async (decision: 'approved' | 'rejected') => {
    if (decision === 'rejected' && !notes.trim()) {
      toast.error("Please add notes explaining the reason for rejection.", {
        icon: <AlertCircle className="text-danger" />
      });
      return;
    }

    setSubmittingDecision(decision);
    setIsSubmitting(true);
    toast.info("Recording decision...", { duration: 1500 });
    
    try {
      const data = await apiFetch<ApprovalResponse>(`${apiBaseUrl}/approve/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          reviewer,
          notes,
          em_rating: rating,
          email: user?.email || '',
        })
      });

      setHasSubmitted(true);
      toast.success(`The Plan is successfully ${decision}!`, {
        icon: <ThumbsUp className="text-success" />
      });
      if (onDecisionSubmitted) {
        onDecisionSubmitted(data);
      }
    } catch (error) {
      console.error("Failed to submit decision:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div id="decision-gate" className="max-w-3xl mx-auto p-6 bg-card border border-border rounded-xl space-y-6 shadow-xl">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <h3 className="text-xs font-black text-primary uppercase tracking-wider">Decision Gate</h3>
        <span className="px-2.5 py-1 rounded bg-warning/20 border border-warning/40 text-[10px] font-extrabold text-warning uppercase tracking-wider">
          Awaiting Manager Action
        </span>
      </div>

      <div className="bg-primary/10 border border-primary/30 p-4 rounded text-xs text-primary">
        Upon approval, the artifacts will be exported to Jira and this request is logged in EM Dashboard.
      </div>

      {/* Voice approval fallback hint - shown when ElevenLabs is not configured on
          this deployment. Without this, EMs wouldn't know that voice approval is
          an intended feature; they'd just see no voice button and assume the
          system only supports click-approval. */}
      {!elevenlabsAgentId && (
        <IntegrationNotConfigured
          title="Voice approval not available"
          envVars={["ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID"]}
          description="The voice-based HITL approval flow (powered by ElevenLabs Conversational AI) is not configured on this deployment. Use the Approve & Export / Reject Plan buttons below."
          docsAnchor="#L68-L70"
        />
      )}



      <div className="grid grid-cols-2 gap-6">
        <div>
          <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">Reviewer</label>
          <input 
            type="text" 
            value={reviewer} 
            onChange={(e) => setReviewer(e.target.value)}
            disabled={isSubmitting || hasSubmitted}
            className="w-full bg-background border border-border px-3 py-2 rounded text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none text-foreground font-medium placeholder:text-muted-foreground/50"
          />
        </div>
        <div>
          <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
            EM Rating (1 = unusable • 5 = excellent): <span className="font-extrabold text-primary">{rating}</span>
          </label>
          <input 
            type="range" 
            min={1} 
            max={5} 
            value={rating} 
            onChange={(e) => setRating(Number(e.target.value))}
            disabled={isSubmitting || hasSubmitted}
            className="w-full h-1.5 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary mt-3.5"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
          Notes <span className="text-danger">*Required if rejecting</span>
        </label>
        <textarea 
          placeholder="Provide context or feedback on output quality..." 
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isSubmitting || hasSubmitted}
          className="w-full bg-background border border-border px-3 py-2 rounded text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none h-20 text-foreground placeholder:text-muted-foreground/50"
        />
      </div>

      <div className="flex justify-between items-center pt-2 w-full">
        <div>
          <button
            onClick={() => handleSubmit('rejected')}
            disabled={isSubmitting || hasSubmitted}
            className="px-4 py-2 rounded-lg bg-danger/10 hover:bg-danger/20 text-danger border border-danger/30 transition flex items-center gap-2 text-xs font-bold"
          >
            <X size={14} />
            Reject Plan
          </button>
        </div>
        <div>
          <button
            onClick={() => handleSubmit('approved')}
            disabled={isSubmitting || hasSubmitted}
            className="px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-white shadow-md hover:shadow-primary/30 transition flex items-center gap-2 text-xs font-bold disabled:opacity-50"
          >
            {isSubmitting && submittingDecision === 'approved' ? (
              <Loader2 className="animate-spin" size={14} />
            ) : (
              <Check size={14} />
            )}
            {isSubmitting && submittingDecision === 'approved' ? 'Exporting & Pushing to Jira...' : 'Approve & Export'}
          </button>
        </div>
      </div>

      {isSubmitting && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground justify-start pt-4 border-t border-border/60 animate-pulse">
          <Loader2 className="animate-spin text-primary shrink-0" size={16} />
          {submittingDecision === 'rejected' ? (
            <span>Recording rejection · Writing audit log to Google Sheets...</span>
          ) : (
            <span>Recording approval · Pushing to Jira, writing to Google Sheets...</span>
          )}
        </div>
      )}
    </div>
  );
};
