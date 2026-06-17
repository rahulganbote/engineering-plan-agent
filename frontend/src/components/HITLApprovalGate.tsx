import React, { useState } from 'react';
import { Check, X, ThumbsUp, AlertCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useWorkspace } from '../context/WorkspaceContext';
import { apiFetch } from '../lib/apiClient';

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
  const { apiBaseUrl } = useWorkspace();
  const [reviewer, setReviewer] = useState('Engineering Manager');
  const [rating, setRating] = useState(4);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (decision: 'approved' | 'rejected') => {
    if (decision === 'rejected' && !notes.trim()) {
      toast.error("Please add notes explaining the reason for rejection.", {
        icon: <AlertCircle className="text-red-500" />
      });
      return;
    }

    setIsSubmitting(true);
    toast.info("Recording decision and exporting artifacts...", { duration: 1500 });
    
    try {
      const data = await apiFetch<ApprovalResponse>(`${apiBaseUrl}/approve/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          reviewer,
          notes,
          em_rating: rating,
        })
      });

      toast.success(`Pipeline successfully ${decision}!`, {
        icon: <ThumbsUp className="text-green-500" />
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
    <div id="decision-gate" className="max-w-3xl mx-auto p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-6 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Decision Gate</h3>
        <span className="px-2.5 py-1 rounded bg-amber-950/20 border border-amber-800/40 text-[10px] font-extrabold text-amber-400 uppercase tracking-wider">
          Awaiting Manager Action
        </span>
      </div>

      <div className="bg-indigo-950/20 border border-indigo-800/30 p-4 rounded text-xs text-indigo-300">
        Upon approval, the artifacts will be exported to Jira and this request is logged in EM Dashboard.
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div>
          <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Reviewer</label>
          <input 
            type="text" 
            value={reviewer} 
            onChange={(e) => setReviewer(e.target.value)}
            disabled={isSubmitting}
            className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-slate-100"
          />
        </div>
        <div>
          <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
            EM Rating (1 = unusable • 5 = excellent): <span className="font-extrabold text-indigo-400">{rating}</span>
          </label>
          <input 
            type="range" 
            min={1} 
            max={5} 
            value={rating} 
            onChange={(e) => setRating(Number(e.target.value))}
            disabled={isSubmitting}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500 mt-3.5"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
          Notes <span className="text-red-500">*Required if rejecting</span>
        </label>
        <textarea 
          placeholder="Provide context or feedback on output quality..." 
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isSubmitting}
          className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 outline-none h-20 text-slate-100"
        />
      </div>

      <div className="grid grid-cols-3 items-center pt-2">
        <div /> {/* Left spacer */}
        <div className="flex justify-center">
          <button
            onClick={() => handleSubmit('approved')}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-md transition flex items-center gap-2 text-xs font-bold"
          >
            <Check size={14} />
            Approve & Export
          </button>
        </div>
        <div className="flex justify-end">
          <button
            onClick={() => handleSubmit('rejected')}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg bg-slate-950 hover:bg-red-950/25 text-slate-300 hover:text-red-400 border border-slate-800 hover:border-red-900/30 transition flex items-center gap-2 text-xs font-bold"
          >
            <X size={14} />
            Reject Plan
          </button>
        </div>
      </div>

      {isSubmitting && (
        <div className="flex items-center gap-3 text-xs text-slate-400 justify-start pt-4 border-t border-slate-800/60 animate-pulse">
          <Loader2 className="animate-spin text-indigo-400 shrink-0" size={16} />
          <span>Recording decision · Pushing to Jira, writing to Google Sheets...</span>
        </div>
      )}
    </div>
  );
};
