import { useState, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Wrench, Upload, Download, X, CheckCircle2, Maximize2, Minimize2, Droplets, Type,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

// ── Shared upload zone ────────────────────────────────────────────────────────
function UploadZone({ image, onChange, accentColor = 'sky', inputId = 'tools-input' }) {
  const [drag, setDrag] = useState(false)
  const colorMap = {
    sky: { border: 'border-sky-400', bg: 'bg-sky-400/10', icon: 'text-sky-400', hover: 'hover:border-white/35' },
  }
  const c = colorMap[accentColor] || colorMap.sky

  const process = useCallback(file => {
    if (!file || !file.type.startsWith('image/')) return
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => onChange({ file, preview: url, name: file.name, width: img.width, height: img.height })
    img.src = url
  }, [onChange])

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => { e.preventDefault(); setDrag(false); process(e.dataTransfer.files?.[0]) }}
      onClick={() => !image && document.getElementById(inputId)?.click()}
      className={`relative rounded-2xl border-2 border-dashed transition-all cursor-pointer overflow-hidden
        ${drag ? `${c.border} ${c.bg} scale-[1.01]` : `border-white/20 bg-white/[0.03] hover:bg-white/[0.06] ${c.hover}`}`}
      style={{ minHeight: 200 }}
    >
      <input id={inputId} type="file" accept="image/*" className="hidden"
        onChange={e => { process(e.target.files?.[0]); e.target.value = '' }} />

      {image ? (
        <>
          <img src={image.preview} alt="input" className="w-full h-full object-contain" style={{ maxHeight: 260 }} />
          <button
            onClick={e => { e.stopPropagation(); onChange(null) }}
            className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/70 flex items-center justify-center hover:bg-red-500/80 transition-colors z-10"
          >
            <X className="w-3 h-3 text-white" />
          </button>
          <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-full bg-black/60 text-[10px] text-white/80 truncate max-w-[80%]">
            {image.name} — {image.width}×{image.height}px
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center gap-3 py-12 px-4 text-center h-full">
          <div className={`w-14 h-14 rounded-2xl ${c.bg} border ${c.border}/30 flex items-center justify-center`}>
            <Upload className={`w-6 h-6 ${c.icon}`} />
          </div>
          <div>
            <p className="text-sm font-semibold text-white/80">Drop your image here</p>
            <p className="text-xs text-muted mt-1">or click to browse • PNG, JPG, WEBP</p>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Resize Tool ───────────────────────────────────────────────────────────────
const RESIZE_PRESETS = [
  { label: 'Instagram Square', w: 1080, h: 1080 },
  { label: 'Instagram Portrait', w: 1080, h: 1350 },
  { label: 'Instagram Story', w: 1080, h: 1920 },
  { label: 'YouTube Thumbnail', w: 1280, h: 720 },
  { label: 'LinkedIn Post', w: 1200, h: 627 },
  { label: 'Facebook Cover', w: 1640, h: 624 },
  { label: 'Twitter/X Header', w: 1500, h: 500 },
  { label: 'HD Wallpaper', w: 1920, h: 1080 },
]

function ResizeTool() {
  const [image, setImage] = useState(null)
  const [customW, setCustomW] = useState('')
  const [customH, setCustomH] = useState('')
  const [keepAspect, setKeepAspect] = useState(true)
  const [selectedPreset, setSelectedPreset] = useState(null)
  const [mode, setMode] = useState('preset')   // 'preset' | 'custom'

  const handlePreset = ({ w, h, label }) => {
    setSelectedPreset(label)
    setCustomW(String(w))
    setCustomH(String(h))
  }

  const handleWidthChange = v => {
    setCustomW(v)
    setSelectedPreset(null)
    if (keepAspect && image && v) {
      const ratio = image.height / image.width
      setCustomH(String(Math.round(Number(v) * ratio)))
    }
  }

  const handleHeightChange = v => {
    setCustomH(v)
    setSelectedPreset(null)
    if (keepAspect && image && v) {
      const ratio = image.width / image.height
      setCustomW(String(Math.round(Number(v) * ratio)))
    }
  }

  const handleResize = () => {
    if (!image) return
    const tw = parseInt(customW) || image.width
    const th = parseInt(customH) || image.height
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = tw
      canvas.height = th
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, tw, th)
      canvas.toBlob(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `resized_${tw}x${th}.png`
        a.click()
      }, 'image/png')
    }
    img.src = image.preview
  }

  return (
    <div className="space-y-5">
      <UploadZone image={image} onChange={setImage} inputId="resize-input" />

      {image && (
        <>
          {/* Presets */}
          <div className="space-y-2">
            <p className="text-xs font-semibold text-white/50 uppercase tracking-wider">Presets</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {RESIZE_PRESETS.map(p => (
                <button
                  key={p.label}
                  onClick={() => handlePreset(p)}
                  className={`px-3 py-2 rounded-xl text-left transition-colors border
                    ${selectedPreset === p.label
                      ? 'bg-sky-500/20 border-sky-500/40 text-sky-200'
                      : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10 hover:text-white'
                    }`}
                >
                  <p className="text-xs font-semibold leading-tight">{p.label}</p>
                  <p className="text-[10px] text-white/40 mt-0.5">{p.w}×{p.h}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Custom dimensions */}
          <div className="glass rounded-2xl p-4 space-y-3">
            <p className="text-xs font-semibold text-white/50 uppercase tracking-wider">Custom Size</p>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className="text-xs text-muted block mb-1">Width (px)</label>
                <input
                  type="number"
                  value={customW}
                  onChange={e => handleWidthChange(e.target.value)}
                  placeholder={String(image.width)}
                  className="input-premium w-full"
                />
              </div>
              <span className="text-white/30 mt-4">×</span>
              <div className="flex-1">
                <label className="text-xs text-muted block mb-1">Height (px)</label>
                <input
                  type="number"
                  value={customH}
                  onChange={e => handleHeightChange(e.target.value)}
                  placeholder={String(image.height)}
                  className="input-premium w-full"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 cursor-pointer text-xs text-white/60 hover:text-white transition-colors">
              <div
                onClick={() => setKeepAspect(v => !v)}
                className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-all flex-shrink-0
                  ${keepAspect ? 'bg-sky-500 border-sky-500' : 'border-white/30'}`}
              >
                {keepAspect && <CheckCircle2 className="w-2.5 h-2.5 text-white" />}
              </div>
              Maintain aspect ratio
            </label>
          </div>

          <Button
            onClick={handleResize}
            disabled={!customW && !customH}
            className="w-full gap-2 bg-sky-500 hover:bg-sky-400 text-white font-bold"
          >
            <Maximize2 className="w-4 h-4" />
            Resize & Download PNG
          </Button>
        </>
      )}
    </div>
  )
}

// ── Compress Tool ─────────────────────────────────────────────────────────────
function CompressTool() {
  const [image, setImage] = useState(null)
  const [quality, setQuality] = useState(80)
  const [format, setFormat] = useState('jpeg')

  const handleCompress = () => {
    if (!image) return
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0)
      const mime = format === 'jpeg' ? 'image/jpeg' : format === 'webp' ? 'image/webp' : 'image/png'
      const q = format === 'png' ? undefined : quality / 100
      canvas.toBlob(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `compressed.${format}`
        a.click()
      }, mime, q)
    }
    img.src = image.preview
  }

  return (
    <div className="space-y-5">
      <UploadZone image={image} onChange={setImage} inputId="compress-input" />

      {image && (
        <>
          <div className="glass rounded-2xl p-4 space-y-4">
            {/* Format selector */}
            <div>
              <p className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Output Format</p>
              <div className="flex gap-2">
                {['jpeg', 'webp', 'png'].map(f => (
                  <button
                    key={f}
                    onClick={() => setFormat(f)}
                    className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors border
                      ${format === f
                        ? 'bg-sky-500/20 border-sky-500/40 text-sky-200'
                        : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10 hover:text-white'
                      }`}
                  >
                    {f.toUpperCase()}
                  </button>
                ))}
              </div>
              {format === 'png' && (
                <p className="text-xs text-white/30 mt-2">PNG is lossless — quality slider has no effect</p>
              )}
            </div>

            {/* Quality slider */}
            {format !== 'png' && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white/60 font-semibold">Quality</span>
                  <span className="text-xs text-white/80 font-mono">{quality}%</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={100}
                  value={quality}
                  onChange={e => setQuality(Number(e.target.value))}
                  className="w-full h-1.5 rounded-full accent-sky-400 cursor-pointer"
                  style={{
                    background: `linear-gradient(to right, #38bdf8 0%, #38bdf8 ${quality}%, rgba(255,255,255,0.12) ${quality}%, rgba(255,255,255,0.12) 100%)`
                  }}
                />
                <div className="flex justify-between text-[10px] text-white/30">
                  <span>Smaller file</span>
                  <span>Best quality</span>
                </div>
              </div>
            )}
          </div>

          <Button
            onClick={handleCompress}
            className="w-full gap-2 bg-sky-500 hover:bg-sky-400 text-white font-bold"
          >
            <Minimize2 className="w-4 h-4" />
            Compress & Download {format.toUpperCase()}
          </Button>
        </>
      )}
    </div>
  )
}

