import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ImagePlay, Upload, Download, X, CheckCircle2,
  Sparkles, Palette, Image as ImageIcon, Wand2, RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

const PRESET_COLORS = [
  { label: 'Deep Space',   hex: '#090914' },
  { label: 'Ocean Blue',   hex: '#0a1628' },
  { label: 'Forest',       hex: '#0a1a0f' },
  { label: 'Sunset',       hex: '#1a0a14' },
  { label: 'Pure White',   hex: '#f8f9fa' },
  { label: 'Studio Gray',  hex: '#2d2d2d' },
  { label: 'Warm Cream',   hex: '#faf3e0' },
  { label: 'Midnight',     hex: '#0d0d1a' },
]

const BG_MODES = [
  { id: 'upload', label: 'Upload BG',      icon: ImageIcon, desc: 'Use your own background image' },
  { id: 'color',  label: 'Solid Colour',   icon: Palette,   desc: 'Pick any colour as background'  },
  { id: 'ai',     label: 'AI Background',  icon: Wand2,     desc: 'Generate with FLUX AI'          },
]

function UploadZone({ id, image, onChange, label, accent = 'cyan' }) {
  const [drag, setDrag] = useState(false)
  const colors = {
    cyan:   { border: 'border-cyan-400/50',   bg: 'bg-cyan-400/8',   icon: 'text-cyan-400'   },
    violet: { border: 'border-violet-400/50', bg: 'bg-violet-400/8', icon: 'text-violet-400' },
  }
  const c = colors[accent] || colors.cyan

  const process = useCallback(file => {
    if (!file || !file.type.startsWith('image/')) return
    onChange({ file, preview: URL.createObjectURL(file), name: file.name })
  }, [onChange])

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => { e.preventDefault(); setDrag(false); process(e.dataTransfer.files?.[0]) }}
      onClick={() => !image && document.getElementById(id)?.click()}
      className={`relative rounded-2xl border-2 border-dashed transition-all overflow-hidden cursor-pointer
        ${drag ? `${c.border} ${c.bg}` : 'border-white/15 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/28'}`}
      style={{ minHeight: 200 }}
    >
      <input id={id} type="file" accept="image/*" className="hidden"
        onChange={e => { process(e.target.files?.[0]); e.target.value = '' }} />
      {image ? (
        <>
          <img src={image.preview} alt={label} className="w-full h-full object-cover" style={{ maxHeight: 220 }} />
          <button onClick={e => { e.stopPropagation(); onChange(null) }}
            className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/70 flex items-center justify-center hover:bg-red-500/80 transition-colors">
            <X className="w-3 h-3 text-white" />
          </button>
          <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-full bg-black/60 text-[10px] text-white/80 truncate max-w-[75%]">{label}</div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center gap-2 py-10 px-4 text-center">
          <div className={`w-12 h-12 rounded-2xl ${c.bg} border border-white/10 flex items-center justify-center`}>
            <Upload className={`w-5 h-5 ${c.icon}`} />
          </div>
          <div>
            <p className="text-sm font-semibold text-white/70">{label}</p>
            <p className="text-xs text-white/35 mt-0.5">Drop or click to upload</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChangeBackground() {
  const [subject, setSubject]         = useState(null)
  const [bgImage, setBgImage]         = useState(null)
  const [bgMode, setBgMode]           = useState('upload')
  const [bgColor, setBgColor]         = useState('#090914')
  const [aiPrompt, setAiPrompt]       = useState('')
  const [resultUrl, setResultUrl]     = useState(null)
  const [resultBlob, setResultBlob]   = useState(null)
  const [processing, setProcessing]   = useState(false)
  const [error, setError]             = useState(null)

  const canGenerate = subject && !processing &&
    (bgMode === 'color' ||
     (bgMode === 'upload' && bgImage) ||
     (bgMode === 'ai' && aiPrompt.trim()))

  const handleGenerate = async () => {
    setProcessing(true)
    setError(null)
    setResultUrl(null)
    try {
      const form = new FormData()
      form.append('subject_image', subject.file)
      if (bgMode === 'upload' && bgImage) form.append('background_image', bgImage.file)
      form.append('bg_color', bgColor)
      form.append('bg_prompt', bgMode === 'ai' ? aiPrompt : '')
      form.append('use_ai', bgMode === 'ai' ? 'true' : 'false')

      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
      const res = await fetch(`${API_URL}/tools/change-background`, { method: 'POST', body: form })
      if (!res.ok) {
        const ct = res.headers.get('content-type') || ''
        const body = ct.includes('json') ? await res.json() : await res.text()
        throw new Error(body?.detail || body || 'Generation failed')
      }
      const blob = await res.blob()
      setResultBlob(blob)
      setResultUrl(URL.createObjectURL(blob))
    } catch (err) {
      setError(err.message)
    } finally {
      setProcessing(false)
    }
  }

  const handleDownload = () => {
    if (!resultBlob) return
    const url = URL.createObjectURL(resultBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'changed_bg.jpg'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="w-8 h-8 rounded-xl bg-cyan-400/15 flex items-center justify-center shrink-0">
          <ImagePlay className="w-4 h-4 text-cyan-400" />
        </div>
        <h2 className="font-space text-xl sm:text-2xl font-bold">Change Background</h2>
        <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-cyan-400 text-slate-950">FREE</span>
      </div>
      <p className="text-muted text-sm -mt-3">Upload your subject, then choose or generate a new background.</p>

      <div className="grid xl:grid-cols-[1fr_340px] gap-5 xl:gap-6 items-start">
        <div className="space-y-4 sm:space-y-5">

          {/* Step 1 */}
          <div className="glass rounded-2xl sm:rounded-3xl p-4 sm:p-5">
            <h3 className="font-space font-bold text-sm mb-1 flex items-center gap-2">
              <span className="step-badge">1</span> Upload Your Subject
            </h3>
            <p className="text-xs text-muted mb-4">Person, product or any subject — background is removed automatically.</p>
            <UploadZone id="subject-upload" image={subject} onChange={setSubject} label="Subject Image" accent="cyan" />
          </div>

          {/* Step 2 */}
          <div className="glass rounded-2xl sm:rounded-3xl p-4 sm:p-5">
            <h3 className="font-space font-bold text-sm mb-1 flex items-center gap-2">
              <span className="step-badge">2</span> Choose Background Type
            </h3>
            <p className="text-xs text-muted mb-4">Upload your own, pick a colour, or generate one with AI.</p>

            {/* Mode selector */}
            <div className="grid grid-cols-3 gap-2 sm:gap-3 mb-5">
              {BG_MODES.map(m => {
                const Icon = m.icon
                const active = bgMode === m.id
                return (
                  <button
                    key={m.id}
                    onClick={() => setBgMode(m.id)}
                    className={`relative flex flex-col items-center gap-1.5 sm:gap-2 p-2.5 sm:p-3 rounded-xl sm:rounded-2xl border text-center transition-all
                      ${active
                        ? 'border-cyan-400/60 bg-cyan-400/10 shadow-[0_0_20px_rgba(34,211,238,0.12)]'
                        : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.07]'}`}
                  >
                    <div className={`w-7 h-7 sm:w-8 sm:h-8 rounded-xl flex items-center justify-center ${active ? 'bg-cyan-400/20' : 'bg-white/8'}`}>
                      <Icon className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${active ? 'text-cyan-400' : 'text-white/50'}`} />
                    </div>
                    <p className="text-[10px] sm:text-xs font-bold leading-tight">{m.label}</p>
                  </button>
                )
              })}
            </div>

            <AnimatePresence mode="wait">
              {bgMode === 'upload' && (
                <motion.div key="upload" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
                  <UploadZone id="bg-upload" image={bgImage} onChange={setBgImage} label="Background Image" accent="violet" />
                </motion.div>
              )}

              {bgMode === 'color' && (
                <motion.div key="color" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="space-y-3">
                  <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
                    {PRESET_COLORS.map(c => (
                      <button
                        key={c.hex}
                        onClick={() => setBgColor(c.hex)}
                        title={c.label}
                        className={`h-10 sm:h-12 rounded-xl border-2 transition-all ${bgColor === c.hex ? 'border-white/70 scale-110 shadow-lg' : 'border-transparent hover:border-white/30'}`}
                        style={{ backgroundColor: c.hex }}
                      />
                    ))}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <label className="text-xs text-muted">Custom:</label>
                    <input type="color" value={bgColor} onChange={e => setBgColor(e.target.value)}
                      className="w-9 h-8 rounded-lg border border-white/20 cursor-pointer bg-transparent" />
                    <span className="text-xs text-white/50 font-mono">{bgColor}</span>
                  </div>
                </motion.div>
              )}

              {bgMode === 'ai' && (
                <motion.div key="ai" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="space-y-3">
                  <label className="block">
                    <span className="text-sm font-semibold text-white/80 mb-2 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-cyan-400" /> Describe your background
                    </span>
                    <textarea
                      value={aiPrompt}
                      onChange={e => setAiPrompt(e.target.value)}
                      placeholder="e.g. Futuristic neon city at night, rain-slicked streets, blue tones"
                      className="input-premium w-full resize-none"
                      rows={3}
                    />
                  </label>
                  <p className="text-xs text-muted flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3 text-cyan-400" />
                    Generated by FLUX.1 · free, no account needed
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Generate */}
          <Button
            size="lg"
            disabled={!canGenerate}
            onClick={handleGenerate}
            className="w-full gap-2 py-5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-base"
          >
            {processing
              ? <><motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}><ImagePlay className="w-5 h-5" /></motion.div> Processing…</>
              : <><ImagePlay className="w-5 h-5" /> Apply Background</>
            }
          </Button>

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-200 text-sm">{error}</div>
          )}
        </div>

        {/* Result panel */}
        <div className="space-y-3 xl:sticky xl:top-6">
          <p className="text-xs font-semibold text-white/40 uppercase tracking-wider">Result</p>
          <div className="rounded-2xl sm:rounded-3xl border border-white/10 bg-white/[0.03] overflow-hidden" style={{ minHeight: 240 }}>
            <AnimatePresence mode="wait">
              {processing ? (
                <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center gap-3 py-16 text-center">
                  <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}>
                    <ImagePlay className="w-8 h-8 text-cyan-400" />
                  </motion.div>
                  <p className="text-sm font-semibold">Processing…</p>
                  <p className="text-xs text-muted">Removing BG + compositing</p>
                </motion.div>
              ) : resultUrl ? (
                <motion.div key="result" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}>
                  <img src={resultUrl} alt="result" className="w-full object-contain rounded-t-2xl sm:rounded-t-3xl" style={{ maxHeight: 320 }} />
                  <div className="p-4 flex items-center gap-3 border-t border-white/10">
                    <CheckCircle2 className="w-5 h-5 text-cyan-400 shrink-0" />
                    <span className="text-sm text-cyan-300 font-semibold flex-1">Done!</span>
                    <button onClick={() => { setResultUrl(null); setResultBlob(null) }}
                      className="text-xs text-muted hover:text-white flex items-center gap-1 transition-colors">
                      <RefreshCw className="w-3.5 h-3.5" /> Redo
                    </button>
                    <Button size="sm" onClick={handleDownload}
                      className="gap-1.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold">
                      <Download className="w-4 h-4" /> Download
                    </Button>
                  </div>
                </motion.div>
              ) : (
                <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center gap-2 py-16 text-center">
                  <ImagePlay className="w-8 h-8 text-white/12" />
                  <p className="text-white/25 text-sm">Result will appear here</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="text-xs text-muted space-y-1.5">
            {['Upload BG — free', 'Solid colour — free', 'AI Background — free'].map(t => (
              <div key={t} className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" /> {t}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
