/**
 * Voice brief generator for ElevenLabs Conversational AI.
 *
 * Reads the loaded pipeline artifacts and assembles a concise narrative summary
 * that the voice agent can recite or quote from. Designed to fit inside an
 * ElevenLabs dynamic variable (target ~1.5 KB, hard cap ~3 KB).
 *
 * Returns "" when artifacts aren't ready yet — the system prompt should detect
 * empty briefs and tell the EM to wait.
 *
 * Why client-side: the React UI already has the full artifacts in WorkspaceContext
 * via SSE, so we avoid an extra round-trip and ElevenLabs sees the brief at
 * conversation start (no tool-call latency).
 */
import type { ArtifactsState, CriticOutput } from '../hooks/useSSE';

interface Phase {
  name: string;
  duration_weeks: number;
  milestones?: { owner_role?: string }[];
}

interface Risk {
  description: string;
  likelihood?: string;
  impact?: string;
}

interface PlanOutput {
  phases?: Phase[];
  risks?: Risk[];
  team_composition?: Record<string, number>;
  total_duration_weeks?: number;
}

interface ArchOutput {
  pattern?: string;
  components?: { name?: string }[];
}

interface StackOption {
  name?: string;
  category?: string;
  technology?: string;
  domain?: string;
}

interface TechStackOutput {
  options?: StackOption[];
}

export function generateVoiceBrief(
  artifacts: ArtifactsState | null,
  criticOutput: CriticOutput | null,
  runId: string,
): string {
  if (!artifacts || !criticOutput) return '';

  const plan = (artifacts.plan_output ?? {}) as PlanOutput;
  const arch = (artifacts.arch_output ?? {}) as ArchOutput;
  const stack = (artifacts.stack_output ?? {}) as TechStackOutput;

  const parts: string[] = [];

  // ── Critic score + badge ────────────────────────────────────────────────
  const score = criticOutput.overallScore?.toFixed(2) ?? '?';
  const badge = (criticOutput.badge ?? '').toString();
  parts.push(
    `Run ${runId.slice(0, 8)}. The Critic gave this plan ${score} out of 5 with a ${badge} badge.`,
  );

  // ── Plan summary ────────────────────────────────────────────────────────
  const weeks = plan.total_duration_weeks;
  const phaseCount = plan.phases?.length ?? 0;
  if (weeks && phaseCount) {
    parts.push(`The plan covers ${weeks} weeks across ${phaseCount} phases.`);
    const top = plan.phases!.slice(0, 3);
    const phaseLine = top
      .map((p, i) => `Phase ${i + 1}, ${p.name}, runs ${p.duration_weeks} weeks`)
      .join('; ');
    if (phaseLine) parts.push(`${phaseLine}.`);
  }

  // ── Team composition ────────────────────────────────────────────────────
  if (plan.team_composition && Object.keys(plan.team_composition).length) {
    const totalHeadcount = Object.values(plan.team_composition).reduce(
      (a, b) => a + (Number(b) || 0),
      0,
    );
    const roles = Object.entries(plan.team_composition)
      .slice(0, 4)
      .map(([role, n]) => `${n} ${role}`)
      .join(', ');
    parts.push(`Team of ${totalHeadcount}: ${roles}.`);
  }

  // ── Architecture ────────────────────────────────────────────────────────
  if (arch.pattern || arch.components?.length) {
    const componentCount = arch.components?.length ?? 0;
    const pattern = arch.pattern ?? 'unspecified pattern';
    parts.push(
      `Architecture uses ${pattern} with ${componentCount} components.`,
    );
  }

  // ── Tech stack (top recommended option) ─────────────────────────────────
  if (stack.options?.length) {
    const top = stack.options[0];
    const techName = top.name ?? top.technology ?? 'recommended option';
    const techDomain = top.category ?? top.domain ?? '';
    parts.push(
      techDomain
        ? `Top tech stack recommendation: ${techName} for ${techDomain}.`
        : `Top tech stack recommendation: ${techName}.`,
    );
  }

  // ── Top risks (most narrative-impactful element) ────────────────────────
  if (plan.risks?.length) {
    const top = plan.risks.slice(0, 3);
    const riskLine = top
      .map((r, i) => {
        const sev = r.impact ? ` (${r.impact} impact)` : '';
        return `${i + 1}) ${r.description}${sev}`;
      })
      .join('. ');
    parts.push(`Top risks: ${riskLine}.`);
  }

  // Join + trim to keep well under the dynamic-variable size cap
  const brief = parts.join(' ');
  return brief.length > 2800 ? brief.slice(0, 2800) + '…' : brief;
}
