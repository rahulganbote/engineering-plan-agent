import React, { useState, useEffect } from 'react';
import { Upload, Search, FileText, Scale, UserCheck, Rocket, Play, ChevronLeft } from 'lucide-react';
import { LandingWorkflow } from './LandingWorkflow';

interface IngestionLandingProps {
  selectedFile: File | null;
  onFileSelect: (file: File) => void;
  onRemoveFile: () => void;
  onTrigger: () => void;
  isLoading: boolean;
  isAuthenticated: boolean;
  onLogin: () => void;
}

// Real product screenshots cycled in the "glimpse" carousel — each is a
// cropped capture of the live Agentic Workflow Progress diagram in a distinct
// pipeline state, so a first-time visitor sees the actual product working
// before committing to the full 97s walkthrough.
//
// Drop the cropped PNGs into frontend/public/glimpse/ using these exact
// filenames. Until they exist, each <img> fails gracefully and the component
// falls back to the ambient icon pulse (PULSE_ICONS) below — nothing breaks.
const GLIMPSE_SLIDES = [
  { src: '/glimpse/01-upload.png', caption: 'Upload your BRD to kick off the pipeline' },
  { src: '/glimpse/02-orchestrator.png', caption: 'The Orchestrator parses it and routes to specialists' },
  { src: '/glimpse/03-drafting.png', caption: '5 specialist agents draft the plan in parallel' },
  { src: '/glimpse/04-evaluating.png', caption: 'An independent Critic grades the output' },
  { src: '/glimpse/05-decision.png', caption: 'You approve at the Decision Gate' },
  { src: '/glimpse/06-jira.png', caption: 'The approved plan ships to a Jira Epic — audit trail preserved' },
];

// Ambient fallback — mirrors the Tier 1 workflow chain in LandingWorkflow so
// the two visuals feel like one story when screenshots are unavailable.
const PULSE_ICONS = [Upload, Search, FileText, Scale, UserCheck, Rocket];

