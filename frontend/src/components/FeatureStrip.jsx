import { motion } from 'framer-motion'
import { Eraser, ImagePlay, LayoutTemplate, Camera, Wrench } from 'lucide-react'

export const FEATURES = [
  {
    id: 'remove-bg',
    label: 'Background Remover',
    shortLabel: 'Remove BG',
    icon: Eraser,
    badge: 'FREE',
    badgeColor: 'bg-emerald-400 text-slate-950',
    desc: 'Erase any background instantly',
    gradient: 'from-emerald-950/80 via-teal-950/60 to-emerald-950/40',
    glow: 'rgba(52,211,153,0.22)',
    activeGlow: 'rgba(52,211,153,0.85)',
    iconBg: 'bg-emerald-400/15',
    iconColor: 'text-emerald-400',
    border: 'border-emerald-500/40',
  },
  {
    id: 'change-bg',
    label: 'Change Background',
    shortLabel: 'Change BG',
    icon: ImagePlay,
    badge: 'FREE',
    badgeColor: 'bg-cyan-400 text-slate-950',
    desc: 'Swap background with any image',
    gradient: 'from-cyan-950/80 via-blue-950/60 to-cyan-950/40',
    glow: 'rgba(34,211,238,0.22)',
    activeGlow: 'rgba(34,211,238,0.85)',
    iconBg: 'bg-cyan-400/15',
    iconColor: 'text-cyan-400',
    border: 'border-cyan-500/40',
  },
  {
    id: 'smart-poster',
    label: 'Smart Poster',
    shortLabel: 'Poster',
    icon: LayoutTemplate,
    badge: 'FREE',
    badgeColor: 'bg-violet-400 text-white',
    desc: 'Professional ad templates',
    gradient: 'from-violet-950/80 via-purple-950/60 to-violet-950/40',
    glow: 'rgba(167,139,250,0.22)',
    activeGlow: 'rgba(167,139,250,0.85)',
    iconBg: 'bg-violet-400/15',
    iconColor: 'text-violet-400',
    border: 'border-violet-500/40',
  },
  {
    id: 'photo-studio',
    label: 'Photo Studio',
    shortLabel: 'Studio',
    icon: Camera,
    badge: 'FREE',
    badgeColor: 'bg-rose-400 text-white',
    desc: 'Filters, adjustments & effects',
    gradient: 'from-rose-950/80 via-pink-950/60 to-rose-950/40',
    glow: 'rgba(251,113,133,0.22)',
    activeGlow: 'rgba(251,113,133,0.85)',
    iconBg: 'bg-rose-400/15',
    iconColor: 'text-rose-400',
    border: 'border-rose-500/40',
  },
  {
    id: 'image-tools',
    label: 'Image Tools',
    shortLabel: 'Tools',
    icon: Wrench,
    badge: 'FREE',
    badgeColor: 'bg-sky-400 text-slate-950',
    desc: 'Resize, compress & watermark',
    gradient: 'from-sky-950/80 via-blue-950/60 to-sky-950/40',
    glow: 'rgba(56,189,248,0.22)',
    activeGlow: 'rgba(56,189,248,0.85)',
    iconBg: 'bg-sky-400/15',
    iconColor: 'text-sky-400',
    border: 'border-sky-500/40',
  },
]

export default function FeatureStrip({ active, onSelect }) {
  return (
    <div className="w-full">
      {/* ── Mobile: horizontal scrollable pill tabs ── */}
      <div className="flex sm:hidden gap-2 overflow-x-auto pb-1 no-scrollbar px-0.5">
        {FEATURES.map(f => {
          const Icon = f.icon
          const isActive = active === f.id
          return (
            <button
              key={f.id}
              onClick={() => onSelect(f.id)}
              className={`flex items-center gap-1.5 px-3 py-2.5 rounded-2xl border whitespace-nowrap text-sm font-semibold transition-all shrink-0
                ${isActive
                  ? `${f.iconBg} ${f.border} text-white shadow-lg`
                  : 'bg-white/[0.04] border-white/[0.07] text-white/55 hover:text-white/80 hover:bg-white/[0.07]'
                }`}
              style={isActive ? { boxShadow: `0 0 20px ${f.glow}` } : {}}
            >
              <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? f.iconColor : 'text-white/40'}`} />
              <span>{f.shortLabel}</span>
            </button>
          )
        })}
      </div>

      {/* ── Tablet: compact 5-col row ── */}
      <div className="hidden sm:grid lg:hidden grid-cols-5 gap-2">
        {FEATURES.map((f, i) => {
          const Icon = f.icon
          const isActive = active === f.id
          return (
            <motion.button
              key={f.id}
              whileTap={{ scale: 0.96 }}
              onClick={() => onSelect(f.id)}
              className={`relative flex flex-col items-center gap-1.5 p-3 rounded-2xl border text-center transition-all
                bg-gradient-to-b ${f.gradient}
                ${isActive ? `${f.border} shadow-lg` : 'border-white/[0.07] hover:border-white/[0.14]'}`}
              style={isActive ? { boxShadow: `0 0 24px ${f.glow}, 0 4px 16px rgba(0,0,0,0.3)` } : {}}
            >
              {isActive && (
                <motion.div layoutId="tab-bar-sm"
                  className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
                  style={{ background: f.activeGlow }} />
              )}
              <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${isActive ? f.iconBg : 'bg-white/[0.06]'}`}>
                <Icon className={`w-4 h-4 ${isActive ? f.iconColor : 'text-white/45'}`} />
              </div>
              <span className={`text-xs font-bold leading-tight ${isActive ? 'text-white' : 'text-white/55'}`}>
                {f.shortLabel}
              </span>
            </motion.button>
          )
        })}
      </div>

      {/* ── Desktop: full feature cards ── */}
      <div className="hidden lg:grid grid-cols-5 gap-3">
        {FEATURES.map((f, i) => {
          const Icon = f.icon
          const isActive = active === f.id
          return (
            <motion.button
              key={f.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ y: -4 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => onSelect(f.id)}
              className={`relative flex flex-col items-start gap-2.5 p-4 rounded-2xl border text-left transition-all duration-200 cursor-pointer
                bg-gradient-to-br ${f.gradient}
                ${isActive ? `${f.border} shadow-2xl` : 'border-white/[0.07] hover:border-white/[0.16]'}`}
              style={isActive ? { boxShadow: `0 0 36px ${f.glow}, 0 6px 28px rgba(0,0,0,0.4)` } : {}}
            >
              {isActive && (
                <motion.div
                  layoutId="feature-active-bar"
                  className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
                  style={{ background: f.activeGlow }}
                />
              )}

              <div className="flex items-center justify-between w-full">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${isActive ? f.iconBg : 'bg-white/[0.06]'}`}>
                  <Icon className={`w-5 h-5 ${isActive ? f.iconColor : 'text-white/45'}`} />
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${f.badgeColor}`}>
                  {f.badge}
                </span>
              </div>

              <div>
                <p className={`font-space font-bold text-sm leading-tight ${isActive ? 'text-white' : 'text-white/80'}`}>
                  {f.label}
                </p>
                <p className="text-[11px] text-white/38 mt-0.5 leading-snug">
                  {f.desc}
                </p>
              </div>
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
