import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutTemplate,
  Sparkles,
  Zap,
  Camera,
  Shield,
  Star,
  ChevronRight,
  Search,
  CheckCircle2,
  ImagePlus,
} from 'lucide-react'
import { api } from '@/lib/api'

const CATEGORIES = ['All', 'Technology', 'Fashion & Lifestyle', 'Beauty', 'Sports & Tech', 'Sports', 'Business']

const TAG_COLORS = {
  'Most Popular': 'bg-amber-400 text-slate-950',
  'Premium': 'bg-purple-400 text-slate-950',
  'Bold': 'bg-red-400 text-white',
  'Trending': 'bg-pink-400 text-white',
  'High Energy': 'bg-orange-400 text-slate-950',
  'B2B': 'bg-blue-400 text-white',
}

const CATEGORY_ICONS = {
  'Technology': Zap,
  'Fashion & Lifestyle': Sparkles,
  'Beauty': Star,
  'Sports & Tech': Shield,
  'Sports': Zap,
  'Business': LayoutTemplate,
}

function TemplatePreviewCard({ template, onSelect }) {
  const [hovered, setHovered] = useState(false)
  const colors = template.preview_colors || ['#050618', '#1a1a3e', '#2a2a5e']
  const accent = template.accent_hex || '#00c8ff'

  const gradient = `linear-gradient(135deg, ${colors[0]} 0%, ${colors[1] || colors[0]} 55%, ${colors[2] || colors[1] || colors[0]} 100%)`
  const tagClass = TAG_COLORS[template.tag] || 'bg-white/20 text-white'
  const CategoryIcon = CATEGORY_ICONS[template.category] || LayoutTemplate

  const hasFeatures = template.fields?.some(f => f.group === 'features')

  return (
    <motion.div
      whileHover={{ y: -6, scale: 1.015 }}
      whileTap={{ scale: 0.98 }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      className="rounded-2xl overflow-hidden border border-white/10 cursor-pointer group relative"
      style={{ background: 'rgba(255,255,255,0.04)' }}
      onClick={() => onSelect(template)}
    >
      {/* Template visual preview */}
      <div
        className="relative overflow-hidden"
        style={{
          background: gradient,
          height: 200,
          aspectRatio: template.dimensions ? `${template.dimensions[0]} / ${template.dimensions[1]}` : '1/1',
          maxHeight: 200,
        }}
      >
        {/* Decorative glow */}
        <div
          className="absolute inset-0 opacity-40"
          style={{
            background: `radial-gradient(ellipse at 65% 35%, ${accent}44 0%, transparent 65%)`,
          }}
        />

        {/* Layout mockup elements */}
        <div className="absolute inset-0 p-3 flex flex-col justify-between">
          {/* Top text area mockup */}
          <div className="space-y-1.5">
            {/* Brand badge */}
            <div
              className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold"
              style={{ background: accent, color: '#0a0a1a' }}
            >
              {template.name.split(' ')[0].toUpperCase()}
            </div>
            {/* Headline bars */}
            <div className="space-y-1">
              <div className="h-2.5 rounded w-4/5 opacity-90" style={{ background: 'rgba(255,255,255,0.85)' }} />
              <div className="h-2 rounded w-3/5 opacity-60" style={{ background: 'rgba(255,255,255,0.6)' }} />
            </div>
          </div>

          {/* Person silhouette placeholder */}
          <div className="absolute left-2 bottom-0 w-16 h-28 opacity-20 rounded-t-full" style={{ background: 'rgba(255,255,255,0.5)' }} />

          {/* Product placeholder */}
          <div className="absolute right-4 bottom-8 w-10 h-16 opacity-25 rounded-lg" style={{ background: accent }} />

          {/* Feature bar mockup (for templates that have features) */}
          {hasFeatures && (
            <div
              className="absolute bottom-0 left-0 right-0 h-8 flex items-center justify-around px-2"
              style={{ background: 'rgba(0,0,0,0.55)', borderTop: `1px solid ${accent}55` }}
            >
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex flex-col items-center gap-0.5">
                  <div className="w-2 h-2 rounded-full border opacity-70" style={{ borderColor: accent }} />
                  <div className="h-1 w-8 rounded opacity-50" style={{ background: 'rgba(255,255,255,0.5)' }} />
                </div>
              ))}
            </div>
          )}

          {/* CTA mockup */}
          {!hasFeatures && (
            <div
              className="self-start px-3 py-1 rounded-full text-[9px] font-bold"
              style={{ background: accent, color: '#0a0a1a' }}
            >
              {(template.fields?.find(f => f.key === 'cta')?.placeholder || 'Action')}
            </div>
          )}
        </div>

        {/* Hover overlay */}
        <AnimatePresence>
          {hovered && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex items-center justify-center"
              style={{ background: 'rgba(0,0,0,0.55)' }}
            >
              <motion.div
                initial={{ scale: 0.8 }}
                animate={{ scale: 1 }}
                className="flex items-center gap-2 px-4 py-2 rounded-full font-bold text-sm text-slate-950"
                style={{ background: accent }}
              >
                <CheckCircle2 className="w-4 h-4" /> Use Template
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Card info */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${tagClass}`}>
                {template.tag}
              </span>
              <span className="text-[10px] text-white/40 flex items-center gap-1">
                <CategoryIcon className="w-3 h-3" /> {template.category}
              </span>
            </div>
            <h3 className="font-space font-bold text-base text-white leading-tight">{template.name}</h3>
          </div>
        </div>

        <p className="text-xs text-white/55 leading-relaxed mb-3">{template.description}</p>

        {/* Required inputs summary */}
        <div className="flex items-center gap-2 flex-wrap">
          {template.required_images?.map(img => (
            <span key={img.key} className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-white/8 text-white/60">
              <ImagePlus className="w-2.5 h-2.5" /> {img.label}
            </span>
          ))}
          <span className="text-[10px] text-white/35">
            {template.fields?.length} fields
          </span>
        </div>
      </div>

      {/* Hover border accent */}
      <motion.div
        className="absolute inset-0 rounded-2xl pointer-events-none border-2 opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ borderColor: accent }}
      />
    </motion.div>
  )
}

export default function TemplateGallery({ onSelectTemplate }) {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeCategory, setActiveCategory] = useState('All')
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.templates()
      .then(data => setTemplates(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = templates.filter(t => {
    const matchCat = activeCategory === 'All' || t.category === activeCategory
    const q = search.toLowerCase()
    const matchSearch = !q || t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q) || t.category.toLowerCase().includes(q)
    return matchCat && matchSearch
  })

  const existingCategories = ['All', ...new Set(templates.map(t => t.category))]

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}>
            <Sparkles className="w-8 h-8 text-primary" />
          </motion.div>
          <p className="text-muted text-sm">Loading templates…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-200 text-sm text-center">
        Failed to load templates: {error}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <LayoutTemplate className="w-5 h-5 text-primary" />
          <h2 className="font-space text-xl font-bold">Choose a Template</h2>
        </div>
        <p className="text-muted text-sm">Select a professionally designed template, then fill in your images and text.</p>
      </div>

      {/* Search + Category filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search templates…"
            className="input-premium pl-9 w-full"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {existingCategories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                activeCategory === cat
                  ? 'bg-primary text-white shadow-lg shadow-primary/30'
                  : 'bg-white/8 text-white/60 hover:bg-white/14'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Template grid */}
      <AnimatePresence mode="wait">
        {filtered.length === 0 ? (
          <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-12 text-center text-muted text-sm">
            No templates match your filter.
          </motion.div>
        ) : (
          <motion.div
            key={activeCategory + search}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5"
          >
            {filtered.map((template, idx) => (
              <motion.div
                key={template.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
              >
                <TemplatePreviewCard template={template} onSelect={onSelectTemplate} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom hint */}
      <div className="flex items-center gap-2 text-xs text-muted justify-center pb-2">
        <ChevronRight className="w-3 h-3" />
        All templates are free · No account required · Instant download
      </div>
    </div>
  )
}
