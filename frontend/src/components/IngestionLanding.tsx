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

const PERKS = [
  'Upload complex BRDs (PDF, DOCX, or TXT)',
  'Watch the Agentic AI Pipeline run and review Engineering Plan artifacts with a quality score',
  'Download artifacts or Approve to create Epic using generated Engineering Plan directly into Jira',
];

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
    <div className="space-y-9 w-full max-w-5xl mx-auto py-4">
      {/* Capped at max-w-5xl (1024px) — tightened from max-w-6xl per
          feedback that even the industry-standard 1152px column felt too
          big on a wide monitor. */}
      {/* Welcome & Subtitle Section — big, centered hero (Figma-style type
          scale) with a single primary CTA for signed-out visitors. Signed-in
          users already have Upload/Generate in the sidebar, so no duplicate
          CTA is shown once authenticated. */}
      <div className="space-y-2 text-center max-w-4xl mx-auto pt-0 sm:pt-2">
        <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-foreground leading-[1.1]">
          Transform a Business Requirements Document into your organization's standard Engineering Plan in{' '}
          <span className="text-primary">minutes</span>
        </h2>
        <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          EM Copilot, the <span className="text-primary font-bold">Engineering Plan Agent</span>, transforms your raw BRD into an audit-ready engineering plan, grounded via <span className="text-primary font-bold">RAG</span> (Retrieval-Augmented Generation) in your organization's standards, allowed tech stack, and own architectural patterns.
        </p>
        {!isAuthenticated && (
          <div className="space-y-3 max-w-2xl mx-auto pt-1">
            <ul className="text-sm sm:text-sm text-muted-foreground space-y-1.5 text-left bg-secondary/40 border border-border/50 rounded-lg px-4 py-3">
              {PERKS.map((perk) => (
                <li key={perk} className="flex items-start gap-2">
                  <span className="text-success font-bold shrink-0">✓</span>
                  <span>{perk}</span>
                </li>
              ))}
            </ul>
            <button
              onClick={onLogin}
              className="inline-flex items-center gap-3 px-8 py-4 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold text-base md:text-lg shadow-lg transition"
            >
              Sign in with Google to Get Started
            </button>
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
      {/* max-w-4xl matches the H1 hero's width above, and How It Works below
          — all three now share one column so the page reads as a single
          aligned layout instead of cards of differing widths. */}
      <div id="see-it-in-action" className="w-full max-w-4xl mx-auto bg-card border border-border rounded-xl p-3 md:p-4 shadow-lg space-y-3 scroll-mt-20">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-black text-primary uppercase tracking-wider">
            How it works
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
              SNEAK PEEK
            </span>
          )}
        </div>

        {showVideo ? (
          <div className="relative w-full aspect-video rounded-lg overflow-hidden border border-border bg-muted/30">
            <iframe
              src="https://www.loom.com/embed/b45c127069f84573b0a713a241155214?hide_owner=true&hide_title=true&hideEmbedTopBar=true&autoplay=true"
              className="absolute inset-0 w-full h-full"
              allowFullScreen
              allow="autoplay; fullscreen; picture-in-picture"
              title="EM Copilot demo — BRD to Engineering Plan in minutes"
            />
          </div>
        ) : (
          <div className="space-y-3">
            {hasSlides ? (
              // Screenshot carousel — cross-fading through real pipeline states.
              <div className="space-y-3">
                {/* Interactive Preview Container with Full-Card Play Overlay */}
                <div
                  onClick={() => setShowVideo(true)}
                  className="group relative w-full aspect-video bg-slate-950 rounded-xl border border-border/60 overflow-hidden cursor-pointer shadow-md hover:shadow-xl transition-all duration-300"
                >
                  {slides.map((slide, i) => (
                    <img
                      key={slide.src}
                      src={slide.src}
                      alt={slide.caption}
                      onError={() => setFailedSrcs((prev) => new Set(prev).add(slide.src))}
                      className={`absolute inset-0 w-full h-full object-cover object-center transition-opacity duration-300 group-hover:scale-[1.01] transform ${i === activeIndex ? 'opacity-90 group-hover:opacity-75' : 'opacity-0'
                        }`}
                    />
                  ))}

                  {/* Centered Play Button Overlay */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/20 group-hover:bg-slate-950/40 transition-colors duration-300 z-20">
                    {/* Glowing Primary Play Circle */}
                    <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#4f46e5] text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition-all duration-300">
                      <Play className="w-6 h-6 sm:w-7 sm:h-7 fill-white translate-x-0.5" />
                    </div>
                  </div>

                  {/* Caption bar */}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-4 pt-8 pb-2.5 z-10">
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
                        className={`h-1.5 rounded-full transition-all ${i === activeIndex ? 'w-5 bg-primary' : 'w-1.5 bg-border hover:bg-muted-foreground'
                          }`}
                      />
                    ))}
                  </div>
                )}

                {/* Persistent solid CTA */}
                <button
                  onClick={() => setShowVideo(true)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 bg-primary hover:bg-primary/90 active:scale-[0.99] rounded-lg font-bold text-sm text-white shadow-md transition-all duration-150 cursor-pointer"
                >
                  <Play size={16} fill="currentColor" />
                  Watch &lt;1min Walkthrough Video
                </button>
              </div>
            ) : (
              // Fallback: ambient icon pulse when no screenshots are present.
              <div className="space-y-3">
                <div
                  onClick={() => setShowVideo(true)}
                  className="group relative flex items-center justify-center gap-3 sm:gap-5 py-8 rounded-xl border border-border/60 bg-card cursor-pointer hover:shadow-md transition-all duration-300"
                >
                  {PULSE_ICONS.map((Icon, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-primary/10 text-primary"
                      style={{ animation: 'pipelinePulse 3.6s ease-in-out infinite', animationDelay: `${i * 0.6}s` }}
                    >
                      <Icon size={20} />
                    </div>
                  ))}
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/10 group-hover:bg-slate-950/20 transition-colors duration-300 rounded-xl">
                    <div className="w-12 h-12 rounded-full bg-[#4f46e5] text-white flex items-center justify-center shadow-md group-hover:scale-110 transition-all duration-300">
                      <Play className="w-5 h-5 fill-white translate-x-0.5" />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* User-journey workflow diagram — story-first, non-technical audience.
          The technical System Architecture diagram (was TimelineStepper) has
          moved to the About page for engineers/technical evaluators who want
          the plumbing view. */}
      <div id="how-it-works" className="w-full max-w-4xl mx-auto scroll-mt-20">
        <LandingWorkflow title="Engineering Plan Agent Workflow" />
      </div>
    </div>
  );
};
