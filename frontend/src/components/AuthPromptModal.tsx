import { X, Sparkles } from 'lucide-react';

interface AuthPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: () => void;
}

// Perks shown to convince a signed-out visitor to sign in — replaces the
// "What you can do:" checklist that used to sit permanently in the sidebar.
const PERKS = [
  'Upload complex BRDs (PDF, DOCX, or TXT)',
  'Watch the Agentic Pipeline run and review Engineering Plan artifacts with a confidence score',
  'Download or sync your approved Engineering Plan directly into a Jira Epic',
];

export default function AuthPromptModal({ isOpen, onClose, onLogin }: AuthPromptModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="bg-card border border-border shadow-2xl rounded-2xl max-w-sm w-full relative z-10 flex flex-col overflow-hidden animate-scale-in text-foreground">

        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition p-1.5 rounded-lg hover:bg-secondary/80"
          aria-label="Close sign-in prompt"
        >
          <X size={16} />
        </button>

        <div className="px-6 pt-8 pb-6 text-center space-y-5">
          <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 text-primary flex items-center justify-center">
            <Sparkles size={22} />
          </div>

          <div className="space-y-1.5">
            <h2 className="text-lg font-extrabold tracking-tight">Sign in to run the pipeline</h2>
            <p className="text-xs text-muted-foreground">Free to use. Your email only identifies your sessions.</p>
          </div>

          <ul className="text-xs text-muted-foreground space-y-2.5 text-left bg-secondary/40 border border-border/50 rounded-lg p-4">
            {PERKS.map((perk) => (
              <li key={perk} className="flex items-start gap-2">
                <span className="text-success font-bold shrink-0">✓</span>
                <span>{perk}</span>
              </li>
            ))}
          </ul>

          <button
            onClick={onLogin}
            className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-lg font-bold text-sm shadow-md transition"
          >
            Sign in with Google
          </button>

          <button
            onClick={onClose}
            className="block w-full text-xs text-muted-foreground hover:text-foreground transition"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