export const IngestionLanding: React.FC<IngestionLandingProps> = ({
  selectedFile: _selectedFile,
  isAuthenticated,
  onLogin,
}) => {
  const [showVideo, setShowVideo] = useState(false);
  const [slideIndex, setSlideIndex] = useState(0);
  const [failedSrcs, setFailedSrcs] = useState<Set<string>>(new Set());

  const slides = GLIMPSE_SLIDES.filter((s) => !failedSrcs.has(s.src));
  const hasSlides = slides.length > 0;
  const activeIndex = hasSlides ? slideIndex % slides.length : 0;

  // Auto-advance the carousel while the glimpse (not the video) is showing.
  useEffect(() => {
    if (showVideo || slides.length < 2) return;
    const id = setInterval(() => setSlideIndex((i) => i + 1), 1500);
    return () => clearInterval(id);
  }, [showVideo, slides.length]);

  return (
    <div className="space-y-3 w-full py-2">
      {/* Welcome & Subtitle Section — big, centered hero (Figma-style type
          scale) with a single primary CTA for signed-out visitors. Signed-in
          users already have Upload/Generate in the sidebar, so no duplicate
          CTA is shown once authenticated. */}
      <div className="space-y-4 text-center max-w-4xl mx-auto pt-4 sm:pt-10">
        <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-foreground leading-[1.1]">
          Transform a Business Requirements Document (BRD) into your organization's standard Engineering Plan in{' '}
          <span className="text-primary">minutes</span>
        </h2>
        <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          EM Copilot transforms your raw BRD into an audit-ready engineering plan, grounded via RAG (Retrieval-Augmented Generation) in your organization's own architectural patterns and approved tech stack. Artifacts are presented for your review; on approval, pushed to Jira.
        </p>
        {!isAuthenticated && (
          <div className="space-y-2">
            <button
              onClick={onLogin}
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary hover:bg-primary/90 text-white rounded-lg font-bold text-sm shadow-md transition"
            >
              Sign in with Google to Get Started
            </button>
            <p className="text-xs text-muted-foreground">
              Takes 10 seconds — then upload your BRD and get a plan in minutes.
            </p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pipelinePulse {
          0%, 100% { opacity: 0.3; transform: scale(0.9); }
          15% { opacity: 1; transform: scale(1.08); }
          30% { opacity: 0.3; transform: scale(0.9); }
        }
      `}</style>
      <div id="see-it-in-action" className="w-full bg-card border border-border rounded-xl p-3 md:p-4 shadow-lg space-y-3 scroll-mt-20">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-black text-primary uppercase tracking-wider">
            See It in Action
          </h3>
          {showVideo ? (
            <button
              onClick={() => setShowVideo(false)}
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
            >
              <ChevronLeft size={13} /> Back to glimpse
            </button>
          ) : (
            <span className="text-xs text-muted-foreground font-semibold tracking-wider">
              LIVE GLIMPSE
            </span>
          )}
        </div>

        {showVideo ? (
          <div className="relative w-full aspect-video rounded-lg overflow-hidden border border-border bg-muted/30">
            <iframe
              src="https://www.loom.com/embed/b45c127069f84573b0a713a241155214?hide_owner=true&hide_title=true&hideEmbedTopBar=true"
              className="absolute inset-0 w-full h-full"
              allowFullScreen
              allow="fullscreen; picture-in-picture"
              title="EM Copilot demo — BRD to Engineering Plan in minutes"
            />
          </div>
        ) : (
          <div className="space-y-3">
            {hasSlides ? (
              // Screenshot carousel — cross-fades through real pipeline states.
              <div className="space-y-2">
                <div className="relative w-full aspect-video rounded-lg overflow-hidden border border-border bg-slate-900">
                  {slides.map((slide, i) => (
                    <img
                      key={slide.src}
                      src={slide.src}
                      alt={slide.caption}
                      onError={() => setFailedSrcs((prev) => new Set(prev).add(slide.src))}
                      className={`absolute inset-0 w-full h-full object-cover object-top transition-opacity duration-700 ${
                        i === activeIndex ? 'opacity-100' : 'opacity-0'
                      }`}
                    />
                  ))}
                  {/* Caption bar */}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-4 pt-8 pb-2.5">
                    <p className="text-xs sm:text-sm font-semibold text-white text-center">
                      {slides[activeIndex]?.caption}
                    </p>
                  </div>
                </div>
                {/* Progress dots */}
                {slides.length > 1 && (
                  <div className="flex items-center justify-center gap-1.5">
                    {slides.map((slide, i) => (
                      <button
                        key={slide.src}
                        onClick={() => setSlideIndex(i)}
                        aria-label={`Show step ${i + 1}`}
                        className={`h-1.5 rounded-full transition-all ${
                          i === activeIndex ? 'w-5 bg-primary' : 'w-1.5 bg-border hover:bg-muted-foreground'
                        }`}
                      />
                    ))}
                  </div>
                )}
              </div>
            ) : (
              // Fallback: ambient icon pulse when no screenshots are present.
              <div className="flex items-center justify-center gap-3 sm:gap-5 py-4">
                {PULSE_ICONS.map((Icon, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-primary/10 text-primary"
                    style={{ animation: 'pipelinePulse 3.6s ease-in-out infinite', animationDelay: `${i * 0.6}s` }}
                  >
                    <Icon size={20} />
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => setShowVideo(true)}
              className="group w-full flex items-center justify-center gap-2 py-2.5 bg-secondary/60 hover:bg-secondary hover:shadow-md text-foreground rounded-lg font-bold text-sm transition-all"
            >
              <span className="relative flex items-center justify-center w-5 h-5">
                <span className="absolute inset-0 rounded-full bg-primary/30 group-hover:animate-ping" />
                <Play size={16} className="relative text-primary" />
              </span>
              Watch the 97s walkthrough
            </button>
          </div>
        )}
      </div>

      {/* User-journey workflow diagram — story-first, non-technical audience.
          The technical System Architecture diagram (was TimelineStepper) has
          moved to the About page for engineers/technical evaluators who want
          the plumbing view. */}
      <div id="how-it-works" className="scroll-mt-20">
        <LandingWorkflow title="How It Works" />
      </div>
    </div>
  );
};
