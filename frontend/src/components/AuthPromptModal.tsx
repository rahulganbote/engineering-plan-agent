import { X, AlertTriangle } from 'lucide-react';

interface AuthPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: () => void;
  // Both nav CTAs ("Sign in" and "Get started") open this same modal and
  // same Google OAuth flow — there's only one auth path. This just varies
  // the headline copy so the two buttons don't feel like true duplicates.
  variant?: 'signin' | 'signup';
}

export default function AuthPromptModal({ isOpen, onClose, onLogin, variant = 'signup' }: AuthPromptModalProps) {
  if (!isOpen) return null;

  const headline = variant === 'signin' ? 'Welcome back' : 'Get started with EM Copilot';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="bg-card border border-border shadow-2xl rounded-2xl max-w-lg w-full relative z-10 flex flex-col overflow-hidden animate-scale-in text-foreground">

        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 text-muted-foreground hover:text-foreground transition p-2 rounded-lg hover:bg-secondary/80"
          aria-label="Close sign-in prompt"
        >
          <X size={20} />
        </button>

        <div className="px-8 pt-10 pb-8 text-center space-y-6">
          <div className="mx-auto h-16 w-16 rounded-xl flex items-center justify-center overflow-hidden">
            <img src="/favicon.svg" alt="EM Copilot" className="h-full w-full object-contain" />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">{headline}</h2>
            <p className="text-sm sm:text-base text-muted-foreground">Free to use. Your email is only used to track & limit usage.</p>
          </div>

          <div className="text-left bg-amber-500/5 dark:bg-amber-500/10 border border-amber-500/30 rounded-xl p-4.5 space-y-2">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-500 font-extrabold text-sm sm:text-base">
              <AlertTriangle size={18} className="shrink-0" />
              <span>Important Terms</span>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed font-medium">
              Your <span className="font-bold text-foreground">email-id</span> and <span className="font-bold text-foreground">BRD data</span> is stored temporarily in our App. EM Copilot is currently configured as a <span className="font-bold text-foreground">sandbox and demonstration environment</span>.  BRD data is shared with LLM providers (OpenAI, Anthropic) and third party tool like Tavily, Pinecone etc. to generate the engineering plan. You should not upload sensitive, proprietary, or regulated production data here.
            </p>
          </div>

          <button
            onClick={onLogin}
            className="w-full py-4 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold text-base sm:text-lg shadow-md transition"
          >
            Sign in with Google
          </button>

          <button
            onClick={onClose}
            className="block w-full text-sm font-semibold text-muted-foreground hover:text-foreground transition"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
