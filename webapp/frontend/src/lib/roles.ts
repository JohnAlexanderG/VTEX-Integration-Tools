import type { BadgeTone } from '../components/ui'

export const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Super Admin',
  admin:      'Admin',
  operator:   'Operador',
}

export const ROLE_TONES: Record<string, BadgeTone> = {
  superadmin: 'accent',
  admin:      'info',
  operator:   'neutral',
}
