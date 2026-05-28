import { useRef, useState } from 'react'
import { Upload, X, ImageIcon } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'

export default function ImageUploadZone({ label, sublabel, image, onImageChange, accentColor = 'purple' }) {
  const inputRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = (e) => onImageChange({ file, preview: e.target.result })
    reader.readAsDataURL(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleRemove = (e) => {
    e.stopPropagation()
    onImageChange(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const tone = accentColor === 'cyan' ? 'accent' : 'primary'

  return (
    <div className="flex flex-col gap-3 w-full">
      <div className="flex items-center gap-2">
        <div className={cn('w-2 h-2 rounded-full', tone === 'accent' ? 'bg-accent' : 'bg-primary')} />
        <span className="font-space font-bold text-sm text-foreground">{label}</span>
        <span className="text-xs text-muted">{sublabel}</span>
      </div>

      <div
        className={cn('image-upload-zone rounded-2xl overflow-hidden cursor-pointer relative min-h-[260px] flex items-center justify-center', isDragging && 'drag-over')}
        onClick={() => !image && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => handleFile(e.target.files[0])} />
        <AnimatePresence mode="wait">
          {image ? (
            <motion.div key="image" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }} className="w-full h-full relative group">
              <img src={image.preview} alt={label} className="w-full h-full object-cover min-h-[260px] max-h-[340px]" />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                <button onClick={(e) => { e.stopPropagation(); inputRef.current?.click() }} className="px-4 py-2 bg-white/10 backdrop-blur-sm rounded-lg text-white text-sm font-medium hover:bg-white/20 transition-colors">Change</button>
                <button onClick={handleRemove} className="p-2 bg-red-500/20 backdrop-blur-sm rounded-lg text-red-300 hover:bg-red-500/30 transition-colors"><X className="w-4 h-4" /></button>
              </div>
              <div className={cn('absolute top-3 right-3 px-2.5 py-1 rounded-lg text-xs font-semibold border', tone === 'accent' ? 'bg-accent/20 text-accent border-accent/30' : 'bg-primary/20 text-primary border-primary/30')}>✓ Ready</div>
            </motion.div>
          ) : (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col items-center gap-4 p-8 text-center">
              <div className={cn('w-16 h-16 rounded-2xl flex items-center justify-center border', tone === 'accent' ? 'bg-accent/10 border-accent/20' : 'bg-primary/10 border-primary/20')}>
                <ImageIcon className={cn('w-7 h-7', tone === 'accent' ? 'text-accent' : 'text-primary')} />
              </div>
              <div>
                <p className="text-foreground font-semibold text-sm mb-1">Drop image here or click to upload</p>
                <p className="text-muted text-xs">PNG, JPG, WEBP supported</p>
              </div>
              <div className={cn('flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold', tone === 'accent' ? 'bg-accent/10 text-accent' : 'bg-primary/10 text-primary')}>
                <Upload className="w-3 h-3" /> Choose file
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
