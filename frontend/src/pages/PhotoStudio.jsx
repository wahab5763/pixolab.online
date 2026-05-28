import { useState, useRef, useCallback, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Camera, Upload, Download, X, RotateCcw, FlipHorizontal, FlipVertical,
  SlidersHorizontal, RefreshCw, CheckCircle2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

// ── Filter presets ────────────────────────────────────────────────────────────
const PRESETS = [
  { id: 'normal',  label: 'Normal',  css: 'none' },
  { id: 'vivid',   label: 'Vivid',   css: 'saturate(1.6) contrast(1.1)' },
  { id: 'warm',    label: 'Warm',    css: 'sepia(0.35) saturate(1.2) brightness(1.05)' },
  { id: 'cool',    label: 'Cool',    css: 'hue-rotate(20deg) saturate(1.1) brightness(1.02)' },
  { id: 'bw',      label: 'B&W',     css: 'grayscale(1)' },
  { id: 'sepia',   label: 'Sepia',   css: 'sepia(0.85)' },
  { id: 'vintage', label: 'Vintage', css: 'sepia(0.4) contrast(0.85) brightness(0.9) saturate(0.8)' },
  { id: 'fade',    label: 'Fade',    css: 'contrast(0.75) brightness(1.1) saturate(0.75)' },
  { id: 'drama',   label: 'Drama',   css: 'contrast(1.35) brightness(0.85) saturate(1.1)' },
  { id: 'golden',  label: 'Golden',  css: 'sepia(0.5) saturate(1.4) brightness(1.08) hue-rotate(-10deg)' },
]

const DEFAULT_ADJUSTMENTS = {
  brightness: 100,
  contrast: 100,
  saturation: 100,
  sharpness: 0,   // we simulate sharpness with contrast boost
  blur: 0,
}

function buildFilterString(adj, presetCss) {
  const parts = [
    `brightness(${adj.brightness / 100})`,
    `contrast(${adj.contrast / 100})`,
    `saturate(${adj.saturation / 100})`,
    adj.blur > 0 ? `blur(${adj.blur * 0.06}px)` : '',
  ].filter(Boolean).join(' ')

  if (presetCss && presetCss !== 'none') return `${parts} ${presetCss}`
  return parts
}

// Slider component
function AdjustSlider({ label, value, min, max, onChange, unit = '%' }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-white/60 font-semibold">{label}</span>
        <span className="text-xs text-white/80 font-mono">{value}{unit}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full accent-primary cursor-pointer"
        style={{
          background: `linear-gradient(to right, var(--primary) 0%, var(--primary) ${((value - min) / (max - min)) * 100}%, rgba(255,255,255,0.12) ${((value - min) / (max - min)) * 100}%, rgba(255,255,255,0.12) 100%)`
        }}
      />
    </div>
  )
}

