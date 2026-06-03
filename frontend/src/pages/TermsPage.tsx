import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Shield, Scale, BadgeCheck, Landmark, ArrowLeft, Printer, Download, Share2, Menu, X
} from 'lucide-react';

const sections = [
  { id: 'introduction', title: '1. Introduction and Acceptance' },
  { id: 'definitions', title: '2. Definitions' },
  { id: 'eligibility', title: '3. Eligibility & Registration' },
  { id: 'services', title: '4. Description of Services' },
  { id: 'ai-disclaimer', title: '5. AI & Learning Disclaimer' },
  { id: 'acceptable-use', title: '6. Acceptable Use Policy' },
  { id: 'intellectual-property', title: '7. Intellectual Property' },
  { id: 'user-content', title: '8. User Content & Data' },
  { id: 'privacy', title: '9. Privacy & Security' },
  { id: 'payments', title: '10. Payments & Subscriptions' },
  { id: 'warranties', title: '11. Disclaimer of Warranties' },
  { id: 'liability', title: '12. Limitation of Liability' },
  { id: 'indemnification', title: '13. Indemnification' },
  { id: 'termination', title: '14. Termination' },
  { id: 'disputes', title: '15. Dispute Resolution' },
  { id: 'changes', title: '16. Modifications to Terms' },
  { id: 'contact', title: '17. Contact Information' }
];

