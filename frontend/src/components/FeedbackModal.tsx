import React, { useState, useEffect } from 'react';
import { X, Check, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  runId?: string | null;
  apiBaseUrl: string;
}

export default function FeedbackModal({ isOpen, onClose, runId, apiBaseUrl }: FeedbackModalProps) {
  const { user, isAuthenticated } = useAuth();
  
  // Form state
  const [area, setArea] = useState('');
  const [category, setCategory] = useState('bug'); // bug, performance, feature_request
  const [description, setDescription] = useState('');
  const [includeTranscript, setIncludeTranscript] = useState(true);
  const [isAnonymous, setIsAnonymous] = useState(false);
  
  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [showLogsDetails, setShowLogsDetails] = useState(false);
  const [validationError, setValidationError] = useState('');

  // Diagnostic logs payload
  const [diagnosticInfo, setDiagnosticInfo] = useState({
    os: 'Unknown OS',
    browser: 'Unknown Browser',
    userAgent: '',
    language: '',
    screenResolution: '',
    version: '1.1.0',
    timestamp: ''
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const ua = navigator.userAgent;
      let os = 'Unknown OS';
      if (ua.indexOf('Mac') !== -1) os = 'macOS';
      else if (ua.indexOf('Win') !== -1) os = 'Windows';
      else if (ua.indexOf('Linux') !== -1) os = 'Linux';
      else if (ua.indexOf('Android') !== -1) os = 'Android';
      else if (ua.indexOf('like Mac') !== -1) os = 'iOS';

      let browser = 'Unknown Browser';
      if (ua.indexOf('Chrome') !== -1) browser = 'Chrome';
      else if (ua.indexOf('Safari') !== -1) browser = 'Safari';
      else if (ua.indexOf('Firefox') !== -1) browser = 'Firefox';
      else if (ua.indexOf('MSIE') !== -1 || !!(document as any).documentMode) browser = 'IE';

      setDiagnosticInfo({
        os,
        browser,
        userAgent: ua,
        language: navigator.language || '',
        screenResolution: `${window.screen.width}x${window.screen.height}`,
        version: '1.1.0',
        timestamp: new Date().toISOString()
      });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError('');

    if (!area) {
      setValidationError('Please select an area.');
      return;
    }
    if (!description.trim()) {
      setValidationError('Please enter a description of your feedback.');
      return;
    }

    setIsSubmitting(true);
    setSubmitStatus('idle');

    const sender = (isAuthenticated && user?.email && !isAnonymous) ? user.email : 'Anonymous';

    const payload = {
      area,
      category,
      description,
      include_transcript: includeTranscript,
      workspace: 'EM-Copilot Development',
      diagnostic_logs: diagnosticInfo,
      sender,
      run_id: runId || null
    };

    try {
      const response = await fetch(`${apiBaseUrl}/api/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        setSubmitStatus('success');
        // Reset form
        setArea('');
        setCategory('bug');
        setDescription('');
        setIncludeTranscript(true);
        setIsAnonymous(false);
      } else {
        setSubmitStatus('error');
      }
    } catch (err) {
      console.error('Error submitting feedback:', err);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
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
      <div className="bg-card border border-border shadow-2xl rounded-2xl max-w-lg w-full relative z-10 flex flex-col max-h-[90vh] overflow-hidden animate-scale-in text-foreground">
        
        {/* Close Button */}
        <button 
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition p-1.5 rounded-lg hover:bg-secondary/80"
          aria-label="Close feedback modal"
        >
          <X size={16} />
        </button>

        {submitStatus === 'success' ? (
          <div className="p-8 text-center flex flex-col items-center justify-center space-y-4">
            <div className="h-12 w-12 rounded-full bg-success/20 text-success flex items-center justify-center animate-bounce">
              <Check size={24} />
            </div>
            <h2 className="text-xl font-bold">Feedback Submitted!</h2>
            <p className="text-sm text-muted-foreground max-w-sm">
              Thank you for helping us improve EM Copilot. Your feedback and diagnostics have been successfully delivered.
            </p>
            <button
              onClick={() => {
                setSubmitStatus('idle');
                onClose();
              }}
              className="mt-4 px-6 py-2 bg-primary text-white rounded-lg font-bold text-xs hover:bg-primary/90 transition shadow-md"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col overflow-hidden">
            
            {/* Header */}
            <div className="px-6 pt-6 pb-4 border-b border-border/40 shrink-0">
              <h2 className="text-lg sm:text-xl font-bold tracking-tight">Give feedback about EM Copilot</h2>
            </div>

            {/* Scrollable Body */}
            <div className="p-6 space-y-5 overflow-y-auto flex-1 text-sm leading-relaxed">
              
              {validationError && (
                <div className="p-3 text-xs bg-danger/10 border border-danger/30 text-danger rounded-lg font-semibold">
                  ⚠️ {validationError}
                </div>
              )}

              {submitStatus === 'error' && (
                <div className="p-3 text-xs bg-danger/10 border border-danger/30 text-danger rounded-lg font-semibold">
                  ❌ Failed to submit feedback. Please try again.
                </div>
              )}

              {/* Area Select */}
              <div className="space-y-1.5">
                <label className="block font-bold text-muted-foreground text-xs uppercase tracking-wider">What's this about?</label>
                <div className="relative">
                  <select
                    value={area}
                    onChange={(e) => setArea(e.target.value)}
                    className="w-full bg-background border border-border hover:border-muted-foreground/40 rounded-lg px-3 py-2.5 outline-none focus:ring-1 focus:ring-primary focus:border-primary appearance-none cursor-pointer font-medium"
                  >
                    <option value="" disabled>Choose an area...</option>
                    <option value="Ingestion / Upload">Ingestion / Upload</option>
                    <option value="Plan Generation">Plan Generation</option>
                    <option value="Schedule / Estimates">Schedule / Estimates</option>
                    <option value="Tech Stack recommendations">Tech Stack recommendations</option>
                    <option value="System Design / Architecture">System Design / Architecture</option>
                    <option value="User Interface / Visuals">User Interface / Visuals</option>
                    <option value="Other">Other</option>
                  </select>
                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground">
                    <ChevronDown size={14} />
                  </div>
                </div>
              </div>

              {/* Category Pills */}
              <div className="flex gap-2">
                {['bug', 'performance', 'feature_request'].map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setCategory(cat)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
                      category === cat
                        ? 'bg-primary/10 text-primary border-primary/30 shadow-sm'
                        : 'bg-secondary/40 text-muted-foreground border-transparent hover:bg-secondary/80'
                    }`}
                  >
                    {cat === 'bug' && 'Bug'}
                    {cat === 'performance' && 'Performance'}
                    {cat === 'feature_request' && 'Feature request'}
                  </button>
                ))}
              </div>

              {/* Textarea Description */}
              <div className="space-y-1.5">
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What did you expect, and what happened instead?"
                  rows={4}
                  className="w-full bg-background border border-border hover:border-muted-foreground/40 rounded-lg p-3 outline-none focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/60 resize-none font-normal"
                />
              </div>

              {/* Sender Identity Info */}
              {isAuthenticated && user?.email ? (
                <div className="flex items-center justify-between bg-secondary/20 border border-border/40 rounded-lg p-3 text-xs">
                  <span className="font-semibold text-muted-foreground">
                    Sending as: <span className="text-foreground">{user.email}</span>
                  </span>
                  <label className="flex items-center gap-1.5 cursor-pointer font-semibold text-muted-foreground select-none">
                    <input
                      type="checkbox"
                      checked={isAnonymous}
                      onChange={(e) => setIsAnonymous(e.target.checked)}
                      className="rounded border-border bg-background text-primary focus:ring-primary h-3.5 w-3.5 cursor-pointer"
                    />
                    Send anonymously
                  </label>
                </div>
              ) : (
                <div className="bg-secondary/20 border border-border/40 rounded-lg p-3 text-xs font-semibold text-muted-foreground">
                  Sending as: <span className="text-foreground">Anonymous</span>
                </div>
              )}

              {/* Transcript Checkbox */}
              <div className="flex items-center gap-3 bg-secondary/10 border border-border/20 rounded-lg p-3 text-xs">
                <label className="flex items-center gap-1.5 cursor-pointer font-semibold text-muted-foreground select-none">
                  <input
                    type="checkbox"
                    checked={includeTranscript}
                    onChange={(e) => setIncludeTranscript(e.target.checked)}
                    className="rounded border-border bg-background text-primary focus:ring-primary h-3.5 w-3.5 cursor-pointer"
                  />
                  <span>Include <span className="underline decoration-dotted underline-offset-2">task transcript</span></span>
                </label>
                <div className="flex-1 relative max-w-[200px]">
                  <select
                    disabled
                    className="w-full bg-background/50 border border-border/60 text-muted-foreground rounded px-2.5 py-1 outline-none text-[11px] appearance-none font-medium"
                  >
                    <option>EM-Copilot Development</option>
                  </select>
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground/60">
                    <ChevronDown size={10} />
                  </div>
                </div>
              </div>

              {/* Diagnostics Box */}
              <div className="space-y-2">
                <p className="text-[11px] text-muted-foreground/80 leading-normal">
                  Your feedback, diagnostic logs, and task transcript will be used to improve EM Copilot.
                </p>

                <div className="border border-border/60 rounded-lg p-3.5 space-y-2 bg-secondary/30 relative">
                  <div className="flex items-center justify-between text-xs font-medium">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-muted-foreground font-semibold">Diagnostic logs will be attached.</span>
                      <button
                        type="button"
                        onClick={() => setShowLogsDetails(!showLogsDetails)}
                        className="text-primary hover:underline text-left flex items-center gap-0.5"
                      >
                        What's included?
                        {showLogsDetails ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                      </button>
                    </div>
                    <span className="text-[10px] text-muted-foreground font-semibold uppercase font-mono tracking-wider">
                      {diagnosticInfo.version} · {diagnosticInfo.os.toLowerCase()}
                    </span>
                  </div>

                  {showLogsDetails && (
                    <div className="mt-2 pt-2 border-t border-border/40 text-[10px] font-mono text-muted-foreground space-y-1 overflow-x-auto max-h-24 bg-background/50 p-2 rounded">
                      <div><strong>OS:</strong> {diagnosticInfo.os}</div>
                      <div><strong>Browser:</strong> {diagnosticInfo.browser}</div>
                      <div><strong>Resolution:</strong> {diagnosticInfo.screenResolution}</div>
                      <div><strong>Language:</strong> {diagnosticInfo.language}</div>
                      <div><strong>Timestamp:</strong> {diagnosticInfo.timestamp}</div>
                      <div><strong>Run ID:</strong> {runId || 'None'}</div>
                      <div className="truncate"><strong>User Agent:</strong> {diagnosticInfo.userAgent}</div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div className="px-6 py-4 bg-secondary/10 border-t border-border/40 flex justify-end gap-3 shrink-0">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="px-4 py-2 border border-border bg-card hover:bg-secondary rounded-lg text-xs font-bold text-foreground transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-5 py-2 bg-zinc-950 dark:bg-zinc-100 hover:bg-zinc-900 dark:hover:bg-zinc-200 text-zinc-100 dark:text-zinc-900 rounded-lg text-xs font-bold transition-colors flex items-center gap-1.5 shadow-md disabled:opacity-50"
              >
                {isSubmitting && <Loader2 size={12} className="animate-spin" />}
                Submit
              </button>
            </div>

          </form>
        )}
      </div>
    </div>
  );
}