export default function PhotoStudio() {
  const [image, setImage] = useState(null)    // { file, preview, name, width, height }
  const [adj, setAdj] = useState(DEFAULT_ADJUSTMENTS)
  const [preset, setPreset] = useState('normal')
  const [rotation, setRotation] = useState(0)
  const [flipH, setFlipH] = useState(false)
  const [flipV, setFlipV] = useState(false)
  const [drag, setDrag] = useState(false)

  const canvasRef = useRef(null)

  const processFile = useCallback(file => {
    if (!file || !file.type.startsWith('image/')) return
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      setImage({ file, preview: url, name: file.name, width: img.width, height: img.height })
    }
    img.src = url
  }, [])

  const presetCss = PRESETS.find(p => p.id === preset)?.css || 'none'
  const liveFilter = buildFilterString(adj, presetCss)

  const imgStyle = {
    filter: liveFilter,
    transform: `rotate(${rotation}deg) scaleX(${flipH ? -1 : 1}) scaleY(${flipV ? -1 : 1})`,
    transition: 'filter 0.1s, transform 0.15s',
  }

  const resetAll = () => {
    setAdj(DEFAULT_ADJUSTMENTS)
    setPreset('normal')
    setRotation(0)
    setFlipH(false)
    setFlipV(false)
  }

  // Download: render to canvas with filters applied
  const handleDownload = useCallback((fmt = 'png') => {
    if (!image) return
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      // Account for rotation when sizing canvas
      const rad = (rotation * Math.PI) / 180
      const cos = Math.abs(Math.cos(rad))
      const sin = Math.abs(Math.sin(rad))
      const cw = Math.round(img.width * cos + img.height * sin)
      const ch = Math.round(img.width * sin + img.height * cos)

      const canvas = document.createElement('canvas')
      canvas.width = cw
      canvas.height = ch
      const ctx = canvas.getContext('2d')

      ctx.filter = liveFilter
      ctx.translate(cw / 2, ch / 2)
      ctx.rotate(rad)
      ctx.scale(flipH ? -1 : 1, flipV ? -1 : 1)
      ctx.drawImage(img, -img.width / 2, -img.height / 2)

      const mime = fmt === 'jpeg' ? 'image/jpeg' : 'image/png'
      const quality = fmt === 'jpeg' ? 0.92 : undefined
      canvas.toBlob(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `edited.${fmt}`
        a.click()
      }, mime, quality)
    }
    img.src = image.preview
  }, [image, liveFilter, rotation, flipH, flipV])

  const hasEdits = preset !== 'normal' || rotation !== 0 || flipH || flipV ||
    adj.brightness !== 100 || adj.contrast !== 100 || adj.saturation !== 100 || adj.blur !== 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-xl bg-rose-400/15 flex items-center justify-center">
              <Camera className="w-4 h-4 text-rose-400" />
            </div>
            <h2 className="font-space text-2xl font-bold">Photo Studio</h2>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-400 text-slate-950">FREE</span>
          </div>
          <p className="text-muted text-sm">Adjust brightness, apply filters and transform your photos — all in the browser.</p>
        </div>
      </div>

      {!image ? (
        /* ── Upload zone ── */
        <div
          onDragOver={e => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={e => { e.preventDefault(); setDrag(false); processFile(e.dataTransfer.files?.[0]) }}
          onClick={() => document.getElementById('studio-input')?.click()}
          className={`rounded-3xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center gap-4 py-20
            ${drag ? 'border-rose-400 bg-rose-400/10 scale-[1.01]' : 'border-white/20 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/35'}`}
        >
          <input id="studio-input" type="file" accept="image/*" className="hidden"
            onChange={e => { processFile(e.target.files?.[0]); e.target.value = '' }} />
          <div className="w-16 h-16 rounded-3xl bg-rose-400/10 border border-rose-400/20 flex items-center justify-center">
            <Upload className="w-7 h-7 text-rose-400" />
          </div>
          <div className="text-center">
            <p className="text-base font-semibold text-white/80">Drop your photo here</p>
            <p className="text-sm text-muted mt-1">or click to browse</p>
            <p className="text-xs text-white/30 mt-2">PNG, JPG, WEBP</p>
          </div>
        </div>
      ) : (
        <div className="grid xl:grid-cols-[1fr_320px] gap-6 items-start">
          {/* ── Canvas / Preview ── */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-white/50 uppercase tracking-wider">Preview</p>
              <div className="flex items-center gap-2">
                {hasEdits && (
                  <button onClick={resetAll} className="text-xs text-muted hover:text-white flex items-center gap-1 transition-colors">
                    <RefreshCw className="w-3.5 h-3.5" /> Reset
                  </button>
                )}
                <button
                  onClick={() => { setImage(null); resetAll() }}
                  className="text-xs text-muted hover:text-white flex items-center gap-1 transition-colors"
                >
                  <X className="w-3.5 h-3.5" /> Change photo
                </button>
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/[0.03] overflow-hidden flex items-center justify-center p-4"
              style={{ minHeight: 340 }}>
              <img
                src={image.preview}
                alt="preview"
                style={{ ...imgStyle, maxWidth: '100%', maxHeight: 480, objectFit: 'contain' }}
                className="rounded-xl"
              />
            </div>

            {/* Transform controls */}
            <div className="flex items-center gap-3 flex-wrap">
              <p className="text-xs font-semibold text-white/50 uppercase tracking-wider mr-1">Transform:</p>
              <button
                onClick={() => setRotation(r => (r - 90 + 360) % 360)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/8 hover:bg-white/14 text-xs text-white/70 hover:text-white transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Rotate -90°
              </button>
              <button
                onClick={() => setRotation(r => (r + 90) % 360)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/8 hover:bg-white/14 text-xs text-white/70 hover:text-white transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5 scale-x-[-1]" /> Rotate +90°
              </button>
              <button
                onClick={() => setFlipH(v => !v)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors
                  ${flipH ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-white/8 hover:bg-white/14 text-white/70 hover:text-white'}`}
              >
                <FlipHorizontal className="w-3.5 h-3.5" /> Flip H
              </button>
              <button
                onClick={() => setFlipV(v => !v)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors
                  ${flipV ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-white/8 hover:bg-white/14 text-white/70 hover:text-white'}`}
              >
                <FlipVertical className="w-3.5 h-3.5" /> Flip V
              </button>
            </div>

            {/* Download buttons */}
            <div className="flex gap-3">
              <Button
                onClick={() => handleDownload('png')}
                className="flex-1 gap-2 bg-rose-500 hover:bg-rose-400 text-white font-bold"
              >
                <Download className="w-4 h-4" /> Download PNG
              </Button>
              <Button
                onClick={() => handleDownload('jpeg')}
                variant="outline"
                className="flex-1 gap-2 border-white/20 text-white/80 hover:bg-white/8"
              >
                <Download className="w-4 h-4" /> Download JPG
              </Button>
            </div>
          </div>

          {/* ── Controls panel ── */}
          <div className="space-y-4">
            {/* Filter presets */}
            <div className="glass rounded-3xl p-4 space-y-3">
              <p className="text-xs font-semibold text-white/50 uppercase tracking-wider flex items-center gap-1.5">
                <Camera className="w-3.5 h-3.5" /> Filter Presets
              </p>
              <div className="grid grid-cols-5 gap-1.5">
                {PRESETS.map(p => (
                  <button
                    key={p.id}
                    onClick={() => setPreset(p.id)}
                    className={`flex flex-col items-center gap-1 p-1.5 rounded-xl transition-all
                      ${preset === p.id ? 'bg-rose-500/20 border border-rose-500/40' : 'bg-white/5 hover:bg-white/10 border border-transparent'}`}
                  >
                    <div
                      className="w-9 h-9 rounded-lg overflow-hidden"
                      style={{
                        background: 'linear-gradient(135deg, #e8b4b8, #a678c8, #78a8e8)',
                        filter: p.css === 'none' ? 'none' : p.css,
                      }}
                    />
                    <span className={`text-[9px] font-semibold leading-none ${preset === p.id ? 'text-rose-300' : 'text-white/50'}`}>
                      {p.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Adjustments */}
            <div className="glass rounded-3xl p-4 space-y-4">
              <p className="text-xs font-semibold text-white/50 uppercase tracking-wider flex items-center gap-1.5">
                <SlidersHorizontal className="w-3.5 h-3.5" /> Adjustments
              </p>
              <AdjustSlider
                label="Brightness"
                value={adj.brightness}
                min={20} max={200}
                onChange={v => setAdj(a => ({ ...a, brightness: v }))}
              />
              <AdjustSlider
                label="Contrast"
                value={adj.contrast}
                min={20} max={200}
                onChange={v => setAdj(a => ({ ...a, contrast: v }))}
              />
              <AdjustSlider
                label="Saturation"
                value={adj.saturation}
                min={0} max={300}
                onChange={v => setAdj(a => ({ ...a, saturation: v }))}
              />
              <AdjustSlider
                label="Blur"
                value={adj.blur}
                min={0} max={20}
                unit=""
                onChange={v => setAdj(a => ({ ...a, blur: v }))}
              />
            </div>

            {/* Info strip */}
            <div className="text-xs text-muted space-y-1.5">
              {[
                'All processing happens in your browser',
                'Original file never uploaded',
                'Exports at full resolution',
              ].map(t => (
                <div key={t} className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                  {t}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
