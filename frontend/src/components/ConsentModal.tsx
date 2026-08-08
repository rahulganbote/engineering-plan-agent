import React, { useState } from 'react';
import { X, ShieldAlert, FileText, Check } from 'lucide-react';

interface ConsentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAccept: () => void;
}

export default function ConsentModal({ isOpen, onClose, onAccept }: ConsentModalProps) {
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [confirmedAuthority, setConfirmedAuthority] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (agreedToTerms && confirmedAuthority) {
      onAccept();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-background/80 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="bg-card border border-border shadow-2xl rounded-2xl max-w-md w-full relative z-10 flex flex-col overflow-hidden animate-scale-in text-foreground">
        
        {/* Close Button */}
        <button 
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition p-1.5 rounded-lg hover:bg-secondary/80"
          aria-label="Close consent modal"
        >
          <X size={16} />
        </button>

        <form onSubmit={handleSubmit} className="flex flex-col">
          {/* Header */}
          <div className="px-6 pt-6 pb-4 border-b border-border/40 flex items-center gap-3 shrink-0">
            <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center">
              <FileText size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight">User Consent Required</h2>
              <p className="text-xs text-muted-foreground">Please review this sandbox terms & conditions</p>
            </div>
          </div>

          {/* Body */}
          <div className="p-6 space-y-4 text-xs sm:text-sm leading-relaxed">
            <div className="bg-warning/10 border border-warning/30 p-3 rounded-lg text-warning flex gap-2">
              <ShieldAlert size={18} className="shrink-0 mt-0.5" />
              <p className="text-xs">
                EM Copilot is a <strong>sandbox demonstration environment</strong>. Uploaded files flow through LLM model provider APIs (OpenAI/Anthropic/Llama).
              </p>
            </div>

            <p className="text-muted-foreground text-xs">
              Before your first upload, you must review and agree to the guidelines governing data uploads:
            </p>

            <div className="space-y-3 pt-2">
              {/* Checkbox 1: Terms & Privacy */}
              <label className="flex items-start gap-3 cursor-pointer group select-none">
                <input
                  type="checkbox"
                  checked={agreedToTerms}
                  onChange={(e) => setAgreedToTerms(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary focus:ring-offset-background bg-background shrink-0"
                />
                <span className="text-xs text-foreground group-hover:text-foreground/90 font-medium">
                  I agree to the{" "}
                  <a 
                    href="#/terms" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="text-primary hover:underline font-bold"
                  >
                    Terms of Service
                  </a>{" "}
                  and{" "}
                  <a 
                    href="#/privacy" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="text-primary hover:underline font-bold"
                  >
                    Privacy Policy
                  </a>.
                </span>
              </label>

              {/* Checkbox 2: Authority & PII Confirmation */}
              <label className="flex items-start gap-3 cursor-pointer group select-none">
                <input
                  type="checkbox"
                  checked={confirmedAuthority}
                  onChange={(e) => setConfirmedAuthority(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary focus:ring-offset-background bg-background shrink-0"
                />
                <span className="text-xs text-foreground group-hover:text-foreground/90 font-medium">
                  I confirm that I have the <strong>authority to upload</strong> this document, and that it contains no highly confidential business data, trade secrets, or unredacted customer PII.
                </span>
              </label>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="px-6 py-4 bg-secondary/20 border-t border-border/40 flex items-center justify-end gap-3 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-border text-muted-foreground hover:text-foreground rounded-lg font-bold text-xs hover:bg-secondary/40 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!agreedToTerms || !confirmedAuthority}
              className={`px-5 py-2 rounded-lg font-bold text-xs flex items-center gap-1.5 transition-all ${
                agreedToTerms && confirmedAuthority
                  ? 'bg-primary text-white hover:bg-primary/90 shadow-md cursor-pointer'
                  : 'bg-secondary/40 text-muted-foreground/60 border border-border/50 cursor-not-allowed shadow-none'
              }`}
            >
              <Check size={14} />
              Agree & Proceed
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
