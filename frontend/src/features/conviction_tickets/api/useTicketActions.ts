import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { TicketActionResponse, ConvictionTicket } from '../../../core/types'
import { ticketKeys } from './useTickets'

export function useReviewTicket(
  ticketId: string,
): UseMutationResult<TicketActionResponse, Error, void> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiClient.post<TicketActionResponse>(`/api/v1/tickets/${ticketId}/review`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets', ticketId] })
      queryClient.invalidateQueries({ queryKey: ticketKeys.all })
    },
  })
}

export function useActionTicket(
  ticketId: string,
): UseMutationResult<TicketActionResponse, Error, { notes?: string }> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) =>
      apiClient.post<TicketActionResponse>(`/api/v1/tickets/${ticketId}/action`, body),
    onMutate: async (body) => {
      await queryClient.cancelQueries({ queryKey: ['tickets', ticketId] })
      const previous = queryClient.getQueryData<ConvictionTicket>(['tickets', ticketId])
      if (previous) {
        queryClient.setQueryData<ConvictionTicket>(['tickets', ticketId], {
          ...previous,
          status: 'ACTIONED',
          user_notes: body.notes ?? previous.user_notes,
        })
      }
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['tickets', ticketId], context.previous)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets', ticketId] })
      queryClient.invalidateQueries({ queryKey: ticketKeys.all })
    },
  })
}
