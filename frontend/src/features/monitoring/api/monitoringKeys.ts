export const monitoringKeys = {
  all: ['monitoring'] as const,
  ingestStatus: () => [...monitoringKeys.all, 'ingest-status'] as const,
  modelHealth: () => [...monitoringKeys.all, 'model-health'] as const,
  modelCard: (universeId: string) => [...monitoringKeys.all, 'model-card', universeId] as const,
  coverage: (filters: Record<string, string | number>) => [...monitoringKeys.all, 'coverage', filters] as const,
  drift: (universeId: string) => [...monitoringKeys.all, 'drift', universeId] as const,
}
