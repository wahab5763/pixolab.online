import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  Sparkles,
  BadgeCheck,
  Zap,
  Lightbulb,
  Camera,
  Battery,
  Shield,
  Star,
  ChevronRight,
  Monitor,
  Signal,
  Cpu,
  CheckCircle2,
  ShieldAlert,
  ImagePlus,
  Upload,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import ProcessingStatus from '@/components/ProcessingStatus'
import ResultDisplay from '@/components/ResultDisplay'

const ICON_MAP = {
  BadgeCheck, Zap, Lightbulb, Camera, Battery, Shield, Star, ChevronRight,
  Monitor, Signal, Cpu, Sparkles, ImagePlus,
}

function FieldIcon({ name }) {
  const Icon = ICON_MAP[name] || Zap
  return <Icon className="w-4 h-4 text-primary" />
}

function TemplateUploadZone({ imageConfig, image, onChange }) {
  const [dragging, setDragging] = useState(false)

  const processFile = useCallback(file => {
    if (!file) return
    if (!file.type.startsWith('image/')) return
    const preview = URL.createObjectURL(file)
    onChange({ file, preview, name: file.name })
  }, [onChange])

  const onDrop = useCallback(e => {
    e.preventDefault()
    setDragging(false)
    processFile(e.dataTransfer.files?.[0])
  }, [processFile])

  const onFile = useCallback(e => processFile(e.target.files?.[0]), [processFile])

  const clear = useCallback(e => {
    e.stopPropagation()
    onChange(null)
  }, [onChange])

  const isOptional = imageConfig.optional === true

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <p className="text-sm font-semibold text-white/90">{imageConfig.label}</p>
        {isOptional && (
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-white/10 text-white/50 border border-white/15">
            Optional
          </span>
        )}
      </div>
      <p className="text-xs text-muted -mt-1">{imageConfig.sublabel}</p>

      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`relative rounded-2xl border-2 border-dashed transition-all cursor-pointer overflow-hidden
          ${dragging ? 'border-primary bg-primary/10' : 'border-white/20 bg-white/[0.03] hover:bg-white/[0.07] hover:border-white/35'}`}
        style={{ minHeight: 140 }}
        onClick={() => !image && document.getElementById(`tpl-upload-${imageConfig.key}`)?.click()}
      >
        <input
          id={`tpl-upload-${imageConfig.key}`}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={onFile}
        />

        {image ? (
          <div className="relative w-full h-36">
            <img src={image.preview} alt={imageConfig.label} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
            <div className="absolute bottom-2 left-2 text-xs text-white/80 font-medium truncate max-w-[80%]">{image.name}</div>
            <button
              onClick={clear}
              className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/60 flex items-center justify-center hover:bg-red-500/80 transition-colors"
            >
              <X className="w-3 h-3 text-white" />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-2 py-8 px-4 text-center">
            <div className="w-10 h-10 rounded-2xl bg-white/8 flex items-center justify-center">
              <Upload className="w-5 h-5 text-muted" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white/70">
                {isOptional ? 'Drop or click to upload' : 'Drop or click to upload'}
              </p>
              <p className="text-xs text-muted mt-0.5">PNG, JPG, WEBP • Max 10MB</p>
              {isOptional && (
                <p className="text-xs text-white/30 mt-1">Skip to generate without this image</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function TemplateField({ field, value, onChange }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-white/90 mb-2 flex items-center gap-2">
        <FieldIcon name={field.icon} />
        {field.label}
        {field.required && <span className="text-red-400 text-xs">*</span>}
      </span>
      <input
        value={value}
        onChange={e => onChange(field.key, e.target.value)}
        placeholder={field.placeholder}
        className="input-premium"
      />
    </label>
  )
}

export default function TemplateForm({ template, onBack }) {
  const [images, setImages] = useState({})
  const [fieldValues, setFieldValues] = useState(() => {
    const init = {}
    template.fields?.forEach(f => { init[f.key] = '' })
    return init
  })
  const [consentGiven, setConsentGiven] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const accent = template.accent_hex || '#00c8ff'
  const colors = template.preview_colors || ['#050618', '#1a1a3e']
  const gradient = `linear-gradient(135deg, ${colors[0]} 0%, ${colors[1] || colors[0]} 100%)`

  const requiredImages = template.required_images || []
  // Only non-optional images must be uploaded
  const mandatoryImages = requiredImages.filter(img => !img.optional)
  const allMandatoryUploaded = mandatoryImages.every(img => images[img.key])
  const requiredFields = template.fields?.filter(f => f.required) || []
  const allRequiredFilled = requiredFields.every(f => (fieldValues[f.key] || '').trim())

  const canGenerate = allMandatoryUploaded && allRequiredFilled && consentGiven && !processing

  const setFieldValue = useCallback((key, val) => {
    setFieldValues(prev => ({ ...prev, [key]: val }))
  }, [])

  const handleGenerate = async () => {
    setProcessing(true)
    setError(null)
    setResult(null)
    setCurrentStep(0)
    setProgress(5)

    const timers = [0, 3500, 16000, 35000].map((t, i) => setTimeout(() => setCurrentStep(i), t))
    const interval = setInterval(() => setProgress(p => Math.min(92, p + Math.max(0.5, Math.random() * 2.5))), 900)

    try {
      const form = new FormData()
      // Always append product image
      if (images.product) form.append('product_image', images.product.file)
      // Only append person image if provided
      if (images.person) form.append('person_image', images.person.file)
      form.append('template_id', template.id)
      form.append('consent_confirmed', 'true')
      template.fields?.forEach(f => form.append(f.key, fieldValues[f.key] || ''))

      const generated = await api.generateFromTemplate(form)
      setProgress(100)
      setCurrentStep(3)
      setTimeout(() => setResult(generated), 250)
    } catch (err) {
      setError(err.message)
    } finally {
      timers.forEach(clearTimeout)
      clearInterval(interval)
      setTimeout(() => setProcessing(false), 300)
    }
  }

  const handleReset = () => {
    setImages({})
    setFieldValues(() => {
      const init = {}
      template.fields?.forEach(f => { init[f.key] = '' })
      return init
    })
    setResult(null)
    setError(null)
    setCurrentStep(0)
    setProgress(0)
    setConsentGiven(false)
  }

  if (result) {
    return <ResultDisplay result={result} onReset={handleReset} />
  }

  if (processing) {
    return (
      <div className="flex justify-center py-8">
        <ProcessingStatus currentStep={currentStep} mode="poster" progress={progress} />
      </div>
    )
  }

  const mainFields = template.fields?.filter(f => f.group === 'main') || []
  const featureFields = template.fields?.filter(f => f.group === 'features') || []
  const extraFields = template.fields?.filter(f => f.group === 'extra') || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="w-10 h-10 rounded-xl bg-white/8 flex items-center justify-center hover:bg-white/14 transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-white/70" />
        </button>
        <div>
          <p className="text-xs text-muted">Template selected</p>
          <h2 className="font-space text-xl font-bold">{template.name}</h2>
        </div>
        <div
          className="ml-auto px-3 py-1 rounded-full text-xs font-bold"
          style={{ background: accent, color: '#0a0a1a' }}
        >
          {template.tag}
        </div>
      </div>

      {/* Template preview strip */}
      <div
        className="rounded-2xl overflow-hidden relative"
        style={{ background: gradient, height: 80 }}
      >
        <div className="absolute inset-0 opacity-40" style={{ background: `radial-gradient(ellipse at 70% 50%, ${accent}55 0%, transparent 70%)` }} />
        <div className="relative z-10 h-full flex items-center px-5 gap-4">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: `${accent}30`, border: `1px solid ${accent}55` }}
          >
            <Sparkles className="w-5 h-5" style={{ color: accent }} />
          </div>
          <div>
            <p className="font-bold text-white">{template.name}</p>
            <p className="text-xs text-white/60">{template.long_description || template.description}</p>
          </div>
          <div className="ml-auto text-right text-xs text-white/40">
            {template.dimensions?.[0]}×{template.dimensions?.[1]}px
          </div>
        </div>
      </div>

      <div className="grid xl:grid-cols-[1fr_340px] gap-6 items-start">
        <div className="space-y-5">
          {/* Image uploads */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-3xl p-5">
            <h3 className="font-space text-base font-bold mb-4 flex items-center gap-2">
              <ImagePlus className="w-5 h-5 text-accent" /> Upload Your Images
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              {requiredImages.map(imgConfig => (
                <TemplateUploadZone
                  key={imgConfig.key}
                  imageConfig={imgConfig}
                  image={images[imgConfig.key] || null}
                  onChange={img => setImages(prev => ({ ...prev, [imgConfig.key]: img }))}
                />
              ))}
            </div>
          </motion.div>

          {/* Main fields */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }} className="glass rounded-3xl p-5">
            <h3 className="font-space text-base font-bold mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" /> Campaign Details
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              {mainFields.map(field => (
                <TemplateField key={field.key} field={field} value={fieldValues[field.key] || ''} onChange={setFieldValue} />
              ))}
            </div>
          </motion.div>

          {featureFields.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="glass rounded-3xl p-5">
              <h3 className="font-space text-base font-bold mb-1 flex items-center gap-2">
                <Shield className="w-5 h-5 text-emerald-400" /> Feature Highlights
              </h3>
              <p className="text-xs text-muted mb-4">These appear in the feature bar at the bottom of your poster.</p>
              <div className="grid sm:grid-cols-3 gap-4">
                {featureFields.map(field => (
                  <TemplateField key={field.key} field={field} value={fieldValues[field.key] || ''} onChange={setFieldValue} />
                ))}
              </div>
            </motion.div>
          )}

          {extraFields.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16 }} className="glass rounded-3xl p-5">
              <h3 className="font-space text-base font-bold mb-4 flex items-center gap-2">
                <Star className="w-5 h-5 text-amber-300" /> Extra Text
              </h3>
              <div className="grid sm:grid-cols-2 gap-4">
                {extraFields.map(field => (
                  <TemplateField key={field.key} field={field} value={fieldValues[field.key] || ''} onChange={setFieldValue} />
                ))}
              </div>
            </motion.div>
          )}

          {/* Consent */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.20 }} className="glass rounded-2xl p-4">
            <label className="flex items-start gap-3 cursor-pointer">
              <div
                onClick={() => setConsentGiven(v => !v)}
                className={`mt-0.5 w-5 h-5 rounded flex items-center justify-center flex-shrink-0 border-2 transition-all ${
                  consentGiven ? 'bg-primary border-primary' : 'border-white/30 bg-transparent'
                }`}
              >
                {consentGiven && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
              </div>
              <span className="text-sm text-white/75 leading-relaxed">
                I confirm I have the rights to use all uploaded images for commercial advertising purposes and accept the terms of service.
              </span>
            </label>
          </motion.div>

          {/* Generate button */}
          <div className="flex flex-col items-center gap-3">
            <Button
              size="lg"
              disabled={!canGenerate}
              onClick={handleGenerate}
              className="gap-2 px-10 py-6 text-base rounded-xl shadow-lg w-full md:w-auto"
            >
              <Sparkles className="w-5 h-5" /> Generate from Template
            </Button>

            {!consentGiven && (allMandatoryUploaded || allRequiredFilled) && (
              <div className="flex items-center gap-1.5 text-xs text-amber-300">
                <ShieldAlert className="w-3.5 h-3.5" /> Please confirm consent to enable generation
              </div>
            )}
            {!allMandatoryUploaded && (
              <p className="text-center text-xs text-muted">Upload the product image to continue</p>
            )}
          </div>

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-100 text-sm text-center">
              {error}
            </div>
          )}
        </div>

        {/* Sidebar preview */}
        <motion.aside
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          className="glass rounded-3xl p-5 sticky top-6 hidden xl:block"
        >
          <h3 className="font-space font-bold mb-4 flex items-center gap-2">
            <ImagePlus className="w-5 h-5 text-primary" /> Live Preview
          </h3>

          {/* Mini poster mockup */}
          <div
            className="rounded-2xl overflow-hidden border border-white/10 relative mb-4"
            style={{ background: gradient, aspectRatio: template.dimensions ? `${template.dimensions[0]}/${template.dimensions[1]}` : '1/1', minHeight: 220 }}
          >
            <div className="absolute inset-0 opacity-35" style={{ background: `radial-gradient(ellipse at 65% 35%, ${accent}44 0%, transparent 65%)` }} />
            <div className="relative z-10 p-3 h-full flex flex-col justify-between">
              <div className="space-y-1.5">
                <div className="inline-flex px-2 py-0.5 rounded-full text-[9px] font-bold" style={{ background: accent, color: '#0a0a1a' }}>
                  {fieldValues.brand_name || template.required_images?.[0]?.label || 'Brand'}
                </div>
                <div className="font-bold text-white text-sm leading-tight">
                  {fieldValues.headline || template.fields?.find(f => f.key === 'headline')?.placeholder || 'Headline'}
                </div>
                {fieldValues.subheadline && (
                  <div className="text-xs text-white/60">{fieldValues.subheadline}</div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                {requiredImages.map(img => (
                  <div key={img.key} className="rounded-xl overflow-hidden bg-white/10 border border-white/10" style={{ height: 70 }}>
                    {images[img.key] ? (
                      <img src={images[img.key].preview} alt={img.label} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[9px] text-white/30">
                        {img.label}{img.optional ? ' (opt.)' : ''}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {featureFields.length > 0 && (
                <div
                  className="absolute bottom-0 left-0 right-0 h-7 flex items-center justify-around px-2"
                  style={{ background: 'rgba(0,0,0,0.55)', borderTop: `1px solid ${accent}44` }}
                >
                  {featureFields.map(f => (
                    <div key={f.key} className="flex flex-col items-center gap-0.5">
                      <div className="w-1.5 h-1.5 rounded-full" style={{ background: accent }} />
                      <div className="h-1 w-6 rounded opacity-40" style={{ background: 'rgba(255,255,255,0.4)' }} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Checklist */}
          <div className="space-y-2 text-sm">
            {requiredImages.map(img => (
              <div key={img.key} className="flex items-center gap-2">
                <CheckCircle2 className={`w-4 h-4 ${images[img.key] ? 'text-emerald-400' : img.optional ? 'text-white/15' : 'text-white/20'}`} />
                <span className={images[img.key] ? 'text-white' : 'text-white/40'}>
                  {img.label}{img.optional ? ' (optional)' : ''}
                </span>
              </div>
            ))}
            {requiredFields.map(f => (
              <div key={f.key} className="flex items-center gap-2">
                <CheckCircle2 className={`w-4 h-4 ${(fieldValues[f.key] || '').trim() ? 'text-emerald-400' : 'text-white/20'}`} />
                <span className={(fieldValues[f.key] || '').trim() ? 'text-white' : 'text-white/40'}>{f.label}</span>
              </div>
            ))}
            <div className="flex items-center gap-2">
              <CheckCircle2 className={`w-4 h-4 ${consentGiven ? 'text-emerald-400' : 'text-white/20'}`} />
              <span className={consentGiven ? 'text-white' : 'text-white/40'}>Consent confirmed</span>
            </div>
          </div>
        </motion.aside>
      </div>
    </div>
  )
}
