import { motion } from 'framer-motion'
import { Zap, Eraser, ImagePlay, LayoutTemplate, Camera, Wrench } from 'lucide-react'

const TOOL_META = {
  'remove-bg':    { label: 'Background Remover', Icon: Eraser,         color: 'text-emerald-400' },
  'change-bg':    { label: 'Change Background',  Icon: ImagePlay,      color: 'text-cyan-400'    },
  'smart-poster': { label: 'Smart Poster',        Icon: LayoutTemplate, color: 'text-violet-400'  },
  'photo-studio': { label: 'Photo Studio',         Icon: Camera,         color: 'text-rose-400'    },
  'image-tools':  { label: 'Image Tools',          Icon: Wrench,         color: 'text-sky-400'     },
}

export default function Navbar({ activeFeature, onNavigate }) {
  const tool = TOOL_META[activeFeature]
  const ToolIcon = tool?.Icon

  return (
    <header className="sticky top-0 z-40">
      <div className="h-px w-full bg-gradient-to-r from-transparent via-violet-500/50 to-transparent" />

      <div className="bg-[#07070e]/92 backdrop-blur-2xl border-b border-white/[0.07]">
        <div className="max-w-6xl mx-auto px-3 sm:px-4 lg:px-6 h-14 sm:h-16 flex items-center justify-between gap-3">

          {/* Logo */}
          <button
            onClick={() => onNavigate('remove-bg')}
            className="flex items-center gap-2.5 shrink-0 group"
          >
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-violet-500/25 group-hover:shadow-violet-500/45 transition-shadow">
              <Zap className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
            </div>
            <div className="leading-none">
              <p className="font-space font-bold text-white text-sm sm:text-[1.05rem] leading-none tracking-tight">
                Pixo<span className="text-violet-400">lab</span>
              </p>
              <p className="text-[10px] text-white/35 leading-none mt-0.5 hidden sm:block tracking-wide">
                pixolab.online
              </p>
            </div>
          </button>

          {/* Active tool indicator — desktop only */}
          {tool && (
            <motion.div
              key={activeFeature}
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.05] border border-white/[0.08]"
            >
              <ToolIcon className={`w-3.5 h-3.5 ${tool.color}`} />
              <span className="text-sm font-semibold text-white/75">{tool.label}</span>
            </motion.div>
          )}

          {/* Free badge */}
          <div className="shrink-0">
            <span className="px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 text-[10px] sm:text-xs font-bold tracking-wide whitespace-nowrap">
              100% FREE
            </span>
          </div>

        </div>
      </div>
    </header>
  )
}
