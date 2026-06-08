import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useParams, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useCreateUniverse } from '../api/useCreateUniverse'
import { useUpdateUniverse } from '../api/useUpdateUniverse'
import { useUniverse } from '../api/useUniverse'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '../../../shared/components/ui/card'
import { ApiRequestError } from '../../../core/api-client'

const universeFormSchema = z.object({
  name: z
    .string()
    .min(1, 'Name is required')
    .regex(/^[a-z0-9_-]+$/, 'Only lowercase letters, numbers, hyphens, underscores'),
  display_name: z.string().min(1, 'Display name is required'),
  description: z.string().optional(),
})

type UniverseFormData = z.infer<typeof universeFormSchema>

interface UniverseFormPageProps {
  readonly mode: 'create' | 'edit'
}

export function UniverseFormPage({ mode }: UniverseFormPageProps): JSX.Element {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const createUniverse = useCreateUniverse()
  const updateUniverse = useUpdateUniverse(id ?? '')
  const { data: existingUniverse, isLoading: isLoadingUniverse } = useUniverse(
    mode === 'edit' ? (id ?? '') : '',
  )

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UniverseFormData>({
    resolver: zodResolver(universeFormSchema),
  })

  useEffect(() => {
    if (existingUniverse) {
      reset({
        name: existingUniverse.name,
        display_name: existingUniverse.display_name,
        description: existingUniverse.description ?? undefined,
      })
    }
  }, [existingUniverse, reset])

  useEffect(() => {
    if (existingUniverse?.is_system_managed) {
      navigate('/universes', { replace: true })
    }
  }, [existingUniverse, navigate])

  const createError = createUniverse.error
  const updateError = updateUniverse.error
  const apiError: Error | null = mode === 'create' ? createError : updateError

  const onSubmit = (data: UniverseFormData): void => {
    const payload = {
      name: data.name,
      display_name: data.display_name,
      ...(data.description ? { description: data.description } : {}),
    }

    if (mode === 'create') {
      createUniverse.mutate(payload, {
        onSuccess: (result) => {
          navigate(`/universes/${result.id}`)
        },
      })
    } else if (id) {
      updateUniverse.mutate(payload, {
        onSuccess: () => {
          navigate(`/universes/${id}`)
        },
      })
    }
  }

  const isPending = mode === 'create' ? createUniverse.isPending : updateUniverse.isPending
  const title = mode === 'create' ? 'Create Universe' : 'Edit Universe'

  if (mode === 'edit' && isLoadingUniverse) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading universe...</p>
      </div>
    )
  }

  if (mode === 'edit' && existingUniverse?.is_system_managed) {
    return <></>
  }

  return (
    <div className="mx-auto max-w-lg p-8">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <div className="space-y-1">
              <label htmlFor="name" className="text-sm font-medium">
                Slug
              </label>
              <Input
                id="name"
                autoComplete="off"
                disabled={mode === 'edit'}
                aria-describedby={errors.name ? 'name-error' : undefined}
                {...register('name')}
              />
              {errors.name && (
                <p id="name-error" className="text-sm text-red-600" role="alert">
                  {errors.name.message}
                </p>
              )}
            </div>

            <div className="space-y-1">
              <label htmlFor="display_name" className="text-sm font-medium">
                Display Name
              </label>
              <Input
                id="display_name"
                autoComplete="off"
                aria-describedby={errors.display_name ? 'display_name-error' : undefined}
                {...register('display_name')}
              />
              {errors.display_name && (
                <p id="display_name-error" className="text-sm text-red-600" role="alert">
                  {errors.display_name.message}
                </p>
              )}
            </div>

            <div className="space-y-1">
              <label htmlFor="description" className="text-sm font-medium">
                Description
              </label>
              <textarea
                id="description"
                rows={3}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                {...register('description')}
              />
            </div>

            {apiError && (
              <p className="text-sm text-red-600" role="alert">
                {apiError instanceof ApiRequestError && apiError.code === 'DUPLICATE_UNIVERSE'
                  ? 'A universe with this name already exists.'
                  : apiError.message}
              </p>
            )}

            <div className="flex items-center gap-3 pt-2">
              <Button type="submit" disabled={isPending}>
                {isPending ? 'Saving...' : mode === 'create' ? 'Create' : 'Save'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/universes')}
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
