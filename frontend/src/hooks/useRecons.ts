import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { checkSfCli, createRecon, listRecons, getRecon, getReconStatus, cancelRecon, deleteRecon } from '../api/client'
import type { ReconCreateRequest, ReconDetail, ReconStatus, ReconSummary } from '../api/types'

export function useSfCliCheck() {
  return useQuery({
    queryKey: ['sf-cli-check'],
    queryFn: checkSfCli,
    staleTime: 60_000,
  })
}

export function useRecons() {
  return useQuery<ReconSummary[]>({
    queryKey: ['recons'],
    queryFn: listRecons,
  })
}

export function useRecon(id: string | null) {
  return useQuery<ReconDetail>({
    queryKey: ['recon', id],
    queryFn: () => getRecon(id!),
    enabled: !!id,
  })
}

export function useReconStatus(id: string | null, enabled: boolean) {
  return useQuery<ReconStatus>({
    queryKey: ['recon-status', id],
    queryFn: () => getReconStatus(id!),
    enabled: !!id && enabled,
    refetchInterval: 2000,
  })
}

export function useCreateRecon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ReconCreateRequest) => createRecon(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recons'] })
    },
  })
}

export function useCancelRecon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => cancelRecon(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recons'] })
    },
  })
}

export function useDeleteRecon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteRecon(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recons'] })
    },
  })
}
