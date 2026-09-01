import {
  Cloud,
  FileJson,
  FileSpreadsheet,
  Filter,
  Image,
  Layers,
  Tags,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Tool } from '../../types'

/**
 * Icono por herramienta. Vive en el front a propósito: agregar un campo
 * "icon" a los 43 diccionarios del backend no aporta nada y el fallback por
 * requires_vtex cubre cualquier herramienta nueva sin tocar este archivo.
 */
const TOOL_ICONS: Record<string, LucideIcon> = {
  step_01: FileSpreadsheet,
  step_08: Tags,
  step_24: Layers,
  step_17: Image,
  tool_json_to_csv: FileJson,
  tool_csv_cleaner: Filter,
}

export function iconForTool(tool: Tool): LucideIcon {
  return TOOL_ICONS[tool.id] ?? (tool.requires_vtex ? Cloud : Wrench)
}
