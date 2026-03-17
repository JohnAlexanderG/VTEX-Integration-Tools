import { useRef } from 'react'
import { Upload, X } from 'lucide-react'
import type { ToolInput } from '../types'

interface Props {
  field: ToolInput
  value: string | boolean | File | null
  onChange: (name: string, value: string | boolean | File | null) => void
}

export default function FormField({ field, value, onChange }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const labelClass = 'block text-xs font-medium text-gray-400 mb-1'
  const inputClass =
    'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-vtex-pink focus:ring-1 focus:ring-vtex-pink'

  if (field.type === 'file') {
    const file = value instanceof File ? value : null
    return (
      <div>
        <label className={labelClass}>
          {field.label}
          {field.required && <span className="text-vtex-pink ml-1">*</span>}
        </label>
        <div
          className={`relative border-2 border-dashed rounded-lg p-3 cursor-pointer transition-colors ${
            file ? 'border-green-600 bg-green-900/10' : 'border-gray-700 hover:border-gray-500'
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={field.accept}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null
              onChange(field.name, f)
            }}
          />
          {file ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <Upload size={14} className="text-green-400 flex-shrink-0" />
                <span className="text-sm text-green-300 truncate">{file.name}</span>
                <span className="text-xs text-gray-500 flex-shrink-0">
                  ({(file.size / 1024).toFixed(1)} KB)
                </span>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onChange(field.name, null)
                  if (fileInputRef.current) fileInputRef.current.value = ''
                }}
                className="text-gray-500 hover:text-red-400 flex-shrink-0 ml-2"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-gray-500">
              <Upload size={14} />
              <span className="text-sm">
                {field.accept ? `${field.accept} — ` : ''}Clic o arrastra un archivo
              </span>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (field.type === 'checkbox') {
    return (
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id={field.name}
          checked={value === true}
          onChange={(e) => onChange(field.name, e.target.checked)}
          className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-vtex-pink focus:ring-vtex-pink focus:ring-offset-0"
        />
        <label htmlFor={field.name} className="text-sm text-gray-300 cursor-pointer">
          {field.label}
        </label>
      </div>
    )
  }

  if (field.type === 'select') {
    return (
      <div>
        <label className={labelClass}>{field.label}</label>
        <select
          value={typeof value === 'string' ? value : String(field.default ?? '')}
          onChange={(e) => onChange(field.name, e.target.value)}
          className={inputClass}
        >
          {(field.options ?? []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    )
  }

  if (field.type === 'number') {
    return (
      <div>
        <label className={labelClass}>{field.label}</label>
        <input
          type="number"
          value={typeof value === 'string' ? value : String(field.default ?? '')}
          onChange={(e) => onChange(field.name, e.target.value)}
          className={inputClass}
          step="any"
        />
      </div>
    )
  }

  // text
  return (
    <div>
      <label className={labelClass}>
        {field.label}
        {field.required && <span className="text-vtex-pink ml-1">*</span>}
      </label>
      <input
        type="text"
        value={typeof value === 'string' ? value : ''}
        placeholder={String(field.default ?? '')}
        onChange={(e) => onChange(field.name, e.target.value)}
        className={inputClass}
      />
    </div>
  )
}
