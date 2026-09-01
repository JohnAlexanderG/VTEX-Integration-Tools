import { useCallback, useState } from 'react'
import type { Tool } from '../types'

export type FieldValue = string | boolean | File | null

export interface ToolFormPayload {
  params: Record<string, string>
  files: Array<{ fieldName: string; file: File }>
}

/** Estado y serialización del formulario dinámico de una herramienta. */
export function useToolForm(tool: Tool, initialValues: Record<string, FieldValue> = {}) {
  const [values, setValues] = useState<Record<string, FieldValue>>(() => {
    const defaults: Record<string, FieldValue> = {}
    for (const inp of tool.inputs) {
      defaults[inp.name] =
        initialValues[inp.name] !== undefined
          ? initialValues[inp.name]
          : inp.default !== undefined
          ? (inp.default as FieldValue)
          : inp.type === 'checkbox'
          ? false
          : null
    }
    return defaults
  })

  const setValue = useCallback((name: string, value: FieldValue) => {
    setValues((prev) => ({ ...prev, [name]: value }))
  }, [])

  /** Devuelve el mensaje del primer campo requerido vacío, o null si está ok. */
  const validate = useCallback((): string | null => {
    for (const inp of tool.inputs) {
      if (inp.required && !values[inp.name]) {
        return `El campo "${inp.label}" es requerido.`
      }
    }
    return null
  }, [tool.inputs, values])

  const toPayload = useCallback((): ToolFormPayload => {
    const params: Record<string, string> = {}
    const files: Array<{ fieldName: string; file: File }> = []

    for (const inp of tool.inputs) {
      const val = values[inp.name]
      if (inp.type === 'file') {
        if (val instanceof File) files.push({ fieldName: inp.name, file: val })
      } else if (inp.type === 'checkbox') {
        // Un checkbox apagado no manda nada: el flag CLI simplemente se omite.
        if (val === true) params[inp.name] = 'true'
      } else if (val !== null && val !== undefined && val !== '') {
        params[inp.name] = String(val)
      }
    }

    return { params, files }
  }, [tool.inputs, values])

  return { values, setValue, validate, toPayload }
}
