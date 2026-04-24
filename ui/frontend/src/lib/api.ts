import { useQuery } from '@tanstack/react-query'
import type { AppStatus, ImportSummary, TaxYear } from '../types/api'

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path)

  if (!response.ok) {
    throw new Error(`Request failed for ${path}: ${response.status}`)
  }

  return (await response.json()) as T
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
    queryFn: () => request<TaxYear[]>('/api/years'),
  })
}
