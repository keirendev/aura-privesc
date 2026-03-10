import { useQuery } from '@tanstack/react-query'
import { getScanStatus } from '../api/client'
import type { ScanStatus } from '../api/types'

export function useJob(scanId: string | undefined) {
  return useQuery<ScanStatus>({
    queryKey: ['scan-status', scanId],
    queryFn: () => getScanStatus(scanId!),
    enabled: !!scanId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 2000
      if (data.status === 'completed' || data.status === 'failed') return false
      return 2000
    },
  })
}
