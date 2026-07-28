import { X, AlertTriangle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

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
  const { loginAsGuest } = useAuth();

  if (!isOpen) return null;

  const headline = variant === 'signin' ? 'Welcome back' : 'Get started with EM Copilot';

  const handleGuestLogin = async () => {
    await loginAsGuest();
    onClose();
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
          aria-label="Close sign-in prompt"
        >
          <X size={18} />
        </button>

        <div className="px-6 pt-8 pb-6 text-center space-y-4">
          <div className="mx-auto h-12 w-12 rounded-xl flex items-center justify-center overflow-hidden">
            <img src="/favicon.svg" alt="EM Copilot" className="h-full w-full object-contain" />
          </div>

          <div className="space-y-1">
            <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight">{headline}</h2>
            <p className="text-xs sm:text-sm text-muted-foreground">Free to use. Your email is only used to track & limit usage.</p>
          </div>

          <div className="text-left bg-amber-500/5 dark:bg-amber-500/10 border border-amber-500/30 rounded-xl p-3.5 space-y-1.5">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-500 font-extrabold text-xs sm:text-sm">
              <AlertTriangle size={16} className="shrink-0" />
              <span>Important Terms</span>
            </div>
            <p className="text-[11px] sm:text-xs text-muted-foreground leading-relaxed font-medium">
              Your <span className="font-bold text-foreground">email-id</span> and <span className="font-bold text-foreground">BRD data</span> is stored temporarily in our App. EM Copilot is currently configured as a <span className="font-bold text-foreground">sandbox and demonstration environment</span>.  BRD data is shared with LLM providers (OpenAI, Anthropic) and third party tool like Tavily, Pinecone etc. to generate the engineering plan. You should not upload sensitive, proprietary, or production data here.
            </p>
          </div>

          <p className="text-[10px] text-muted-foreground leading-relaxed text-center font-medium px-2">
            By continuing, I accept the{' '}
            <a href="#/terms" target="_blank" rel="noopener noreferrer" className="font-bold text-foreground hover:underline">
              Services Agreement
            </a>{' '}
            and acknowledge that I have read the{' '}
            <a href="#/privacy" target="_blank" rel="noopener noreferrer" className="font-bold text-foreground hover:underline">
              Privacy Policy
            </a>
            .
          </p>

          <div className="space-y-2.5">
            <button
              onClick={onLogin}
              className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold text-sm sm:text-base shadow-md transition"
            >
              Sign in with Google
            </button>

            <button
              onClick={handleGuestLogin}
              className="w-full py-2.5 bg-secondary hover:bg-secondary/80 text-foreground rounded-xl font-bold text-xs sm:text-sm border border-border transition"
            >
              Try it free as a guest (runs on Llama 3.3 70B)
            </button>
          </div>

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
