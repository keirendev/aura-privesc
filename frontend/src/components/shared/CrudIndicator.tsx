import type { CrudValidationResult } from '../../api/types'

function OpIcon({ success }: { success: boolean }) {
  return success ? (
    <span style={{ color: 'var(--green)' }}>&#x2713;</span>
  ) : (
    <span style={{ color: 'var(--red)' }}>&#x2717;</span>
  )
}

function Dash() {
  return <span style={{ color: 'var(--muted)' }}>&mdash;</span>
}

export function CrudCell({
  crud_validation,
  op,
}: {
  crud_validation: CrudValidationResult | null
  op: 'create' | 'update' | 'delete'
}) {
  if (!crud_validation) return <Dash />
  const result = crud_validation[op]
  if (!result) return <Dash />
  return <OpIcon success={result.success} />
}

export function ReadableIcon({ readable }: { readable: boolean }) {
  return readable ? <OpIcon success={true} /> : <OpIcon success={false} />
}
