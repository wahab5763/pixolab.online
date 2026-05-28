import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Eraser, Upload, Download, X, CheckCircle2, Sparkles, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

function UploadZone({ image, onChange }) {
  const [drag, setDrag] = useState(false)

  const process = useCallback(file => {
    if (!file || !file.type.startsWith('image/')) return
    onChange({ file, preview: URL.createObjectURL(file), name: file.name })
  }, [onChange])

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => { e.preventDefault(); setDrag(false); process(e.dataTransfer.files?.[0]) }}
      onClick={() => !image && document.getElementById('bg-remover-input')?.click()}
      className={`relative rounded-3xl border-2 border-dashed transition-all overflow-hidden cursor-pointer
        ${drag ? 'border-emerald-400 bg-emerald-400/10 scale-[1.01]' : 'border-white/20 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/35'}`}
      style={{ minHeight: 320 }}
    >
      <input id="bg-remover-input" type="file" accept="image/*" className="hidden"
        onChange={e => { process(e.target.files?.[0]); e.target.value = '' }} />

      {image ? (
        <>
          <img src={image.preview} alt="input" className="w-full h-full object-contain" style={{ maxHeight: 420 }} />
          <button
            onClick={e => { e.stopPropagation(); onChange(null) }}
            className="absolute top-3 right-3 w-7 h-7 rounded-full bg-black/70 flex items-center justify-center hover:bg-red-500/80 transition-colors z-10"
          >
            <X className="w-3.5 h-3.5 text-white" />
          </button>
          <div className="absolute bottom-3 left-3 px-2 py-1 rounded-full bg-black/60 text-[10px] text-white/80 truncate max-w-[75%]">
            {image.name}
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center gap-3 py-16 px-6 text-center h-full">
          <div className="w-16 h-16 rounded-3xl bg-emerald-400/10 border border-emerald-400/20 flex items-center justify-center">
            <Upload className="w-7 h-7 text-emerald-400" />
          </div>
          <div>
            <p className="text-base font-semibold text-white/80">Drop your image here</p>
            <p className="text-sm text-muted mt-1">or click to browse</p>
            <p className="text-xs text-white/30 mt-2">PNG, JPG, WEBP • Any subject</p>
          </div>
        </div>
      )}
    </div>
  )
}

function ResultPane({ resultUrl, isProcessing, error, onDownload, onReset }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] overflow-hidden" style={{ minHeight: 320 }}>
      <AnimatePresence mode="wait">
        {isProcessing ? (
          <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center gap-4 h-full py-20">
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}>
              <Eraser className="w-10 h-10 text-emerald-400" />
            </motion.div>
            <div className="text-center">
              <p className="font-semibold text-white">Removing background…</p>
              <p className="text-xs text-muted mt-1">Usually takes 5–15 seconds</p>
            </div>
          </motion.div>
        ) : error ? (
          <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center gap-3 h-full py-20 px-6 text-center">
            <div className="text-red-300 font-semibold">Something went wrong</div>
            <div className="text-xs text-red-200/70">{error}</div>
          </motion.div>
        ) : resultUrl ? (
          <motion.div key="result" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="relative">
            {/* Checkerboard pattern behind transparent PNG */}
            <div className="absolute inset-0 rounded-t-3xl pointer-events-none" style={{
              backgroundImage: 'repeating-conic-gradient(#ffffff12 0% 25%, #ffffff06 0% 50%)',
              backgroundSize: '24px 24px',
            }} />
            <img src={resultUrl} alt="result" className="relative w-full object-contain rounded-t-3xl" style={{ maxHeight: 380 }} />
            <div className="p-4 flex items-center gap-3 border-t border-white/10 bg-white/[0.03]">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
              <span className="text-sm text-emerald-300 font-semibold flex-1">Background removed!</span>
              <button onClick={onReset} className="text-xs text-muted hover:text-white transition-colors flex items-center gap-1">
                <RefreshCw className="w-3.5 h-3.5" /> New image
              </button>
              <Button size="sm" onClick={onDownload} className="gap-1.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold">
                <Download className="w-4 h-4" /> Download PNG
              </Button>
            </div>
          </motion.div>
        ) : (
          <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center gap-3 h-full py-20 px-6 text-center">
            <div className="w-14 h-14 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white/20" />
            </div>
            <p className="text-white/30 text-sm">Your result will appear here</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function BackgroundRemover() {
  const [image, setImage] = useState(null)
  const [resultUrl, setResultUrl] = useState(null)
  const [resultBlob, setResultBlob] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState(null)

  const handleRemove = async () => {
    if (!image) return
    setProcessing(true)
    setError(null)
    setResultUrl(null)
    try {
      const form = new FormData()
      form.append('image', image.file)
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
      const res = await fetch(`${API_URL}/tools/remove-background`, { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.text()
        throw new Error(body || 'Background removal failed')
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
    a.download = 'bg_removed.png'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const handleReset = () => {
    const input = document.getElementById('bg-remover-input')
    if (input) input.value = ''
    setImage(null)
    setResultUrl(null)
    setResultBlob(null)
    setError(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-xl bg-emerald-400/15 flex items-center justify-center">
              <Eraser className="w-4 h-4 text-emerald-400" />
            </div>
            <h2 className="font-space text-2xl font-bold">Background Remover</h2>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-400 text-slate-950">FREE</span>
          </div>
          <p className="text-muted text-sm">Remove the background from any photo instantly — no credits needed.</p>
        </div>
      </div>

      {/* Upload + Result grid */}
      <div className="grid md:grid-cols-2 gap-5">
        <div className="space-y-4">
          <p className="text-xs font-semibold text-white/50 uppercase tracking-wider">Original Image</p>
          <UploadZone image={image} onChange={setImage} />
          <Button
            size="lg"
            disabled={!image || processing}
            onClick={handleRemove}
            className="w-full gap-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-5 rounded-xl"
          >
            {processing
              ? <><motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}><Eraser className="w-5 h-5" /></motion.div> Removing…</>
              : <><Eraser className="w-5 h-5" /> Remove Background</>
            }
          </Button>
        </div>

        <div className="space-y-4">
          <p className="text-xs font-semibold text-white/50 uppercase tracking-wider">Result (Transparent PNG)</p>
          <ResultPane
            resultUrl={resultUrl}
            isProcessing={processing}
            error={error}
            onDownload={handleDownload}
            onReset={handleReset}
          />
        </div>
      </div>

      {/* Info strip */}
      <div className="flex flex-wrap gap-4 text-xs text-muted">
        {['Works on people, products & objects', 'Exports as transparent PNG', 'No credits consumed', 'Powered by U²-Net AI'].map(t => (
          <span key={t} className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> {t}
          </span>
        ))}
      </div>
    </div>
  )
}
