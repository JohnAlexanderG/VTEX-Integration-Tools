import { Building2, ChevronRight } from 'lucide-react'
import type { AccountSummary } from '../api/client'
import { ROLE_LABELS, ROLE_TONES } from '../lib/roles'
import { Badge, cn } from './ui'

interface Props {
  accounts:   AccountSummary[]
  onSelect:   (account: AccountSummary) => void
  /** user_id que se está procesando (deshabilita la lista mientras tanto). */
  pendingId?: number | null
  /** user_id de la sesión actual, si aplica. */
  currentId?: number
}

/** Lista de cuentas (tenants) a las que pertenece el email con el que se inició sesión. */
export default function AccountList({ accounts, onSelect, pendingId = null, currentId }: Props) {
  return (
    <ul className="space-y-2">
      {accounts.map(account => {
        const isCurrent = account.user_id === currentId
        return (
          <li key={account.user_id}>
            <button
              type="button"
              onClick={() => onSelect(account)}
              disabled={pendingId !== null || isCurrent}
              className={cn(
                'w-full flex items-center gap-3 rounded-card border border-line-1 bg-surface-2/40 px-4 py-3 text-left transition-colors',
                'hover:border-accent hover:bg-surface-2 disabled:cursor-not-allowed',
                pendingId !== null && pendingId !== account.user_id && 'opacity-50',
                isCurrent && 'border-accent',
              )}
            >
              <div className="w-9 h-9 rounded-full bg-surface-2 flex items-center justify-center flex-shrink-0">
                <Building2 size={17} className="text-ink-3" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink-1 truncate">{account.tenant_name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-ink-4 truncate">{account.username}</span>
                  <Badge tone={ROLE_TONES[account.role] ?? 'neutral'}>
                    {ROLE_LABELS[account.role] ?? account.role}
                  </Badge>
                  {isCurrent && <Badge tone="accent">Actual</Badge>}
                </div>
              </div>
              <ChevronRight size={16} className="text-ink-4 flex-shrink-0" />
            </button>
          </li>
        )
      })}
    </ul>
  )
}
