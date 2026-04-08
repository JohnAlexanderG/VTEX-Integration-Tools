import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, AlertCircle, Info } from 'lucide-react'
import type { Tool, JobStatus } from '../types'
import { fetchTools, fetchConfig } from '../api/client'
import AccessDeniedModal from '../components/AccessDeniedModal'
import ToolCard from '../components/ToolCard'
import { useAuth } from '../context/AuthContext'

interface StepState {
  status: JobStatus | null
  outputFiles: string[]
  jobId: string | null
}

export default function Pipeline() {
  const { hasSectionAccess, isAdmin } = useAuth()
  const pipelineAllowed = hasSectionAccess('pipeline')
  const [tools, setTools] = useState<Tool[]>([])
  const [vtexConfigured, setVtexConfigured] = useState(false)
  const [stepStates, setStepStates] = useState<Record<string, StepState>>({})
  const [activeStep, setActiveStep] = useState<string | null>(null)
  const [showDeniedModal, setShowDeniedModal] = useState(false)

  useEffect(() => {
    fetchTools().then((all) => {
      const pipeline = all
        .filter((t) => t.category === 'pipeline')
        .sort((a, b) => (a.step ?? 0) - (b.step ?? 0))
      setTools(pipeline)
    })
    if (isAdmin) {
      fetchConfig().then((c) => setVtexConfigured(c.configured)).catch(() => setVtexConfigured(false))
    } else {
      setVtexConfigured(false)
    }
  }, [isAdmin])

  useEffect(() => {
    if (!pipelineAllowed) setShowDeniedModal(true)
  }, [pipelineAllowed])

  const handleComplete = (toolId: string) => (jobId: string, outputFiles: string[]) => {
    setStepStates((prev) => ({
      ...prev,
      [toolId]: { status: 'completed', outputFiles, jobId },
    }))
  }

  function stepIcon(toolId: string) {
    const s = stepStates[toolId]?.status
    if (s === 'completed') return <CheckCircle2 size={18} className="text-green-400" />
    if (s === 'failed') return <AlertCircle size={18} className="text-red-400" />
    if (s === 'running') return (
      <div className="w-[18px] h-[18px] rounded-full border-2 border-vtex-pink border-t-transparent animate-spin" />
    )
    return <Circle size={18} className="text-gray-600" />
  }

  return (
    <div className="p-4 md:p-6 max-w-3xl">
      <div className="mb-5 md:mb-6">
        <h1 className="text-xl font-bold text-gray-100">Pipeline</h1>
        <p className="text-sm text-gray-500 mt-1">
          Ejecuta los pasos del flujo completo de integración VTEX en orden.
        </p>
      </div>

      {/* Pre-step note */}
      <div className="flex items-start gap-2 bg-blue-900/20 border border-blue-700/40 rounded-lg px-4 py-3 mb-5 md:mb-6">
        <Info size={15} className="text-blue-400 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-blue-300">
          <strong>Antes de empezar:</strong> Si es la primera vez creando categorías en VTEX, ejecuta el{' '}
          <strong>Paso 24</strong> primero para establecer la jerarquía de categorías.
        </p>
      </div>

      <div className="space-y-4">
        {tools.map((tool, i) => {
          const isOpen = activeStep === tool.id
          const state = stepStates[tool.id]

          return (
            <div key={tool.id} className="relative">
              {/* Connector line */}
              {i < tools.length - 1 && (
                <div className="absolute left-[22px] top-full w-0.5 h-4 bg-gray-800 z-10" />
              )}

              {/* Step header (collapsible) */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <button
                  onClick={() => {
                    if (!pipelineAllowed || tool.enabled === false) {
                      setShowDeniedModal(true)
                      return
                    }
                    setActiveStep(isOpen ? null : tool.id)
                  }}
                  className="w-full flex items-center gap-3 md:gap-4 px-4 md:px-5 py-3 md:py-4 text-left hover:bg-gray-800/40 transition-colors"
                >
                  <div className="flex-shrink-0">{stepIcon(tool.id)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono text-gray-500">
                        {tool.step !== undefined ? `#${tool.step}` : ''}
                      </span>
                      <span className="text-sm font-medium text-gray-100">{tool.shortName}</span>
                      {tool.requires_vtex && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-vtex-pink/20 text-vtex-pink rounded font-medium">
                          VTEX API
                        </span>
                      )}
                      {tool.enabled === false && (
                        <span className="rounded border border-red-800 bg-red-950 px-1.5 py-0.5 text-[10px] font-medium text-red-300">
                          Bloqueado
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 truncate mt-0.5">{tool.description}</p>
                  </div>
                  {state?.outputFiles && state.outputFiles.length > 0 && (
                    <span className="text-xs text-green-400 flex-shrink-0 hidden sm:inline">
                      {state.outputFiles.length} archivo{state.outputFiles.length !== 1 ? 's' : ''}
                    </span>
                  )}
                  <span className="text-gray-600 flex-shrink-0">{isOpen ? '▲' : '▼'}</span>
                </button>

                {isOpen && (
                  <div className="border-t border-gray-800">
                    <div className="p-4 md:p-5">
                      <ToolCard
                        tool={tool}
                        vtexConfigured={vtexConfigured}
                        onComplete={handleComplete(tool.id)}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <AccessDeniedModal
        open={showDeniedModal}
        title="Pipeline bloqueado"
        message="Tu cuenta no tiene permisos para acceder a esta sección o a alguno de sus pasos. Solicita la habilitación desde Laburu Agencia."
        onClose={() => setShowDeniedModal(false)}
      />
    </div>
  )
}