export default function TermsPage() {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState('introduction');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 150;
      
      for (const section of sections) {
        const element = document.getElementById(section.id);
        if (element) {
          const { top, bottom } = element.getBoundingClientRect();
          const absoluteTop = top + window.scrollY;
          const absoluteBottom = bottom + window.scrollY;
          
          if (scrollPosition >= absoluteTop && scrollPosition < absoluteBottom) {
            setActiveSection(section.id);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setIsSidebarOpen(false);
    const element = document.getElementById(id);
    if (element) {
      window.scrollTo({
        top: element.offsetTop - 100,
        behavior: 'smooth'
      });
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-[#070714] text-gray-300 relative font-sans selection:bg-cyan-500/30 selection:text-cyan-100">
      {/* Background styling for corporate look */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-full h-[300px] bg-gradient-to-b from-[#0a0a1a] to-transparent border-b border-white/5" />
      </div>

      {/* Header Bar */}
      <header className="fixed top-0 left-0 right-0 h-16 bg-[#070714]/90 backdrop-blur-xl border-b border-white/10 z-40 flex items-center justify-between px-4 lg:px-8">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setIsSidebarOpen(true)} 
            className="lg:hidden p-2 text-gray-400 hover:text-white transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm font-semibold group">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span className="hidden sm:inline">Back to NeuroLab</span>
          </button>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="h-8 w-px bg-white/10 mx-2 hidden sm:block" />
          <button onClick={handlePrint} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-white/5">
            <Printer className="w-4 h-4" />
            <span className="hidden sm:inline">Print</span>
          </button>
          <button onClick={handlePrint} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-white/5">
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Download PDF</span>
          </button>
        </div>
      </header>

      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <div className="relative z-10 max-w-7xl mx-auto flex pt-16">
        
        {/* Navigation Sidebar */}
        <aside className={`
          fixed lg:sticky top-16 left-0 h-[calc(100vh-4rem)] w-72 bg-[#0a0a1a] lg:bg-transparent
          border-r border-white/10 lg:border-none z-50 transform transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          overflow-y-auto py-8 px-6 no-scrollbar
        `}>
          <div className="flex justify-between items-center mb-6 lg:hidden">
            <h3 className="text-white font-bold text-sm uppercase tracking-wider">Contents</h3>
            <button onClick={() => setIsSidebarOpen(false)} className="text-gray-400 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
          
          <nav className="space-y-1">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => scrollToSection(section.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-200 flex items-center gap-3
                  ${activeSection === section.id 
                    ? 'bg-cyan-500/10 text-cyan-400 font-semibold border border-cyan-500/20' 
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                  }
                `}
              >
                {section.title}
              </button>
            ))}
          </nav>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 max-w-4xl px-6 py-12 lg:px-12 lg:py-16 bg-[#070714] min-h-screen">
          
          <div className="mb-16 border-b border-white/10 pb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-bold uppercase tracking-wider mb-6">
              <Scale className="w-4 h-4" /> Legal Agreement
            </div>
            <h1 className="text-4xl md:text-5xl font-black text-white mb-6 leading-tight tracking-tight">
              NeuroLab AI Conditions of Use
            </h1>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-sm text-gray-400">
              <div>
                <p><strong className="text-gray-300">Last Updated:</strong> June 3, 2026</p>
                <p><strong className="text-gray-300">Effective Date:</strong> June 10, 2026</p>
              </div>
              <div>
                <p><strong className="text-gray-300">Version:</strong> 2.4.0 (Global Enterprise)</p>
                <p><strong className="text-gray-300">Entity:</strong> NeuroLab Technologies Inc.</p>
              </div>
            </div>
          </div>

          <div className="prose prose-invert prose-cyan max-w-none space-y-10">
            
            <section id="introduction" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">1.</span> Introduction and Acceptance
              </h2>
              <p className="leading-relaxed">
                Welcome to NeuroLab AI ("NeuroLab", "we", "our", or "us"). These Conditions of Use ("Terms", "Agreement") govern your access to and use of the NeuroLab AI platform, including our website, mobile applications, APIs, physical simulation engines, artificial intelligence tutoring services, and all related software and services (collectively, the "Services").
              </p>
              <p className="leading-relaxed mt-4">
                <strong>PLEASE READ THESE TERMS CAREFULLY BEFORE USING OUR SERVICES.</strong> By registering for an account, accessing, or utilizing any portion of the Services, you acknowledge that you have read, understood, and agree to be bound by these Terms in their entirety. If you are accepting these Terms on behalf of an educational institution, school district, corporation, or other legal entity, you represent and warrant that you have the authority to bind such entity to these Terms.
              </p>
              <p className="leading-relaxed mt-4 uppercase text-xs font-bold text-gray-500 tracking-wider">
                Note: Section 15 of these Terms contains a binding arbitration agreement and class action waiver that affect your legal rights.
              </p>
            </section>

            <section id="definitions" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">2.</span> Definitions
              </h2>
              <ul className="space-y-3 list-none pl-0">
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">"AI Tutor"</strong> refers to our proprietary generative artificial intelligence models configured to provide educational assistance, code explanations, and STEM problem-solving guidance.</li>
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">"Live Lab"</strong> refers to the computer-vision driven physical experiment tracking module that utilizes device cameras to analyze real-world phenomena.</li>
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">"User Content"</strong> means any data, text, code, audio, video, images, or other materials submitted, uploaded, or generated by you through the Services.</li>
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">"Institution"</strong> refers to a school, university, or educational organization that purchases enterprise or educational licensing for its students.</li>
              </ul>
            </section>

            <section id="eligibility" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">3.</span> Eligibility and Account Registration
              </h2>
              <h3 className="text-lg font-semibold text-gray-200 mt-6 mb-2">3.1 Age Requirements</h3>
              <p className="leading-relaxed">
                You must be at least 13 years of age (or the minimum legal age in your jurisdiction) to create a personal account. If you are under 18, you represent that you have your parent or legal guardian's permission to use the Services. If a school or educational institution has provisioned your account, that institution is responsible for obtaining any necessary parental consent under COPPA, FERPA, or similar applicable regulations.
              </p>
              <h3 className="text-lg font-semibold text-gray-200 mt-6 mb-2">3.2 Account Security</h3>
              <p className="leading-relaxed">
                You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You agree to notify us immediately of any unauthorized use of your account. NeuroLab will not be liable for any loss or damage arising from your failure to protect your login information. Accounts are strictly non-transferable.
              </p>
            </section>

            <section id="services" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">4.</span> Description of Services
              </h2>
              <p className="leading-relaxed">
                NeuroLab provides a virtual STEM (Science, Technology, Engineering, and Mathematics) laboratory environment. Our Services include, but are not limited to, real-time physics simulations, chemical reaction modeling, mathematics visualizations, code execution sandboxes, and AI-driven pedagogical tools.
              </p>
              <p className="leading-relaxed mt-4">
                We reserve the right to modify, update, suspend, or discontinue any part of the Services at our sole discretion, with or without notice, to improve performance, enhance security, or comply with legal requirements.
              </p>
            </section>

            <section id="ai-disclaimer" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">5.</span> Artificial Intelligence & Learning Disclaimer
              </h2>
              <div className="p-5 border border-amber-500/30 bg-amber-500/5 rounded-xl text-amber-200/90 leading-relaxed">
                <strong>CRITICAL EDUCATIONAL DISCLAIMER:</strong> The AI Tutor and automated assessment systems provided by NeuroLab utilize large language models and machine learning algorithms. While designed for high accuracy, AI-generated content may occasionally be inaccurate, incomplete, or misleading ("hallucinations").
                <br/><br/>
                Outputs from the AI Tutor do not constitute professional engineering, medical, legal, or safety advice. You must independently verify critical calculations, formulas, and scientific principles. NeuroLab is not liable for academic grades, research outcomes, or real-world physical damages resulting from reliance on our simulated data or AI explanations.
              </div>
            </section>

            <section id="acceptable-use" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">6.</span> Acceptable Use Policy
              </h2>
              <p className="leading-relaxed mb-4">When accessing or using the Services, you strictly agree NOT to:</p>
              <ul className="space-y-2 list-disc pl-5 marker:text-cyan-500">
                <li>Violate any applicable local, state, national, or international law or regulation.</li>
                <li>Attempt to reverse engineer, decompile, hack, disable, or disrupt the Services, our APIs, or underlying infrastructure.</li>
                <li>Use automated scripts, bots, spiders, or scrapers to extract data, training datasets, or AI model weights from the platform.</li>
                <li>Submit prompts to the AI Tutor intended to bypass safety filters, generate malicious code, produce hate speech, or create harmful content.</li>
                <li>Upload viruses, malware, or destructive code to our cloud environments or code sandboxes.</li>
                <li>Use the Live Lab camera features to record individuals without their explicit consent or in violation of privacy laws.</li>
                <li>Resell, sublicense, or commercialize the Services without a formal Enterprise Agreement.</li>
              </ul>
            </section>

            <section id="intellectual-property" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">7.</span> Intellectual Property Rights
              </h2>
              <h3 className="text-lg font-semibold text-gray-200 mt-6 mb-2">7.1 NeuroLab Ownership</h3>
              <p className="leading-relaxed">
                The Services, including but not limited to software code, proprietary algorithms, neural network architectures, UI/UX designs, trademarks, logos, simulations, and documentation, are the exclusive property of NeuroLab Technologies Inc. and its licensors, protected by copyright, trademark, patent, and trade secret laws.
              </p>
              <h3 className="text-lg font-semibold text-gray-200 mt-6 mb-2">7.2 Limited License</h3>
              <p className="leading-relaxed">
                Subject to your compliance with these Terms, NeuroLab grants you a limited, non-exclusive, non-transferable, revocable license to access and use the Services solely for your personal, non-commercial educational purposes (or as explicitly authorized under an Institutional License).
              </p>
            </section>

            <section id="user-content" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">8.</span> User Content and Data
              </h2>
              <p className="leading-relaxed">
                You retain all ownership rights to the User Content you create on the platform, including your code, experiment notes, and project files. By submitting User Content to the Services, you grant NeuroLab a worldwide, royalty-free, sublicensable license to host, store, process, and display that content solely as necessary to operate, provide, and maintain the Services.
              </p>
              <p className="leading-relaxed mt-4">
                NeuroLab does NOT use your personal User Content, private code, or webcam video feeds to train our foundational AI models. Webcam data processed by the Live Lab feature is computed in real-time, either locally on your device or ephemerally on our secure servers, and is immediately discarded.
              </p>
            </section>

            <section id="privacy" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">9.</span> Privacy and Data Security
              </h2>
              <p className="leading-relaxed">
                Your privacy is paramount. Our collection, use, and protection of your personal information are governed by our <a href="/privacy" className="text-cyan-400 hover:underline">Privacy Policy</a>. By using the Services, you consent to the data practices detailed therein. We implement industry-standard encryption (AES-256) and security protocols to safeguard your data.
              </p>
            </section>

            <section id="payments" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">10.</span> Payments, Subscriptions, and Refunds
              </h2>
              <p className="leading-relaxed">
                Certain premium features of NeuroLab AI require a paid subscription ("Pro Plan" or "Enterprise Plan"). By selecting a paid tier, you agree to pay all applicable fees in advance. Subscriptions automatically renew at the end of the billing cycle unless canceled prior to the renewal date.
              </p>
              <p className="leading-relaxed mt-4">
                <strong>Refund Policy:</strong> We offer a 14-day money-back guarantee for initial personal subscription purchases. Refund requests must be submitted to billing@neurolab.ai. Subsequent renewals and Enterprise contracts are non-refundable unless legally required.
              </p>
            </section>

            <section id="warranties" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">11.</span> Disclaimer of Warranties
              </h2>
              <p className="leading-relaxed uppercase font-semibold text-gray-400">
                THE SERVICES ARE PROVIDED ON AN "AS-IS" AND "AS-AVAILABLE" BASIS. NEUROLAB EXPRESSLY DISCLAIMS ALL WARRANTIES OF ANY KIND, WHETHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICES WILL BE UNINTERRUPTED, ERROR-FREE, SECURE, OR FREE FROM VIRUSES, NOR DO WE GUARANTEE THE ACCURACY OR RELIABILITY OF AI OUTPUTS OR SIMULATION DATA.
              </p>
            </section>

            <section id="liability" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">12.</span> Limitation of Liability
              </h2>
              <p className="leading-relaxed uppercase font-semibold text-gray-400">
                TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL NEUROLAB, ITS DIRECTORS, EMPLOYEES, PARTNERS, OR AFFILIATES BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING WITHOUT LIMITATION, LOSS OF PROFITS, DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES, RESULTING FROM (I) YOUR ACCESS TO OR USE OF OR INABILITY TO ACCESS OR USE THE SERVICES; (II) ANY CONDUCT OR CONTENT OF ANY THIRD PARTY ON THE SERVICES; (III) ANY CONTENT OBTAINED FROM THE SERVICES; OR (IV) UNAUTHORIZED ACCESS, USE, OR ALTERATION OF YOUR TRANSMISSIONS OR CONTENT. IN NO EVENT SHALL NEUROLAB'S TOTAL LIABILITY TO YOU EXCEED THE AMOUNT YOU PAID TO NEUROLAB IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.
              </p>
            </section>

            <section id="indemnification" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">13.</span> Indemnification
              </h2>
              <p className="leading-relaxed">
                You agree to defend, indemnify, and hold harmless NeuroLab and its licensee and licensors, and their employees, contractors, agents, officers, and directors, from and against any and all claims, damages, obligations, losses, liabilities, costs or debt, and expenses (including but not limited to attorney's fees), resulting from or arising out of a) your use and access of the Services, by you or any person using your account and password; b) a breach of these Terms; or c) your User Content violating third-party rights or applicable laws.
              </p>
            </section>

            <section id="termination" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">14.</span> Termination
              </h2>
              <p className="leading-relaxed">
                We may terminate or suspend your account and bar access to the Services immediately, without prior notice or liability, under our sole discretion, for any reason whatsoever and without limitation, including but not limited to a breach of the Terms.
              </p>
              <p className="leading-relaxed mt-4">
                If you wish to terminate your account, you may simply discontinue using the Services or request account deletion via the Profile Settings panel. All provisions of the Terms which by their nature should survive termination shall survive termination, including, without limitation, ownership provisions, warranty disclaimers, indemnity, and limitations of liability.
              </p>
            </section>

            <section id="disputes" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">15.</span> Governing Law and Dispute Resolution
              </h2>
              <p className="leading-relaxed">
                These Terms shall be governed and construed in accordance with the laws of the State of Delaware, United States, without regard to its conflict of law provisions.
              </p>
              <p className="leading-relaxed mt-4">
                <strong>Binding Arbitration:</strong> Any dispute, claim, or controversy arising out of or relating to these Terms or the breach, termination, enforcement, interpretation, or validity thereof, including the determination of the scope or applicability of this agreement to arbitrate, shall be determined by arbitration in Wilmington, Delaware, before one arbitrator. The arbitration shall be administered by JAMS pursuant to its Comprehensive Arbitration Rules and Procedures.
              </p>
              <p className="leading-relaxed mt-4 uppercase font-bold text-xs text-gray-500">
                CLASS ACTION WAIVER: YOU AND NEUROLAB AGREE THAT EACH MAY BRING CLAIMS AGAINST THE OTHER ONLY IN YOUR OR ITS INDIVIDUAL CAPACITY, AND NOT AS A PLAINTIFF OR CLASS MEMBER IN ANY PURPORTED CLASS OR REPRESENTATIVE PROCEEDING.
              </p>
            </section>

            <section id="changes" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">16.</span> Modifications to Terms
              </h2>
              <p className="leading-relaxed">
                We reserve the right, at our sole discretion, to modify or replace these Terms at any time. If a revision is material, we will provide at least 30 days' notice prior to any new terms taking effect. By continuing to access or use our Services after any revisions become effective, you agree to be bound by the revised terms.
              </p>
            </section>

            <section id="contact" className="scroll-mt-24 mb-32">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-cyan-500">17.</span> Contact Information
              </h2>
              <p className="leading-relaxed mb-6">
                If you have any questions about these Terms, please contact our Legal Department:
              </p>
              <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                <p className="text-white font-semibold mb-2">NeuroLab Technologies Inc.</p>
                <p className="text-gray-400 text-sm mb-1">Attn: Legal Department</p>
                <p className="text-gray-400 text-sm mb-1">100 Tech Innovation Way, Suite 400</p>
                <p className="text-gray-400 text-sm mb-4">San Francisco, CA 94105, USA</p>
                <p className="text-cyan-400 text-sm font-medium">Email: legal@neurolab.ai</p>
              </div>
            </section>
          </div>
          
        </main>
      </div>
    </div>
  );
}
