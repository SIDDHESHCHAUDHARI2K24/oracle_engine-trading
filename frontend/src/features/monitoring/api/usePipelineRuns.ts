import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { PipelineRunsResponse } from '../../../core/types'

export const pipelineRunKeys = {
  all: ['pipeline-runs'] as const,
  recent: (limit?: number) => [...pipelineRunKeys.all, 'recent', limit] as const,
}

export function usePipelineRuns(limit = 50): UseQueryResult<PipelineRunsResponse> {
  return useQuery({
    queryKey: pipelineRunKeys.recent(limit),
    queryFn: () =>
      apiClient.get<PipelineRunsResponse>(
        `/api/v1/monitoring/pipeline-runs?limit=${limit}`,
      ),
    refetchInterval: 30_000,
  })
}
