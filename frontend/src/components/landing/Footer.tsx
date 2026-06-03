import { motion } from 'framer-motion';
import { Heart, Github, Twitter, Linkedin, ExternalLink, Shield, Lock, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Footer() {
  const navigate = useNavigate();

  const columns = [
    {
      heading: 'Product',
      links: [
        { label: 'Features', route: '/features' },
        { label: 'Live Lab', route: '/live-lab' },
        { label: 'AI Tutor', route: '/ai-tutor' },
        { label: 'Pricing', route: '/pricing' },
        { label: 'Documentation', route: '/docs' },
      ],
    },
    {
      heading: 'Company',
      links: [
        { label: 'About', route: '/about' },
        { label: 'Contact', route: '/contact' },
        { label: 'Careers', route: '/careers' },
        { label: 'Blog', route: '/blog' },
        { label: 'GitHub', href: 'https://github.com/vikassaini77', external: true },
      ],
    },
    {
      heading: 'Legal & Trust',
      links: [
        { label: 'Privacy Policy', route: '/privacy' },
        { label: 'Terms & Conditions', route: '/terms' },
        { label: 'Security Center', route: '/security' },
        { label: 'Trust Center', route: '/trust' },
        { label: 'Cookie Settings', route: '/cookies' },
      ],
    },
  ];

  const socials = [
    { 
      icon: Github, 
      href: 'https://github.com/vikassaini77', 
      label: 'GitHub Profile (vikassaini77)' 
    },
    { 
      icon: Twitter, 
      href: 'https://twitter.com', 
      label: 'Twitter Feed' 
    },
    { 
      icon: Linkedin, 
      href: 'https://www.linkedin.com/in/vikas-saini1/', 
      label: 'LinkedIn Profile (Vikas Saini)' 
    },
  ];

  const trustBadges = [
    { icon: '🔒', label: 'E2E Encrypted' },
    { icon: '🛡️', label: 'Secure Auth' },
    { icon: '🔐', label: 'Privacy Protected' },
    { icon: '✅', label: 'Verified Platform' },
  ];

  return (
    <footer className="relative bg-[#050511] border-t border-white/[0.07]">
      {/* Top divider glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-px bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent" />

      <div className="container mx-auto px-6 py-14">

        {/* Trust badges row */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="flex flex-wrap items-center justify-center gap-4 mb-12 pb-8 border-b border-white/[0.06]"
        >
          <span className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Trusted & Secure</span>
          {trustBadges.map((b) => (
            <div key={b.label} className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.03] border border-white/[0.07] rounded-full">
              <span>{b.icon}</span>
              <span className="text-gray-400 text-xs font-medium">{b.label}</span>
            </div>
          ))}
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 mb-12 text-left">

          {/* Brand column */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="md:col-span-1"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/25 overflow-hidden bg-[#050511]">
                <img src="/logo.png" alt="NeuroLab Logo" className="w-full h-full object-cover" />
              </div>
              <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
                NeuroLab AI
              </span>
            </div>
            <p className="text-gray-500 text-sm leading-relaxed mb-5">
              AI-powered STEM learning platform for the next generation of scientists, engineers, and innovators.
            </p>

            {/* Social links with tab targeting and interactive tooltips */}
            <div className="flex gap-3">
              {socials.map((social) => (
                <motion.a
                  key={social.label}
                  href={social.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  whileHover={{ scale: 1.1, y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  title={social.label}
                  aria-label={social.label}
                  className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-gray-500 hover:text-cyan-400 hover:border-cyan-500/30 hover:bg-cyan-500/5 transition-all cursor-pointer"
                >
                  <social.icon className="w-4 h-4" />
                </motion.a>
              ))}
            </div>
          </motion.div>

          {/* Link columns */}
          {columns.map((col, colIdx) => (
            <motion.div
              key={col.heading}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: (colIdx + 1) * 0.08 }}
            >
              <h4 className="text-white font-bold text-sm mb-4 tracking-wide">{col.heading}</h4>
              <ul className="space-y-2.5">
                {col.links.map((link) => (
                  <li key={link.label}>
                    {link.route ? (
                      <button
                        onClick={() => navigate(link.route!)}
                        className="text-gray-500 hover:text-cyan-400 transition-all text-sm flex items-center gap-1 group w-full text-left"
                      >
                        <span>{link.label}</span>
                        <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 -translate-x-1 group-hover:translate-x-0 transition-all text-cyan-400" />
                      </button>
                    ) : (
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-500 hover:text-cyan-400 transition-all text-sm flex items-center gap-1 group"
                      >
                        <span>{link.label}</span>
                        {link.external && <ExternalLink className="w-3 h-3 text-gray-600 group-hover:text-cyan-400 transition-colors" />}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>

        {/* Bottom bar */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="pt-6 border-t border-white/[0.06] flex flex-col sm:flex-row items-center justify-between gap-4"
        >
          <p className="text-gray-600 text-xs">
            © 2026 NeuroLab AI. All rights reserved.
          </p>

          <div className="flex items-center gap-4">
            <p className="text-gray-600 text-xs flex items-center gap-1.5">
              Made with <Heart className="w-3.5 h-3.5 text-red-500" /> for future scientists
            </p>
            <div className="flex items-center gap-1.5 text-gray-600 text-xs">
              <Lock className="w-3 h-3 text-emerald-500" />
              <span>Secure & Private</span>
            </div>
          </div>
        </motion.div>
      </div>
    </footer>
  );
}
