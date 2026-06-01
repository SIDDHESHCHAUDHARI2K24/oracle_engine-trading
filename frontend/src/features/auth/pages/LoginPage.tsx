import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useLogin } from '../api/useLogin'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '../../../shared/components/ui/card'

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormData = z.infer<typeof loginSchema>

export function LoginPage(): JSX.Element {
  const login = useLogin()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = (data: LoginFormData): void => {
    login.mutate(data)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Oracle Engine</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <div className="space-y-1">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                aria-describedby={errors['email'] ? 'email-error' : undefined}
                {...register('email')}
              />
              {errors['email'] && (
                <p id="email-error" className="text-sm text-red-600" role="alert">
                  {errors['email'].message}
                </p>
              )}
            </div>
            <div className="space-y-1">
              <label htmlFor="password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-describedby={errors['password'] ? 'password-error' : undefined}
                {...register('password')}
              />
              {errors['password'] && (
                <p id="password-error" className="text-sm text-red-600" role="alert">
                  {errors['password'].message}
                </p>
              )}
            </div>
            {login.isError && (
              <p className="text-sm text-red-600" role="alert">
                {login.error.message}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? 'Signing in\u2026' : 'Log in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
