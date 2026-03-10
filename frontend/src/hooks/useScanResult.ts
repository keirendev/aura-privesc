import { useQuery } from '@tanstack/react-query'
import { getScan } from '../api/client'
import type { ScanDetail } from '../api/types'

export function useScanResult(scanId: string | undefined) {
  return useQuery<ScanDetail>({
    queryKey: ['scan', scanId],
    queryFn: () => getScan(scanId!),
    enabled: !!scanId,
  })
}
