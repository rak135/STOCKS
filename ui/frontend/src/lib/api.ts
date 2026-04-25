import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  AppSettings,
  AppStatus,
  AuditSummary,
  FxYearList,
  ImportSummary,
  OpenPositionList,
  Sell,
  SellList,
  SellReviewPatchRequest,
  TaxYearsResponse,
  YearPatchRequest,
} from '../types/api'

export class ApiError extends Error {
  status: number
  detail: string | null

  constructor(path: string, status: number, detail: string | null = null) {
    super(`Request failed for ${path}: ${status}${detail ? ` (${detail})` : ''}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function toErrorDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null

  const obj = payload as Record<string, unknown>
  const candidate = obj.detail ?? obj.message ?? obj.error
  if (candidate == null) return null

  if (typeof candidate === 'string') {
    const trimmed = candidate.trim()
    return trimmed === '' ? null : trimmed
  }

  try {
    const serialized = JSON.stringify(candidate)
    return serialized === '{}' || serialized === '[]' ? null : serialized
  } catch {
    return String(candidate)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)

  let payload: unknown = null
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json')) {
    payload = await response.json()
  }

  if (!response.ok) {
    const detail = toErrorDetail(payload)

    throw new ApiError(path, response.status, detail)
  }

  return payload as T
}

export function useStatusQuery() {
  return useQuery({
    queryKey: ['status'],
    queryFn: () => request<AppStatus>('/api/status'),
  })
}

export function useImportQuery() {
  return useQuery({
    queryKey: ['import'],
    queryFn: () => request<ImportSummary>('/api/import'),
  })
}

export function useYearsQuery() {
  return useQuery({
    queryKey: ['years'],
    queryFn: () => request<TaxYearsResponse>('/api/years'),
  })
}

export function usePatchYearMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ year, payload }: { year: number; payload: YearPatchRequest }) =>
      request<unknown>(`/api/years/${year}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['years'] }),
        queryClient.invalidateQueries({ queryKey: ['status'] }),
        queryClient.invalidateQueries({ queryKey: ['audit'] }),
        queryClient.invalidateQueries({ queryKey: ['sales'] }),
        queryClient.invalidateQueries({ queryKey: ['fx'] }),
        queryClient.invalidateQueries({ queryKey: ['open-positions'] }),
      ])
    },
  })
}

export function useSettingsQuery() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: () => request<AppSettings>('/api/settings'),
  })
}

export function useAuditQuery() {
  return useQuery({
    queryKey: ['audit'],
    queryFn: () => request<AuditSummary>('/api/audit'),
  })
}

export function useOpenPositionsQuery() {
  return useQuery({
    queryKey: ['open-positions'],
    queryFn: () => request<OpenPositionList>('/api/open-positions'),
  })
}

export function useFxQuery() {
  return useQuery({
    queryKey: ['fx'],
    queryFn: () => request<FxYearList>('/api/fx'),
  })
}

export function useSalesQuery() {
  return useQuery({
    queryKey: ['sales'],
    queryFn: () => request<SellList>('/api/sales'),
  })
}

export function useSaleQuery(sellId: string | null) {
  return useQuery({
    queryKey: ['sale', sellId],
    queryFn: () => request<Sell>(`/api/sales/${sellId}`),
    enabled: Boolean(sellId),
  })
}

export function usePatchSaleReviewMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ sellId, payload }: { sellId: string; payload: SellReviewPatchRequest }) =>
      request<Sell>(`/api/sales/${sellId}/review`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['sale', updated.id], updated)
      queryClient.invalidateQueries({ queryKey: ['sales'] })
    },
  })
}

export function useRecalculateMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () =>
      request<unknown>('/api/recalculate', {
        method: 'POST',
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['status'] }),
        queryClient.invalidateQueries({ queryKey: ['import'] }),
        queryClient.invalidateQueries({ queryKey: ['years'] }),
        queryClient.invalidateQueries({ queryKey: ['sales'] }),
        queryClient.invalidateQueries({ queryKey: ['open-positions'] }),
        queryClient.invalidateQueries({ queryKey: ['fx'] }),
        queryClient.invalidateQueries({ queryKey: ['audit'] }),
        queryClient.invalidateQueries({ queryKey: ['settings'] }),
      ])
    },
  })
}
