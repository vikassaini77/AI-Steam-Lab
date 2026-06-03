import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert, ShieldCheck, ArrowLeft, Printer, Download, Menu, X, Camera
} from 'lucide-react';

const sections = [
  { id: 'introduction', title: '1. Introduction & Scope' },
  { id: 'information-collection', title: '2. Information We Collect' },
  { id: 'camera-data', title: '3. Camera & Computer Vision Data' },
  { id: 'how-we-use', title: '4. How We Use Your Information' },
  { id: 'data-sharing', title: '5. Data Sharing & Disclosure' },
  { id: 'cookies', title: '6. Cookies & Tracking Technologies' },
  { id: 'data-security', title: '7. Data Security' },
  { id: 'data-retention', title: '8. Data Retention & Deletion' },
  { id: 'your-rights', title: '9. Your Privacy Rights (GDPR/CCPA)' },
  { id: 'childrens-privacy', title: '10. Children\'s Privacy (COPPA)' },
  { id: 'international-transfers', title: '11. International Data Transfers' },
  { id: 'changes', title: '12. Changes to This Policy' },
  { id: 'contact', title: '13. Contact Us' }
];

export default function PrivacyPage() {
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
    <div className="min-h-screen bg-[#070714] text-gray-300 relative font-sans selection:bg-emerald-500/30 selection:text-emerald-100">
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
                    ? 'bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20' 
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
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider mb-6">
              <ShieldCheck className="w-4 h-4" /> Global Privacy Policy
            </div>
            <h1 className="text-4xl md:text-5xl font-black text-white mb-6 leading-tight tracking-tight">
              NeuroLab AI Privacy Policy
            </h1>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-sm text-gray-400">
              <div>
                <p><strong className="text-gray-300">Last Updated:</strong> June 3, 2026</p>
                <p><strong className="text-gray-300">Effective Date:</strong> June 10, 2026</p>
              </div>
              <div>
                <p><strong className="text-gray-300">Version:</strong> 3.1.0 (Compliance Matrix)</p>
                <p><strong className="text-gray-300">Entity:</strong> NeuroLab Technologies Inc.</p>
              </div>
            </div>
            
            <div className="mt-8 p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-xl flex items-start gap-4">
              <Camera className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-emerald-300 font-bold mb-1">Our Core Camera Promise</h4>
                <p className="text-sm text-gray-400 leading-relaxed">
                  We do not store camera footage. All computer vision processing and AI object detection for our Live Lab runs entirely locally on your device hardware. Your physical environment remains private absolutely.
                </p>
              </div>
            </div>
          </div>

          <div className="prose prose-invert prose-emerald max-w-none space-y-10">
            
            <section id="introduction" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">1.</span> Introduction & Scope
              </h2>
              <p className="leading-relaxed">
                NeuroLab Technologies Inc. ("NeuroLab", "we", "us", or "our") respects your privacy and is deeply committed to protecting your personal data. This Privacy Policy describes how we collect, use, process, and disclose your information, including personal data, in conjunction with your access to and use of the NeuroLab AI platform and services (the "Services").
              </p>
              <p className="leading-relaxed mt-4">
                This policy applies to all visitors, registered users, students, educators, and institutional administrators. By accessing or using the Services, you acknowledge that you have read and understand this Privacy Policy.
              </p>
            </section>

            <section id="information-collection" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">2.</span> Information We Collect
              </h2>
              <h3 className="text-lg font-semibold text-gray-200 mt-6 mb-2">2.1 Information You Provide to Us</h3>
              <ul className="space-y-3 list-none pl-0">
                <li className="pl-4 border-l-2 border-emerald-500/30"><strong className="text-gray-200">Account Data:</strong> Name, email address, username, password (hashed), country, education level, and STEM interests.</li>
                <li className="pl-4 border-l-2 border-emerald-500/30"><strong className="text-gray-200">Profile Data:</strong> Avatar images, biographical information, and other preferences you set in your account profile.</li>
                <li className="pl-4 border-l-2 border-emerald-500/30"><strong className="text-gray-200">Communications:</strong> Support requests, feedback, or any other correspondence you send to us.</li>
              </ul>
              
              <h3 className="text-lg font-semibold text-gray-200 mt-6 mb-2">2.2 Information Collected Automatically</h3>
              <p className="leading-relaxed">
                When you use our Services, we automatically collect certain information about your device and interaction with the platform:
              </p>
              <ul className="space-y-3 list-none pl-0 mt-3">
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">Usage Data:</strong> Pages visited, features accessed, session duration, experiment completion rates, and AI Tutor query histories.</li>
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">Device Information:</strong> IP address, browser type, operating system, device identifiers, and screen resolution.</li>
              </ul>
            </section>

            <section id="camera-data" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">3.</span> Camera & Computer Vision Data
              </h2>
              <p className="leading-relaxed">
                The NeuroLab "Live Lab" feature requires access to your device's camera to track physical experiments (e.g., pendulums, projectiles) in real-time.
              </p>
              <p className="leading-relaxed mt-4">
                <strong>Local Processing:</strong> Video frames are processed entirely locally within your browser using WebRTC and MediaStream APIs. The object detection AI models execute on your device's hardware.
              </p>
              <p className="leading-relaxed mt-4">
                <strong>No Video Transmission:</strong> We NEVER transmit, record, or store video feeds or images on our servers. The only data transmitted to our servers are the numerical outputs of the local computer vision processing (e.g., X/Y coordinates, velocity vectors, and timestamp metrics) necessary to render your experiment data charts and provide AI tutoring.
              </p>
            </section>

            <section id="how-we-use" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">4.</span> How We Use Your Information
              </h2>
              <p className="leading-relaxed mb-4">We use the information we collect for the following business and commercial purposes:</p>
              <ul className="space-y-2 list-disc pl-5 marker:text-emerald-500">
                <li>To provide, maintain, and improve the NeuroLab AI platform.</li>
                <li>To personalize your learning experience and tailor the AI Tutor's responses to your educational level.</li>
                <li>To process payments and manage your premium subscriptions.</li>
                <li>To send administrative notices, technical updates, security alerts, and support messages.</li>
                <li>To analyze usage trends and develop new educational features.</li>
                <li>To protect the safety and security of our users and the integrity of our Services.</li>
              </ul>
            </section>

            <section id="data-sharing" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">5.</span> Data Sharing & Disclosure
              </h2>
              <p className="leading-relaxed">
                NeuroLab does NOT sell your personal data to third parties. We may share your information only in the following limited circumstances:
              </p>
              <ul className="space-y-3 list-none pl-0 mt-4">
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">Service Providers:</strong> We share data with trusted vendors who perform services on our behalf (e.g., cloud hosting via AWS/Supabase, payment processing via Stripe), subject to strict data processing agreements.</li>
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">Educational Institutions:</strong> If you use NeuroLab through a school or enterprise account, your administrators may have access to your learning progress and usage data.</li>
                <li className="pl-4 border-l-2 border-white/10"><strong className="text-gray-200">Legal Compliance:</strong> We may disclose data if required by law, subpoena, or other legal process, or if we believe disclosure is necessary to protect our rights, your safety, or the safety of others.</li>
              </ul>
            </section>

            <section id="cookies" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">6.</span> Cookies & Tracking Technologies
              </h2>
              <p className="leading-relaxed">
                We use cookies, web beacons, local storage, and similar tracking technologies to collect information about your browsing activities. We use:
              </p>
              <ul className="space-y-2 list-disc pl-5 mt-4 marker:text-emerald-500">
                <li><strong>Essential Cookies:</strong> Required for core functionality like authentication and security.</li>
                <li><strong>Functional Cookies:</strong> Remember your preferences, such as theme settings and avatar choices.</li>
                <li><strong>Analytics Cookies:</strong> Help us understand how visitors interact with our platform.</li>
              </ul>
              <p className="leading-relaxed mt-4">
                You can instruct your browser to refuse all cookies or to indicate when a cookie is being sent. However, if you do not accept essential cookies, you may not be able to use some portions of our Services.
              </p>
            </section>

            <section id="data-security" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">7.</span> Data Security
              </h2>
              <p className="leading-relaxed">
                We implement robust technical and organizational measures to protect your data, including AES-256 encryption for data at rest, TLS 1.3 for data in transit, continuous network monitoring, and strict access controls for our personnel. However, no method of transmission over the Internet or method of electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your personal information, we cannot guarantee its absolute security.
              </p>
            </section>

            <section id="data-retention" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">8.</span> Data Retention & Deletion
              </h2>
              <p className="leading-relaxed">
                We retain your personal information for as long as your account is active or as needed to provide you the Services. If you wish to cancel your account or request that we no longer use your information, you may do so via your Account Settings or by contacting us. Upon deletion request, your identifiable data will be permanently deleted from our primary servers within 30 days, and from our secure backups within 90 days.
              </p>
            </section>

            <section id="your-rights" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">9.</span> Your Privacy Rights (GDPR/CCPA)
              </h2>
              <p className="leading-relaxed mb-4">Depending on your location (e.g., the EEA, UK, or California), you may have certain rights regarding your personal data:</p>
              <ul className="space-y-2 list-disc pl-5 marker:text-emerald-500">
                <li><strong>Right to Access:</strong> Request copies of your personal data.</li>
                <li><strong>Right to Rectification:</strong> Request correction of inaccurate data.</li>
                <li><strong>Right to Erasure (Right to be Forgotten):</strong> Request deletion of your personal data.</li>
                <li><strong>Right to Restrict Processing:</strong> Request limitation of how we process your data.</li>
                <li><strong>Right to Data Portability:</strong> Request transfer of your data to another organization.</li>
              </ul>
              <p className="leading-relaxed mt-4">To exercise these rights, please submit a request to privacy@neurolab.ai.</p>
            </section>

            <section id="childrens-privacy" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">10.</span> Children's Privacy (COPPA Compliance)
              </h2>
              <p className="leading-relaxed">
                NeuroLab is designed to be safe for students. We strictly adhere to the Children's Online Privacy Protection Act (COPPA). We do not knowingly collect personal information from children under 13 without verifiable parental consent or authorization from their educational institution. If we become aware that we have collected personal data from a child under 13 without appropriate consent, we will take steps to remove that information and terminate the child's account immediately.
              </p>
            </section>

            <section id="international-transfers" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">11.</span> International Data Transfers
              </h2>
              <p className="leading-relaxed">
                NeuroLab operates globally. Your information may be transferred to, and maintained on, computers located outside of your state, province, country, or other governmental jurisdiction where the data protection laws may differ from those of your jurisdiction. By using the Services, you consent to the transfer of your information to the United States and other regions where we operate, subject to standard contractual clauses or other legally adequate transfer mechanisms.
              </p>
            </section>

            <section id="changes" className="scroll-mt-24">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">12.</span> Changes to This Policy
              </h2>
              <p className="leading-relaxed">
                We may update our Privacy Policy from time to time to reflect changes in our practices or for other operational, legal, or regulatory reasons. We will notify you of any material changes by posting the new Privacy Policy on this page and updating the "Effective Date." We may also provide notice via email or a prominent alert within the platform.
              </p>
            </section>

            <section id="contact" className="scroll-mt-24 mb-32">
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                <span className="text-emerald-500">13.</span> Contact Us
              </h2>
              <p className="leading-relaxed mb-6">
                If you have any questions or concerns about this Privacy Policy or our data practices, please contact our Data Protection Officer:
              </p>
              <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                <p className="text-white font-semibold mb-2">NeuroLab Technologies Inc.</p>
                <p className="text-gray-400 text-sm mb-1">Attn: Data Protection Officer</p>
                <p className="text-gray-400 text-sm mb-1">100 Tech Innovation Way, Suite 400</p>
                <p className="text-gray-400 text-sm mb-4">San Francisco, CA 94105, USA</p>
                <p className="text-emerald-400 text-sm font-medium">Email: privacy@neurolab.ai</p>
              </div>
            </section>
          </div>
          
        </main>
      </div>
    </div>
  );
}
