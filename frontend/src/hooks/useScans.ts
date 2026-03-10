import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listScans, createScan, cancelScan, deleteScan } from '../api/client'
import type { ScanCreateRequest, ScanSummary } from '../api/types'

export function useScans() {
  return useQuery<ScanSummary[]>({
    queryKey: ['scans'],
    queryFn: listScans,
  })
}

export function useCreateScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ScanCreateRequest) => createScan(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] })
    },
  })
}

export function useCancelScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => cancelScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] })
    },
  })
}

export function useDeleteScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] })
    },
  })
}
