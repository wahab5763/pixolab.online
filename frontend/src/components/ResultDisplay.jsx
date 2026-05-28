import { Download, RotateCcw, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function ResultDisplay({ result, onReset }) {
  return (
    <div className="glass rounded-3xl p-5 md:p-7">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
        <div>
          <h2 className="font-space text-2xl font-bold">Your ad creative is ready</h2>
          <p className="text-sm text-muted">{result.width} × {result.height} • {result.style.replaceAll('_', ' ')} • {result.mode?.replaceAll('_', ' ')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onReset}><RotateCcw className="w-4 h-4" /> New</Button>
          <Button asChild><a href={result.result_url} download target="_blank" rel="noreferrer"><Download className="w-4 h-4" /> Download</a></Button>
        </div>
      </div>
      <a href={result.result_url} target="_blank" rel="noreferrer" className="block rounded-2xl overflow-hidden border border-border bg-black/20 group">
        <img src={result.result_url} alt="Generated ad creative" className="w-full h-auto" />
        <div className="flex items-center gap-2 text-sm text-muted p-3 group-hover:text-white transition-colors"><ExternalLink className="w-4 h-4" /> Open full image</div>
      </a>
    </div>
  )
}