// ── Watermark Tool ────────────────────────────────────────────────────────────
const WM_POSITIONS = [
  { id: 'top-left', label: 'Top Left' },
  { id: 'top-right', label: 'Top Right' },
  { id: 'center', label: 'Center' },
  { id: 'bottom-left', label: 'Bottom Left' },
  { id: 'bottom-right', label: 'Bottom Right' },
  { id: 'tiled', label: 'Tiled' },
]

function WatermarkTool() {
  const [image, setImage] = useState(null)
  const [text, setText] = useState('© My Brand')
  const [position, setPosition] = useState('bottom-right')
  const [opacity, setOpacity] = useState(60)
  const [fontSize, setFontSize] = useState(36)
  const [color, setColor] = useState('#ffffff')
  const canvasRef = useRef(null)
  const [preview, setPreview] = useState(null)

  const buildPreview = useCallback(() => {
    if (!image || !text.trim()) return
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0)

      ctx.globalAlpha = opacity / 100
      ctx.fillStyle = color
      ctx.font = `bold ${fontSize}px sans-serif`
      ctx.textBaseline = 'middle'
      const textW = ctx.measureText(text).width
      const pad = 24

      const drawAt = (x, y) => ctx.fillText(text, x, y)

      if (position === 'tiled') {
        const stepX = textW + 80
        const stepY = fontSize * 2.5
        ctx.save()
        ctx.rotate(-Math.PI / 8)
        for (let y = -canvas.height; y < canvas.height * 2; y += stepY) {
          for (let x = -canvas.width; x < canvas.width * 2; x += stepX) {
            drawAt(x, y)
          }
        }
        ctx.restore()
      } else {
        let x, y
        switch (position) {
          case 'top-left':     x = pad; y = pad + fontSize / 2; break
          case 'top-right':    x = img.width - textW - pad; y = pad + fontSize / 2; break
          case 'center':       x = (img.width - textW) / 2; y = img.height / 2; break
          case 'bottom-left':  x = pad; y = img.height - pad - fontSize / 2; break
          case 'bottom-right': x = img.width - textW - pad; y = img.height - pad - fontSize / 2; break
          default:             x = pad; y = pad + fontSize / 2
        }
        drawAt(x, y)
      }
      ctx.globalAlpha = 1

      setPreview(canvas.toDataURL())
    }
    img.src = image.preview
  }, [image, text, position, opacity, fontSize, color])

  // Regenerate preview whenever settings change
  const [debounceTimer, setDebounceTimer] = useState(null)
  const schedulePreview = useCallback(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
    const t = setTimeout(buildPreview, 150)
    setDebounceTimer(t)
  }, [buildPreview, debounceTimer])

  const handleDownload = () => {
    if (!preview) return
    const a = document.createElement('a')
    a.href = preview
    a.download = 'watermarked.png'
    a.click()
  }

  // Rebuild preview when image loads
  const handleImageChange = useCallback(img => {
    setImage(img)
    setPreview(null)
  }, [])

  return (
    <div className="space-y-5">
      <UploadZone image={image} onChange={handleImageChange} inputId="wm-input" />

      {image && (
        <>
          <div className="glass rounded-2xl p-4 space-y-4">
            {/* Text input */}
            <div>
              <label className="text-xs font-semibold text-white/50 uppercase tracking-wider block mb-2">Watermark Text</label>
              <input
                value={text}
                onChange={e => { setText(e.target.value); schedulePreview() }}
                placeholder="© Your Brand"
                className="input-premium w-full"
              />
            </div>

            {/* Position grid */}
            <div>
              <p className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Position</p>
              <div className="grid grid-cols-3 gap-1.5">
                {WM_POSITIONS.map(p => (
                  <button
                    key={p.id}
                    onClick={() => { setPosition(p.id); schedulePreview() }}
                    className={`px-2 py-2 rounded-xl text-xs font-semibold transition-colors border
                      ${position === p.id
                        ? 'bg-sky-500/20 border-sky-500/40 text-sky-200'
                        : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10 hover:text-white'
                      }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Size + Opacity */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-xs text-white/60 font-semibold">Font Size</span>
                  <span className="text-xs font-mono text-white/80">{fontSize}px</span>
                </div>
                <input type="range" min={12} max={120} value={fontSize}
                  onChange={e => { setFontSize(Number(e.target.value)); schedulePreview() }}
                  className="w-full h-1.5 rounded-full accent-sky-400 cursor-pointer"
                  style={{ background: `linear-gradient(to right,#38bdf8 0%,#38bdf8 ${((fontSize-12)/108)*100}%,rgba(255,255,255,0.12) ${((fontSize-12)/108)*100}%,rgba(255,255,255,0.12) 100%)` }} />
              </div>
              <div className="space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-xs text-white/60 font-semibold">Opacity</span>
                  <span className="text-xs font-mono text-white/80">{opacity}%</span>
                </div>
                <input type="range" min={5} max={100} value={opacity}
                  onChange={e => { setOpacity(Number(e.target.value)); schedulePreview() }}
                  className="w-full h-1.5 rounded-full accent-sky-400 cursor-pointer"
                  style={{ background: `linear-gradient(to right,#38bdf8 0%,#38bdf8 ${opacity}%,rgba(255,255,255,0.12) ${opacity}%,rgba(255,255,255,0.12) 100%)` }} />
              </div>
            </div>

            {/* Color picker */}
            <div className="flex items-center gap-3">
              <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">Color</label>
              <input type="color" value={color}
                onChange={e => { setColor(e.target.value); schedulePreview() }}
                className="w-8 h-8 rounded-lg border border-white/20 cursor-pointer bg-transparent" />
              <span className="text-xs font-mono text-white/60">{color}</span>
            </div>
          </div>

          <div className="flex gap-3">
            <Button onClick={buildPreview} variant="outline" className="flex-1 border-white/20 text-white/80 hover:bg-white/8">
              Preview Watermark
            </Button>
            <Button onClick={handleDownload} disabled={!preview}
              className="flex-1 gap-2 bg-sky-500 hover:bg-sky-400 text-white font-bold">
              <Download className="w-4 h-4" /> Download
            </Button>
          </div>

          {preview && (
            <div className="rounded-2xl border border-white/10 overflow-hidden">
              <img src={preview} alt="watermarked preview" className="w-full object-contain" style={{ maxHeight: 360 }} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'resize',    label: 'Resize',    icon: Maximize2,  desc: 'Change dimensions to any preset or custom size' },
  { id: 'compress',  label: 'Compress',  icon: Minimize2,  desc: 'Reduce file size with quality control' },
  { id: 'watermark', label: 'Watermark', icon: Type,       desc: 'Add text watermark with position & opacity control' },
]

export default function ImageTools() {
  const [tab, setTab] = useState('resize')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-xl bg-sky-400/15 flex items-center justify-center">
              <Wrench className="w-4 h-4 text-sky-400" />
            </div>
            <h2 className="font-space text-2xl font-bold">Image Tools</h2>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-sky-400 text-slate-950">FREE</span>
          </div>
          <p className="text-muted text-sm">Resize, compress, and watermark your images — everything runs in your browser.</p>
        </div>
      </div>

      {/* Tab strip */}
      <div className="flex gap-2 p-1 rounded-2xl bg-white/[0.04] border border-white/8 w-fit">
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all
                ${tab === t.id
                  ? 'bg-sky-500/20 text-sky-200 border border-sky-500/30'
                  : 'text-white/50 hover:text-white hover:bg-white/8'
                }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <motion.div
        key={tab}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.15 }}
      >
        {tab === 'resize' && <ResizeTool />}
        {tab === 'compress' && <CompressTool />}
        {tab === 'watermark' && <WatermarkTool />}
      </motion.div>

      {/* Info strip */}
      <div className="flex flex-wrap gap-4 text-xs text-muted">
        {[
          'All processing in your browser',
          'Original file never uploaded to server',
          'No limits — process as many images as you want',
        ].map(t => (
          <span key={t} className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" /> {t}
          </span>
        ))}
      </div>
    </div>
  )
}
