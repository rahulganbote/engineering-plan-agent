/**
 * TermsOfServicePage - the /#/terms route.
 *
 * Reached from the footer/upload area of the copilot page.
 * Details the sandbox terms of service, authority to upload, warranty disclaimers,
 * and limitation of liability.
 */
import { ArrowLeft, FileText, AlertTriangle, ShieldAlert, ShieldCheck, Mail, Shield } from "lucide-react";
import { ThemePicker } from "./ThemePicker";

const goHome = () => {
  window.history.pushState(null, '', '/');
  window.dispatchEvent(new Event('hashchange'));
};

export const TermsOfServicePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans antialiased">
      {/* Sticky header mirrors AboutPage and PrivacyPolicyPage for visual continuity */}
      <header className="sticky top-0 z-30 bg-background/90 backdrop-blur border-b border-border">
        <div className="max-w-3xl mx-auto px-6 min-h-16 flex items-center justify-between gap-4 py-3">
          <button
            onClick={goHome}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition font-semibold"
            aria-label="Back to Copilot"
          >
            <ArrowLeft size={16} />
            <span>Back to Copilot</span>
          </button>
          <div className="flex items-center gap-4">
            <span className="text-sm font-bold text-primary">EM Copilot</span>
            <ThemePicker />
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        {/* Page Title */}
        <section className="space-y-3 pb-6 border-b border-border/40">
          <h1 className="text-3xl font-extrabold tracking-tight flex items-center gap-3">
            <FileText className="text-primary" size={32} />
            Terms of Service
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Effective Date: July 1<sup>st</sup>, 2026. These Terms of Service govern your use of the EM Copilot demonstration platform. By accessing the application, you agree to these Terms.
          </p>
        </section>

        {/* Advisory Block */}
        <section className="p-5 rounded-xl border border-warning/30 bg-warning/5 space-y-3">
          <div className="flex items-center gap-2 text-warning">
            <AlertTriangle size={20} />
            <h3 className="text-sm font-bold">Important Evaluation & Sandbox Terms</h3>
          </div>
          <p className="text-xs leading-relaxed text-foreground">
            EM Copilot is currently configured as a <strong>sandbox and demonstration environment</strong>. It is provided strictly for educational, testing, and portfolio evaluation purposes. You should not upload sensitive, proprietary, or regulated production data.
          </p>
        </section>

        {/* Core Pillars / Terms Cards */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Card 1: Authority to Upload */}
          <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary flex items-center gap-1.5">
              <ShieldCheck size={14} />
              Authority to Upload
            </h3>
            <p className="text-xs leading-relaxed text-muted-foreground">
              By uploading a Business Requirements Document (BRD) or other documentation, you warrant and represent that you have all necessary rights, licenses, consents, and authority to upload and process such content.
            </p>
          </div>

          {/* Card 2: Exclusion of Liability */}
          <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-danger flex items-center gap-1.5">
              <ShieldAlert size={14} />
              No Warranty & Liability Limits
            </h3>
            <p className="text-xs leading-relaxed text-muted-foreground">
              This service is provided <strong>AS-IS</strong>. To the maximum extent permitted by law, the developers and maintainers exclude all liability for direct, indirect, incidental, or consequential damages resulting from your use of this tool.
            </p>
          </div>
        </section>

        {/* Detailed Terms Sections */}
        <section className="space-y-6 pt-4 text-sm leading-relaxed text-foreground">
          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">1. Description of Service</h2>
            <p className="text-xs text-muted-foreground">
              EM Copilot is an AI-assisted orchestration tool designed to generate draft engineering plans, architecture blueprints, component breakdowns, proof-of-concept guidelines, and schedules from Business Requirements Documents (BRDs). As a demonstration and research project, the service is subject to modification, downtime, and deprecation at any time without prior notice.
            </p>
          </div>

          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">2. Acceptable Use & Upload Constraints</h2>
            <p className="text-xs text-muted-foreground">
              You agree not to upload any content that:
            </p>
            <ul className="text-xs text-muted-foreground space-y-1 pl-4 list-disc marker:text-primary">
              <li>Contains highly confidential commercial information, trade secrets, or proprietary source code.</li>
              <li>Contains unredacted Personally Identifiable Information (PII) including names, email addresses, financial accounts, or health records subject to GDPR, HIPAA, or other privacy regulations.</li>
              <li>Is unlawful, harmful, threatening, abusive, defamatory, or otherwise objectionable.</li>
              <li>Contains viruses, malware, prompt injection attacks designed to exploit foundation models, or other malicious payloads.</li>
            </ul>
          </div>

          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">3. Processing & Third-Party APIs</h2>
            <p className="text-xs text-muted-foreground">
              Uploading a document initiates an orchestration process that routes sanitized text chunks to external generative AI model providers (OpenAI, Anthropic, or others selected in the interface). Please review our <a href="#/privacy" className="text-primary hover:underline font-semibold">Privacy Policy</a> to understand data handling, transit, and vector storage details.
            </p>
          </div>

          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">4. Intellectual Property & Code Output</h2>
            <p className="text-xs text-muted-foreground">
              We claim no ownership over the BRDs you upload or the generated plans produced for you. Generated plans are synthesized by third-party language models and provided to you to adopt, edit, or reject. You bear sole responsibility for checking, compiling, and testing any software plans or code outputs prior to production use.
            </p>
          </div>

          <div className="space-y-2 pt-2">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Shield size={16} className="text-muted-foreground" />
              5. Disclaimer of Warranties
            </h2>
            <p className="text-xs text-muted-foreground italic">
              THE PLATFORM AND ALL DERIVED PLANS OR ARTIFACTS ARE PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, SECURE, OR THAT THE RESULTS PRODUCED WILL BE ACCURATE OR RELIABLE.
            </p>
          </div>

          <div className="space-y-2 pt-2">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <AlertTriangle size={16} className="text-muted-foreground" />
              6. Limitation of Liability
            </h2>
            <p className="text-xs text-muted-foreground italic">
              IN NO EVENT SHALL THE MAINTAINERS, DEVELOPERS, OR CONTRIBUTORS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE, UPLOADED DATA, AI-GENERATED PLANS, SYNC TO EXTERNAL JIRA INSTANCES, OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
            </p>
          </div>

          <div className="space-y-2 pt-2">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Mail size={16} className="text-muted-foreground" />
              7. Contact & Support
            </h2>
            <p className="text-xs text-muted-foreground">
              If you have any questions about these Terms, or wish to report security concerns or abuse, please contact us at:{" "}
              <a href="mailto:contact@emcopilot.ai" className="text-primary hover:underline font-medium">
                contact@emcopilot.ai
              </a>
              .
            </p>
          </div>
        </section>

        {/* Footer info */}
        <footer className="text-center pt-8 border-t border-border/40 text-xs text-muted-foreground space-y-1">
          <p>Last updated: July 1<sup>st</sup>, 2026.</p>
          <p>© 2026 EM Copilot. Independently maintained demonstration project.</p>
        </footer>
      </main>
    </div>
  );
};
